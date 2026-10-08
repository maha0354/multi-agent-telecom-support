"""Currency conversion via the Frankfurter public API (ECB rates, no API key)."""

import httpx

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"
TIMEOUT_SECONDS = 5.0


def convert_currency(
    amount: float, from_currency: str, to_currency: str, client: httpx.Client | None = None
) -> dict:
    """Convert an amount between ISO currency codes. Failures return an error result, never raise."""
    source, target = from_currency.upper(), to_currency.upper()
    if source == target:
        return {"amount": amount, "from": source, "to": target, "rate": 1.0, "result": amount}

    owns_client = client is None
    client = client or httpx.Client(timeout=TIMEOUT_SECONDS)
    try:
        response = client.get(FRANKFURTER_URL, params={"base": source, "symbols": target})
        response.raise_for_status()
        data = response.json()
        rate = data["rates"][target]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        return {"amount": amount, "from": source, "to": target,
                "error": f"Currency service unavailable: {type(exc).__name__}"}
    finally:
        if owns_client:
            client.close()

    return {
        "amount": amount,
        "from": source,
        "to": target,
        "rate": rate,
        "result": round(amount * rate, 2),
        "rate_date": data.get("date"),
    }
