"""API tests with a fake graph, so no LLM is called."""

import asyncio
import json

import pytest
from langchain_google_genai.chat_models import GoogleRateLimitError

import app.main as main


class FakeGraph:
    def __init__(self, updates=None, error=None, delay=0.0):
        self.updates, self.error, self.delay = updates or [], error, delay

    async def astream(self, inputs, config, stream_mode):
        assert config["configurable"]["thread_id"] == "t-1"
        for update in self.updates:
            await asyncio.sleep(self.delay)
            yield update
        if self.error:
            raise self.error


def run(graph) -> list[tuple[str, dict]]:
    async def collect():
        return [chunk async for chunk in main.stream_turn(graph, "t-1", "hello")]

    events = []
    for chunk in asyncio.run(collect()):
        event_line, data_line = chunk.strip().split("\n")
        events.append((event_line.removeprefix("event: "), json.loads(data_line.removeprefix("data: "))))
    return events


def test_steps_then_answer_then_done():
    graph = FakeGraph([
        {"router": {"step": {"node": "router", "summary": "policy → ['support']"}}},
        {"numbers_check": {"step": {"node": "numbers_check", "summary": "ok"}, "answer": "Hi!"}},
    ])
    assert [e for e, _ in run(graph)] == ["step", "step", "answer", "done"]
    assert run(graph)[2][1] == {"answer": "Hi!"}


def test_long_tool_output_is_truncated():
    graph = FakeGraph([{"support": {"step": {"node": "support", "detail": {"text": "x" * 5000}}, "answer": "a"}}])
    step = run(graph)[0][1]
    assert len(step["detail"]["text"]) <= main.MAX_DETAIL_STRING + 1


def test_rate_limit_becomes_readable_error():
    events = run(FakeGraph(error=GoogleRateLimitError("429")))
    assert events[0][0] == "error" and "rate limit" in events[0][1]["message"]
    assert events[-1][0] == "done"


def test_unexpected_exception_does_not_leak_details():
    events = run(FakeGraph(error=RuntimeError("secret internals")))
    assert events[0][0] == "error" and "secret" not in events[0][1]["message"]


def test_timeout_emits_error(monkeypatch):
    monkeypatch.setattr(main, "TURN_TIMEOUT_SECONDS", 0.05)
    events = run(FakeGraph([{"router": {"step": {}}}], delay=0.2))
    assert [e for e, _ in events] == ["error", "done"]


@pytest.mark.parametrize("body", [{"thread_id": "t", "message": ""}, {"thread_id": "", "message": "hi"}])
def test_invalid_request_rejected(body):
    from fastapi.testclient import TestClient
    main.app.state.graph = FakeGraph()
    client = TestClient(main.app)  # no lifespan: startup data checks are not run
    assert client.post("/api/chat", json=body).status_code == 422
