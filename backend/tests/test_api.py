"""API tests with a fake graph, so no LLM is called."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from langchain_google_genai.chat_models import GoogleRateLimitError

import app.main as main


class FakeGraph:
    def __init__(self, updates=None, error=None, delay=0.0, owner=None):
        self.updates, self.error, self.delay, self.owner = updates or [], error, delay, owner

    async def aget_state(self, config):
        return SimpleNamespace(values={"customer_id": self.owner} if self.owner else {})

    async def astream(self, inputs, config, stream_mode):
        assert config["configurable"]["thread_id"] == "t-1"
        assert inputs["customer_id"] == "C-1001"  # code passes the selected customer into state
        for update in self.updates:
            await asyncio.sleep(self.delay)
            yield update
        if self.error:
            raise self.error


def run(graph) -> list[tuple[str, dict]]:
    async def collect():
        return [chunk async for chunk in main.stream_turn(graph, "t-1", "C-1001", "hello")]

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


CUSTOMERS = [{"id": "C-1001", "name": "Alex Demo", "area": "Uppsala", "plan_name": "Plus 30 GB"},
             {"id": "C-1002", "name": "Sara Demo", "area": "Malmö", "plan_name": "Bas 10 GB"}]


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(main, "list_customers", lambda: CUSTOMERS)
    main.app.state.graph = FakeGraph()
    return TestClient(main.app)  # no lifespan: startup data checks are not run


def chat(client, **overrides):
    body = {"thread_id": "t-1", "customer_id": "C-1001", "message": "hi", **overrides}
    return client.post("/api/chat", json=body)


@pytest.mark.parametrize("overrides", [{"message": ""}, {"thread_id": ""}, {"customer_id": ""}])
def test_invalid_request_rejected(client, overrides):
    assert chat(client, **overrides).status_code == 422


def test_unknown_customer_rejected(client):
    assert chat(client, customer_id="C-9999").status_code == 422


def test_conversation_cannot_switch_customer(client):
    main.app.state.graph = FakeGraph(owner="C-1002")
    response = chat(client, customer_id="C-1001")
    assert response.status_code == 409


def test_conversation_continues_for_same_customer(client):
    main.app.state.graph = FakeGraph([{"numbers_check": {"answer": "Hi!"}}], owner="C-1001")
    assert "event: answer" in chat(client).text


def test_customers_endpoint(client):
    assert [c["id"] for c in client.get("/api/customers").json()] == ["C-1001", "C-1002"]
