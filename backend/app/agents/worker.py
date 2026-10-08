"""Tool loop shared by the support agent and the account analyst.

The LLM picks tools for up to MAX_TOOL_ROUNDS rounds, then reports its findings through
`submit_findings`. Every tool output is recorded as evidence by code with an ID; claims
must cite those IDs so the verifier checks them against real tool results.
"""

import json
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel, Field, ValidationError

from app.agents.tools import ToolSpec, is_error, run_tool
from app.checks import normalize_status
from app.llm import get_llm

MAX_TOOL_ROUNDS = 3
MAX_TOOL_RESULT_CHARS = 4000


class ClaimIn(BaseModel):
    text: str = Field(description="One self-contained factual statement, with exact figures")
    evidence_ids: list[str] = Field(description="Evidence IDs (E1, E2, ...) that support it")


class Findings(BaseModel):
    """Report your findings. Call this exactly once, when you are done."""
    status: Literal["ok", "ok_empty", "no_relevant_info", "error"] = Field(
        description="ok: found what was needed. ok_empty: tools worked and the answer is 'none' "
                    "(e.g. no outages). no_relevant_info: nothing relevant found. error: tools failed.")
    claims: list[ClaimIn]


# convert_to_openai_tool inlines the nested ClaimIn schema; Gemini ignores "$defs" references.
SUBMIT_TOOL = convert_to_openai_tool(Findings)
SUBMIT_TOOL["function"]["name"] = "submit_findings"

COMMON_RULES = """Rules:
- Use tools to get facts; never rely on your own knowledge for operator facts or prices.
- Every claim must cite the evidence IDs (E1, E2, ...) of the tool results it is based on.
- Copy figures exactly from tool results. Any figure you compute must come from cost_calculator.
- Make claims short and self-contained; include units and currency. A claim states one finished
  fact: never put reasoning, drafts or second thoughts in a claim.
- Finish by calling submit_findings once."""


def _history_text(messages: list, limit: int = 6) -> str:
    lines = [f"{m.type}: {m.text}" for m in messages[-limit:-1] if m.type in ("human", "ai")]
    return "\n".join(lines) or "(none)"


def _task_text(agent: str, state: dict) -> str:
    parts = [
        f"Conversation so far:\n{_history_text(state['messages'])}",
        f"Customer's latest message: {state['question']}",
        f"Customer's area: {state['customer_area']}",
    ]
    others = [c for c in state["claims"] if c["agent"] != agent and c["verdict"] != "dropped"]
    if others:
        parts.append("Findings from other agents:\n" + "\n".join(f"- {c['text']}" for c in others))
    if state["phase"] == "retry" and agent in state["feedback"]:
        kept = [c for c in state["claims"] if c["agent"] == agent and c["verdict"] == "pass"]
        if kept:
            parts.append("Your claims that were already verified (do not repeat them):\n"
                         + "\n".join(f"- {c['text']}" for c in kept))
        parts.append("A verifier rejected some of your claims. Fix them using tools; submit only "
                     f"corrected or replacement claims.\nVerifier feedback:\n{state['feedback'][agent]}")
    return "\n\n".join(parts)


def run_worker(agent: str, system_prompt: str, tools: list[ToolSpec], state: dict) -> dict:
    by_name = {t.name: t for t in tools}
    llm = get_llm().bind_tools([t.schema() for t in tools] + [SUBMIT_TOOL])
    messages = [SystemMessage(f"{system_prompt}\n\n{COMMON_RULES}"), HumanMessage(_task_text(agent, state))]

    evidence = dict(state["evidence"])
    calls_made: list[dict] = []
    findings: Findings | None = None

    for round_no in range(MAX_TOOL_ROUNDS + 1):
        ai = llm.invoke(messages)
        messages.append(ai)
        if not ai.tool_calls:
            break
        for call in ai.tool_calls:
            if call["name"] == "submit_findings":
                try:
                    findings = Findings.model_validate(call["args"])
                    messages.append(ToolMessage("Received.", tool_call_id=call["id"]))
                except ValidationError as exc:
                    # Schema is required but not guaranteed; let the model correct itself.
                    messages.append(ToolMessage(
                        f"Invalid submission: {exc.errors(include_url=False)}. Call submit_findings "
                        "again with both 'status' and 'claims'.", tool_call_id=call["id"]))
                continue
            spec = by_name.get(call["name"])
            result = run_tool(spec, state, call["args"]) if spec else {"error": f"Unknown tool {call['name']}"}
            evidence_id = f"E{len(evidence) + 1}"
            evidence[evidence_id] = {"id": evidence_id, "agent": agent, "tool": call["name"],
                                     "args": call["args"], "output": result}
            calls_made.append({"evidence_id": evidence_id, "tool": call["name"], "args": call["args"],
                               "error": is_error(result)})
            content = json.dumps({"evidence_id": evidence_id, "result": result}, default=str)
            messages.append(ToolMessage(content[:MAX_TOOL_RESULT_CHARS], tool_call_id=call["id"]))
        if findings:
            break
        if round_no == MAX_TOOL_ROUNDS - 1:
            messages.append(HumanMessage("Tool budget used up. Call submit_findings now."))

    if findings is None:
        # The model answered in plain text or ran out of rounds: ask once for structured findings.
        findings = get_llm().with_structured_output(Findings).invoke(
            messages + [HumanMessage("Report your findings now in the required structure.")])

    own_evidence = {eid for eid, e in evidence.items() if e["agent"] == agent}
    start = sum(1 for c in state["claims"] if c["agent"] == agent) + 1
    claims = [
        {"id": f"{agent}-{start + i}", "agent": agent, "text": c.text,
         "evidence_ids": c.evidence_ids, "verdict": None, "reason": None, "policy_violation": False}
        for i, c in enumerate(findings.claims)
    ]
    status = normalize_status(findings.status, len(claims), any(c["error"] for c in calls_made))

    return {
        "evidence": evidence,
        "claims": state["claims"] + claims,
        "agent_status": {**state["agent_status"], agent: status},
        "current_agent": agent,
        "step": {
            "node": agent,
            "summary": f"{agent}: {status}, {len(calls_made)} tool call(s), {len(claims)} claim(s)"
                       + (" (retry)" if state["phase"] == "retry" else ""),
            "detail": {"status": status, "tool_calls": calls_made, "claims": claims,
                       "evidence": {eid: evidence[eid] for eid in own_evidence - set(state["evidence"])}},
        },
    }
