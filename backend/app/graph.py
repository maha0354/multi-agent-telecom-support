"""The LangGraph workflow: which node runs when, and the plain-code nodes between the LLM agents.

user → load_context → router ─ out_of_scope → refuse
                             ─ unclear → clarify
                             ─ plan → agent → step_check → (next agent | router re-plan | verifier)
                                     verifier → (retry agent → step_check → verifier) | responder
                                     responder → numbers_check → (responder once more | END)
"""

import time
from functools import wraps

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.analyst import analyst_node
from app.agents.responder import POLICY_FALLBACK, responder_node, verified_claims
from app.agents.router import router_node
from app.agents.support import support_node
from app.agents.verifier import verifier_node
from app.checks import MAX_NUMBER_RETRIES, next_after_agent, unsupported_numbers
from app.config import DEMO_CUSTOMER_ID
from app.state import GraphState, fresh_turn
from app.tools.account import get_my_account

# Backstop if the graph's own counters have a bug. The longest legitimate path is 22 steps
# (2 agents, a re-plan running both again, 2 retries, 2 verifications, 2 responder drafts).
RECURSION_LIMIT = 25

REFUSAL = ("I can only help with Martins Mobile questions: plans, roaming, billing, refunds and "
           "connectivity. Is there something about your mobile service I can help with?")


def load_context(state: GraphState) -> dict:
    """Reset per-turn fields and inject the logged-in customer. Runs in code, never the LLM."""
    account = get_my_account(DEMO_CUSTOMER_ID)
    return {
        **fresh_turn(state["messages"][-1].text),
        "customer_id": DEMO_CUSTOMER_ID,
        "customer_area": account.get("area", ""),
        "step": {"node": "load_context", "summary": f"customer {DEMO_CUSTOMER_ID} ({account.get('plan_name')})",
                 "detail": {}},
    }


def step_check(state: GraphState) -> dict:
    agent = state["current_agent"]
    plan = [a for a in state["plan"] if a != agent] if state["phase"] == "plan" else state["plan"]
    retry_queue = state["retry_queue"][1:] if state["phase"] == "retry" else state["retry_queue"]
    status = state["agent_status"][agent]
    nxt = next_after_agent(state["phase"], status, plan, retry_queue, state["replans"])
    return {
        "plan": plan,
        "retry_queue": retry_queue,
        "next": nxt,
        "step": {"node": "step_check", "summary": f"{agent} {status} → {nxt}",
                 "detail": {"remaining_plan": plan, "retry_queue": retry_queue}},
    }


def numbers_check(state: GraphState) -> dict:
    """Every number in the reply must appear in a verified claim (or the customer's own message)."""
    facts = verified_claims(state)
    bad = sorted(unsupported_numbers(state["draft"], facts + [state["question"]]))
    if not bad:
        return _finish(state["draft"], "numbers_check: all numbers supported")
    if state["numbers_retries"] < MAX_NUMBER_RETRIES:
        return {
            "numbers_retries": state["numbers_retries"] + 1,
            "numbers_feedback": f"it contained numbers not found in the facts: {bad}.",
            "next": "responder",
            "step": {"node": "numbers_check", "summary": f"numbers_check: unsupported {bad} → regenerate",
                     "detail": {"unsupported": bad}},
        }
    # Safe fallback: the verified facts themselves, which pass the check by construction.
    reply = "Here is what I could confirm:\n\n" + "\n".join(f"- {f}" for f in facts)
    if "policy" in state["notes"]:
        reply += f"\n\n{POLICY_FALLBACK}"
    return _finish(reply, f"numbers_check: unsupported {bad} again → verified facts as reply")


def _finish(answer: str, summary: str) -> dict:
    return {"answer": answer, "next": END, "messages": [AIMessage(answer)],
            "step": {"node": "numbers_check", "summary": summary, "detail": {}}}


def refuse(state: GraphState) -> dict:
    return {"answer": REFUSAL, "messages": [AIMessage(REFUSAL)],
            "step": {"node": "refuse", "summary": "out of scope: refusal", "detail": {}}}


def clarify(state: GraphState) -> dict:
    question = state["clarifying_question"] or "Could you tell me a bit more about what you need help with?"
    return {"answer": question, "messages": [AIMessage(question)],
            "step": {"node": "clarify", "summary": "asked a clarifying question", "detail": {}}}


def route_after_router(state: GraphState) -> str:
    if state["category"] == "out_of_scope":
        return "refuse"
    if state["category"] == "unclear":
        return "clarify"
    return state["plan"][0] if state["plan"] else "verifier"


def _traced(name: str, fn):
    """Adds the node's run time to its trace step."""
    @wraps(fn)
    def wrapper(state):
        start = time.perf_counter()
        update = fn(state)
        update.setdefault("step", {"node": name, "summary": name, "detail": {}})
        update["step"]["duration_ms"] = round((time.perf_counter() - start) * 1000)
        return update
    return wrapper


def build_graph(checkpointer=None):
    g = StateGraph(GraphState)
    nodes = {
        "load_context": load_context, "router": router_node, "refuse": refuse, "clarify": clarify,
        "support": support_node, "analyst": analyst_node, "step_check": step_check,
        "verifier": verifier_node, "responder": responder_node, "numbers_check": numbers_check,
    }
    for name, fn in nodes.items():
        g.add_node(name, _traced(name, fn))

    g.add_edge(START, "load_context")
    g.add_edge("load_context", "router")
    g.add_conditional_edges("router", route_after_router,
                            ["refuse", "clarify", "support", "analyst", "verifier"])
    g.add_edge("support", "step_check")
    g.add_edge("analyst", "step_check")
    g.add_conditional_edges("step_check", lambda s: s["next"], ["support", "analyst", "router", "verifier"])
    g.add_conditional_edges("verifier", lambda s: s["next"], ["support", "analyst", "responder"])
    g.add_edge("responder", "numbers_check")
    g.add_conditional_edges("numbers_check", lambda s: s["next"], ["responder", END])
    g.add_edge("refuse", END)
    g.add_edge("clarify", END)
    return g.compile(checkpointer=checkpointer or MemorySaver())
