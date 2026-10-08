"""Plain-code decisions: no LLM calls, so they are cheap, deterministic and unit-tested."""

import re

MAX_REPLANS = 1
MAX_RETRIES_PER_AGENT = 1
MAX_NUMBER_RETRIES = 1

USEFUL_STATUSES = {"ok", "ok_empty"}


def next_after_agent(phase: str, status: str, remaining_plan: list[str],
                     retry_queue: list[str], replans: int) -> str:
    """Step check after an agent finishes. `remaining_plan` / `retry_queue` exclude that agent."""
    if phase == "retry":
        return retry_queue[0] if retry_queue else "verifier"
    if status not in USEFUL_STATUSES and replans < MAX_REPLANS:
        return "router"
    return remaining_plan[0] if remaining_plan else "verifier"


def normalize_status(status: str, claim_count: int, any_tool_error: bool) -> str:
    """Code overrides the agent's self-reported status when the evidence contradicts it."""
    if claim_count == 0 and status in USEFUL_STATUSES:
        return "error" if any_tool_error else "no_relevant_info"
    return status


# A number not preceded by a letter, digit, dot or hyphen, e.g. "129", "68.96", "68,96",
# "1,234", "6GB". Identifiers such as "C-1001" are skipped.
_NUMBER = re.compile(r"(?<![\w.\-])\d+(?:[.,]\d+)*")
# "1. Restart the phone" / "2) ..." list markers are formatting, not facts.
_LIST_MARKER = re.compile(r"^\s*\d+[.)]\s", re.MULTILINE)


def _to_number(token: str) -> float:
    if "," in token:
        head, _, tail = token.rpartition(",")
        # "1,234" is a thousands separator; "68,96" is a decimal comma.
        token = token.replace(",", "") if len(tail) == 3 and "." not in token else f"{head.replace(',', '')}.{tail}"
    return float(token)


def extract_numbers(text: str) -> set[float]:
    text = _LIST_MARKER.sub("", text)
    return {_to_number(t) for t in _NUMBER.findall(text)}


def unsupported_numbers(reply: str, allowed_sources: list[str]) -> set[float]:
    """Numbers in the reply that appear in none of the verified sources."""
    allowed: set[float] = set()
    for source in allowed_sources:
        allowed |= extract_numbers(source)
    return extract_numbers(reply) - allowed
