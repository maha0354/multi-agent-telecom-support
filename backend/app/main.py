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

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langchain_google_genai.chat_models import GoogleRateLimitError
from pydantic import BaseModel, Field

from app.config import DB_PATH
from app.data.seed import seed
from app.graph import RECURSION_LIMIT, build_graph
from app.rag.ingest import ingest
from app.rag.store import get_collection
from app.tools.account import list_customers

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
    # Simulated login: trusted from the browser as a stand-in for an authenticated session.
    customer_id: str = Field(min_length=1, max_length=20)
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


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}


async def stream_turn(graph, thread_id: str, customer_id: str, message: str):
    config = _config(thread_id)
    inputs = {"messages": [HumanMessage(message)], "customer_id": customer_id}
    answer = None
    try:
        async with asyncio.timeout(TURN_TIMEOUT_SECONDS):
            async for update in graph.astream(inputs, config,
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


@app.get("/api/customers")
async def customers():
    return list_customers()


@app.post("/api/chat")
async def chat(request: ChatRequest):
    if request.customer_id not in {c["id"] for c in list_customers()}:
        raise HTTPException(422, "Unknown customer")
    # A conversation belongs to one customer: its history must never be shown to another.
    state = await app.state.graph.aget_state(_config(request.thread_id))
    owner = (state.values or {}).get("customer_id")
    if owner and owner != request.customer_id:
        raise HTTPException(409, "This conversation belongs to another customer. Start a new chat.")
    return StreamingResponse(
        stream_turn(app.state.graph, request.thread_id, request.customer_id, request.message),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/health")
async def health():
    return {"status": "ok"}
