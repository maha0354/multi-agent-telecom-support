from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.llm import get_llm

PROMPT = """You route customer messages for Martins Mobile, a fictional Swedish mobile operator.

Agents:
- support: support documents (roaming zones and which countries are in them, fair use, Travel
  Pass conditions, billing, refunds, troubleshooting, contact info) and network outages.
- analyst: the logged-in customer's own account and usage, plan list and prices, roaming prices
  per zone number, Travel Pass prices, cost calculations, currency conversion. It CANNOT find
  out which zone a country is in.

Categories:
- policy: general rules and information -> usually [support]
- troubleshooting: connectivity problems, outages -> usually [support]
- account: the customer's own plan, usage, prices, calculations -> usually [analyst]
- both: needs facts from the documents AND account data or prices, e.g. the cost of a trip
  to a named country (zone from support, prices from analyst) -> [support, analyst]
- unclear: about telecom support, but too vague to act on even with the conversation history.
  Write ONE short clarifying question.
- out_of_scope: not about this operator's mobile services.

Use the conversation history to resolve follow-ups like "and what about Thailand?"."""

REPLAN = """Re-planning: some agents did not return useful results.
Agent statuses so far: {statuses}
Findings so far:
{findings}
Decide which agents (if any) should still run, in order. Use an empty plan to answer with
what has been found so far."""


class RouteDecision(BaseModel):
    category: Literal["policy", "troubleshooting", "account", "both", "unclear", "out_of_scope"]
    plan: list[Literal["support", "analyst"]] = Field(description="Agents to run, in order")
    clarifying_question: str | None = Field(None, description="Only for category 'unclear'")
    reason: str = Field(description="One sentence explaining the decision")


def _history(messages: list, limit: int = 6) -> str:
    return "\n".join(f"{m.type}: {m.text}" for m in messages[-limit:-1] if m.type in ("human", "ai")) or "(none)"


def router_node(state: dict) -> dict:
    replanning = bool(state["agent_status"])
    task = f"Conversation so far:\n{_history(state['messages'])}\n\nLatest message: {state['question']}"
    if replanning:
        findings = "\n".join(f"- [{c['agent']}] {c['text']}" for c in state["claims"]) or "(none)"
        task += "\n\n" + REPLAN.format(statuses=state["agent_status"], findings=findings)

    decision = get_llm().with_structured_output(RouteDecision).invoke(
        [SystemMessage(PROMPT), HumanMessage(task)])
    decision.plan = list(dict.fromkeys(decision.plan))  # each agent at most once per plan

    if replanning:
        return {
            "plan": decision.plan,
            "replans": state["replans"] + 1,
            "step": {"node": "router", "summary": f"re-plan: {decision.plan or 'answer with findings so far'}",
                     "detail": {"plan": decision.plan, "reason": decision.reason, "replan": True}},
        }
    return {
        "category": decision.category,
        "plan": decision.plan,
        "route_reason": decision.reason,
        "clarifying_question": decision.clarifying_question,
        "step": {"node": "router", "summary": f"{decision.category} → {decision.plan}",
                 "detail": {"category": decision.category, "plan": decision.plan,
                            "reason": decision.reason, "replan": False}},
    }
