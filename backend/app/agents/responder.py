from langchain_core.messages import HumanMessage, SystemMessage

from app.llm import get_llm

PROMPT = """You write the final reply to a customer of Martins Mobile, a fictional Swedish mobile operator.
Use ONLY the verified facts provided. Do not add facts, and do not calculate anything: every
number in your reply must appear exactly as written in the facts (no new totals, differences or
conversions, no thousands separators). Answer the customer's question directly, be concise and
friendly, and use short paragraphs or bullet points. Do not mention claims, agents or verification."""

NOTE_TEXT = {
    "unverified": "Part of the answer could not be verified and was removed. Briefly say you could "
                  "not confirm that part and suggest contacting customer service for it.",
    "policy": "Part of the answer was removed for policy reasons. Say that for this part the customer "
              "should contact customer service.",
}

NO_FACTS_REPLY = ("I'm sorry, I couldn't find verified information to answer that. Please contact "
                  "customer service in the app or by phone, and they'll be happy to help.")
POLICY_FALLBACK = "For part of your question, please contact customer service."


def verified_claims(state: dict) -> list[str]:
    return [c["text"] for c in state["claims"] if c["verdict"] == "pass"]


def responder_node(state: dict) -> dict:
    facts = verified_claims(state)
    if not facts:
        return {"draft": NO_FACTS_REPLY,
                "step": {"node": "responder", "summary": "responder: no verified facts, fixed reply",
                         "detail": {"llm_calls": 0}}}

    task = [f"Customer's message: {state['question']}", "Verified facts:\n" + "\n".join(f"- {f}" for f in facts)]
    for note in dict.fromkeys(state["notes"]):
        task.append(f"Note: {NOTE_TEXT[note]}")
    if state["numbers_feedback"]:
        task.append(f"Your previous draft was rejected: {state['numbers_feedback']} Rewrite it using only "
                    "numbers that appear in the facts.")

    draft = get_llm().invoke([SystemMessage(PROMPT), HumanMessage("\n\n".join(task))]).text
    regenerated = bool(state["numbers_feedback"])
    return {"draft": draft,
            "step": {"node": "responder",
                     "summary": "responder: regenerated reply" if regenerated else "responder: drafted reply",
                     "detail": {"llm_calls": 1, "facts_used": len(facts), "notes": state["notes"]}}}
