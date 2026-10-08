import json
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.checks import MAX_RETRIES_PER_AGENT
from app.llm import get_llm

PROMPT = """You verify claims made by support agents of Martins Mobile before they reach a customer.
For each claim, look ONLY at the evidence it cites (tool outputs) and decide:
- pass: every fact and figure in the claim is directly supported by the cited evidence. For
  calculations, the inputs must match values in the evidence and the result must come from a
  calculator result. Rounding to 2 decimals is fine.
- fail: anything is missing from, or contradicts, the cited evidence. Give a specific reason,
  quoting the evidence value it contradicts when there is one.
Be strict:
- A comparison ("cheapest", "best", "cheaper than") passes only if it holds against EVERY option
  in the cited evidence. Check the actual prices.
- Fail claims that contain reasoning, hesitation or several alternative statements.
Also flag policy_violation if the claim promises something the assistant cannot do (issue
refunds, change plans, buy passes), reveals another customer's data, or gives advice that
contradicts the documents."""


class ClaimVerdict(BaseModel):
    claim_id: str
    verdict: Literal["pass", "fail"]
    reason: str
    policy_violation: bool = False


class Verification(BaseModel):
    verdicts: list[ClaimVerdict]


def _precheck(claim: dict, evidence: dict) -> str | None:
    """Deterministic checks that need no LLM: claims must cite evidence that really exists."""
    if not claim["evidence_ids"]:
        return "The claim cites no evidence."
    unknown = [e for e in claim["evidence_ids"] if e not in evidence]
    if unknown:
        return f"The claim cites evidence that does not exist: {unknown}."
    return None


def verifier_node(state: dict) -> dict:
    claims = [dict(c) for c in state["claims"]]
    evidence = state["evidence"]
    pending = [c for c in claims if c["verdict"] is None]

    for claim in pending:
        if reason := _precheck(claim, evidence):
            claim.update(verdict="fail", reason=reason)

    to_judge = [c for c in pending if c["verdict"] is None]
    llm_calls = 0
    if to_judge:
        cited = sorted({e for c in to_judge for e in c["evidence_ids"]}, key=lambda e: int(e[1:]))
        payload = {
            "claims": [{"claim_id": c["id"], "text": c["text"], "evidence_ids": c["evidence_ids"]} for c in to_judge],
            "evidence": {e: {"tool": evidence[e]["tool"], "args": evidence[e]["args"], "output": evidence[e]["output"]}
                         for e in cited},
        }
        result = get_llm().with_structured_output(Verification).invoke(
            [SystemMessage(PROMPT), HumanMessage(json.dumps(payload, default=str))])
        llm_calls = 1
        by_id = {v.claim_id: v for v in result.verdicts}
        for claim in to_judge:
            v = by_id.get(claim["id"])
            if v is None:
                claim.update(verdict="fail", reason="The verifier returned no verdict for this claim.")
            else:
                claim.update(verdict=v.verdict, reason=v.reason, policy_violation=v.policy_violation)

    notes = list(state["notes"])
    retries = dict(state["retries"])
    feedback: dict[str, str] = {}
    retry_queue: list[str] = []

    for claim in pending:
        if claim["verdict"] != "fail":
            continue
        agent = claim["agent"]
        if claim["policy_violation"]:
            # Never shown, never retried: replaced by a safe fallback in the reply.
            claim["verdict"] = "dropped"
            notes.append("policy")
        elif retries.get(agent, 0) < MAX_RETRIES_PER_AGENT:
            feedback[agent] = feedback.get(agent, "") + f"- Claim: {claim['text']}\n  Problem: {claim['reason']}\n"
            if agent not in retry_queue:
                retry_queue.append(agent)
        else:
            claim["verdict"] = "dropped"
            notes.append("unverified")

    # Failed claims of agents being retried are replaced by the retry's new claims.
    claims = [c for c in claims if not (c["verdict"] == "fail" and c["agent"] in retry_queue)]
    for agent in retry_queue:
        retries[agent] = retries.get(agent, 0) + 1

    passed = sum(c["verdict"] == "pass" for c in pending)
    failed = len(pending) - passed
    summary = f"verifier: {passed} passed, {failed} failed" + (f" → retry {retry_queue}" if retry_queue else "")
    return {
        "claims": claims,
        "notes": notes,
        "retries": retries,
        "feedback": feedback,
        "retry_queue": retry_queue,
        "phase": "retry" if retry_queue else state["phase"],
        "next": retry_queue[0] if retry_queue else "responder",
        "step": {"node": "verifier", "summary": summary,
                 "detail": {"llm_calls": llm_calls, "verdicts": [
                     {k: c[k] for k in ("id", "agent", "text", "verdict", "reason", "policy_violation")}
                     for c in pending]}},
    }
