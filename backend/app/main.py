"""HTTP API. POST /api/chat streams the graph's progress as server-sent events:

    event: step    {node, summary, detail, duration_ms}   one per finished node
    event: answer  {answer}
    event: error   {message}
    event: done    {}

Run with: uv run uvicorn app.main:app --reload
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langchain_google_genai.chat_models import GoogleRateLimitError
from pydantic import BaseModel, Field

from app.config import DB_PATH
from app.data.seed import seed
from app.graph import RECURSION_LIMIT, build_graph
from app.rag.ingest import ingest
from app.rag.store import get_collection

log = logging.getLogger("telecom")

# Typical turns take 7-9 LLM calls (~40 s for a two-agent question under the free-tier rate limit).
TURN_TIMEOUT_SECONDS = 150
MAX_DETAIL_STRING = 600


def ensure_data() -> None:
    """First run convenience: create the database and the vector index if they are missing."""
    if not DB_PATH.exists():
        seed()
        log.info("Seeded %s", DB_PATH)
    if get_collection().count() == 0:
        log.info("Indexed %d doc chunks", ingest())


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_data()
    app.state.graph = build_graph()
    yield


app = FastAPI(title="Martins Mobile support assistant", lifespan=lifespan)


class ChatRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=2000)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _truncate(value):
    """Keep step events small: long tool outputs (doc chunks) are cut for the trace."""
    if isinstance(value, str) and len(value) > MAX_DETAIL_STRING:
        return value[:MAX_DETAIL_STRING] + "…"
    if isinstance(value, dict):
        return {k: _truncate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate(v) for v in value]
    return value


async def stream_turn(graph, thread_id: str, message: str):
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}
    answer = None
    try:
        async with asyncio.timeout(TURN_TIMEOUT_SECONDS):
            async for update in graph.astream({"messages": [HumanMessage(message)]}, config,
                                              stream_mode="updates"):
                for node, values in update.items():
                    values = values or {}
                    if "step" in values:
                        yield _sse("step", _truncate(values["step"]))
                    answer = values.get("answer") or answer
        if answer:
            yield _sse("answer", {"answer": answer})
        else:
            yield _sse("error", {"message": "The assistant finished without an answer."})
    except TimeoutError:
        yield _sse("error", {"message": "This took too long. Please try again."})
    except GoogleRateLimitError:
        yield _sse("error", {"message": "The AI service is busy (free-tier rate limit). "
                                        "Please wait a minute and try again."})
    except Exception:
        log.exception("Turn failed")
        yield _sse("error", {"message": "Something went wrong while answering. Please try again."})
    yield _sse("done", {})


@app.post("/api/chat")
async def chat(request: ChatRequest):
    return StreamingResponse(
        stream_turn(app.state.graph, request.thread_id, request.message),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/health")
async def health():
    return {"status": "ok"}
