"""Graph state. Only `messages` (and the code-set customer) carry over between turns;
every other field is per-turn work and is reset by load_context at the start of each turn."""

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

AgentName = Literal["support", "analyst"]
AgentStatus = Literal["ok", "ok_empty", "no_relevant_info", "error"]
Verdict = Literal["pass", "fail", "dropped"]


class Evidence(TypedDict):
    id: str            # "E1", "E2", ... assigned by code, never by the LLM
    agent: str
    tool: str
    args: dict
    output: object     # raw tool result


class Claim(TypedDict):
    id: str            # "support-1", "analyst-2", ...
    agent: str
    text: str
    evidence_ids: list[str]
    verdict: Verdict | None
    reason: str | None
    policy_violation: bool


class GraphState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    customer_id: str
    customer_area: str

    # Per-turn fields
    question: str
    category: str
    route_reason: str
    clarifying_question: str | None
    plan: list[str]              # remaining agents to run, in order
    phase: Literal["plan", "retry"]
    current_agent: str | None
    agent_status: dict[str, str]
    evidence: dict[str, Evidence]
    claims: list[Claim]
    feedback: dict[str, str]     # verifier feedback per agent, used on retry
    retries: dict[str, int]
    retry_queue: list[str]
    replans: int
    next: str                    # routing decision written by code nodes
    notes: list[str]             # parts removed after verification, for the responder
    draft: str
    numbers_feedback: str | None
    numbers_retries: int
    answer: str
    step: dict                   # latest trace step, streamed to the UI


def fresh_turn(question: str) -> dict:
    return {
        "question": question,
        "category": "",
        "route_reason": "",
        "clarifying_question": None,
        "plan": [],
        "phase": "plan",
        "current_agent": None,
        "agent_status": {},
        "evidence": {},
        "claims": [],
        "feedback": {},
        "retries": {},
        "retry_queue": [],
        "replans": 0,
        "next": "",
        "notes": [],
        "draft": "",
        "numbers_feedback": None,
        "numbers_retries": 0,
        "answer": "",
    }
