import httpx

from app.tools.currency import convert_currency


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_converts_with_api_rate():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["base"] == "SEK"
        assert request.url.params["symbols"] == "EUR"
        return httpx.Response(200, json={"date": "2026-10-06", "rates": {"EUR": 0.088}})

    result = convert_currency(774, "sek", "eur", client=_client(handler))
    assert result["result"] == 68.11
    assert result["rate"] == 0.088
    assert result["rate_date"] == "2026-10-06"


def test_same_currency_skips_api():
    def handler(request):
        raise AssertionError("API should not be called")

    assert convert_currency(100, "SEK", "SEK", client=_client(handler))["result"] == 100


def test_http_error_returns_error_result():
    result = convert_currency(100, "SEK", "EUR", client=_client(lambda r: httpx.Response(503)))
    assert "error" in result and "result" not in result


def test_timeout_returns_error_result():
    def handler(request):
        raise httpx.ConnectTimeout("timed out", request=request)

    assert "error" in convert_currency(100, "SEK", "EUR", client=_client(handler))


def test_unknown_currency_returns_error_result():
    handler = lambda r: httpx.Response(200, json={"date": "2026-10-06", "rates": {}})
    assert "error" in convert_currency(100, "SEK", "XYZ", client=_client(handler))
