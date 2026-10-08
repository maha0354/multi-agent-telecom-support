from functools import lru_cache

from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import GEMINI_MODEL, GEMINI_REQUESTS_PER_MINUTE

# Free-tier quotas are per minute per model (15 for gemini-3.5-flash-lite). Waiting for a slot
# is better than failing a turn halfway; one "both" question uses about 8 calls.
_rate_limiter = InMemoryRateLimiter(
    requests_per_second=GEMINI_REQUESTS_PER_MINUTE / 60,
    check_every_n_seconds=0.1,
    max_bucket_size=8,
)


@lru_cache
def get_llm() -> ChatGoogleGenerativeAI:
    # max_retries backs off on transient errors before giving up.
    return ChatGoogleGenerativeAI(model=GEMINI_MODEL, max_retries=3, timeout=60, rate_limiter=_rate_limiter)
