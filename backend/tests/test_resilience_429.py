"""
Integration test for 429 Retry-After handling in resilient_request.

Tests the full retry loop (not just _retry_after_seconds in isolation)
by using httpx.MockTransport to simulate real 429 responses.
"""
import time
from unittest.mock import patch

import httpx
import pytest

from app.core.resilience import resilient_request, ExternalServiceError


class _SequentialTransport(httpx.BaseTransport):
    """Returns responses in order; last response repeats if list exhausted."""

    def __init__(self, responses: list[httpx.Response]):
        self._responses = list(responses)
        self._idx = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        resp = self._responses[min(self._idx, len(self._responses) - 1)]
        self._idx += 1
        # Attach request so raise_for_status() works
        return httpx.Response(
            resp.status_code,
            headers=dict(resp.headers),
            content=resp.content,
            request=request,
        )


def _mock_client(transport: _SequentialTransport):
    """Patch httpx.Client so resilient_request uses our transport."""
    original_init = httpx.Client.__init__

    def patched_init(self, *args, **kwargs):
        kwargs.pop("transport", None)
        original_init(self, *args, transport=transport, **kwargs)

    return patch.object(httpx.Client, "__init__", patched_init)


# ---------------------------------------------------------------------------

def test_retry_after_header_used_instead_of_backoff():
    """On 429 with Retry-After: 3, sleep(3) not sleep(backoff * 2^0)."""
    transport = _SequentialTransport([
        httpx.Response(429, headers={"retry-after": "3"}),
        httpx.Response(200, text="ok"),
    ])

    slept: list[float] = []
    with _mock_client(transport), patch("time.sleep", side_effect=slept.append):
        result = resilient_request("GET", "http://test/", retries=1, backoff=0.1)

    assert result.status_code == 200
    assert len(slept) == 1
    assert slept[0] == 3.0, f"expected sleep(3.0), got sleep({slept[0]})"


def test_exponential_backoff_used_when_no_retry_after():
    """On non-429 failure, sleep uses backoff formula, not Retry-After."""
    transport = _SequentialTransport([
        httpx.Response(503),
        httpx.Response(200, text="ok"),
    ])

    slept: list[float] = []
    with _mock_client(transport), patch("time.sleep", side_effect=slept.append):
        result = resilient_request("GET", "http://test/", retries=1, backoff=0.5)

    assert result.status_code == 200
    assert len(slept) == 1
    assert slept[0] == 0.5, f"expected backoff sleep(0.5), got sleep({slept[0]})"


def test_raises_after_all_retries_exhausted_on_429():
    """All attempts return 429 → ExternalServiceError raised."""
    transport = _SequentialTransport([
        httpx.Response(429, headers={"retry-after": "1"}),
        httpx.Response(429, headers={"retry-after": "1"}),
    ])

    with _mock_client(transport), patch("time.sleep"):
        with pytest.raises(ExternalServiceError):
            resilient_request("GET", "http://test/", retries=1, backoff=0.1)


def test_429_without_retry_after_falls_back_to_backoff():
    """429 with no Retry-After header → use backoff formula, not crash."""
    transport = _SequentialTransport([
        httpx.Response(429),   # no Retry-After header
        httpx.Response(200, text="ok"),
    ])

    slept: list[float] = []
    with _mock_client(transport), patch("time.sleep", side_effect=slept.append):
        result = resilient_request("GET", "http://test/", retries=1, backoff=0.4)

    assert result.status_code == 200
    assert len(slept) == 1
    assert slept[0] == pytest.approx(0.4)
