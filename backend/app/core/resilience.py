import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class ExternalServiceError(RuntimeError):
    def __init__(self, message: str, *, timeout: bool = False, service_name: str = "external"):
        super().__init__(message)
        self.timeout = timeout
        self.service_name = service_name


@dataclass
class ExternalResponse:
    status_code: int
    headers: dict[str, str]
    text: str
    content: bytes
    url: str

    def json(self) -> Any:
        return httpx.Response(
            status_code=self.status_code,
            headers=self.headers,
            content=self.content,
            request=httpx.Request("GET", self.url),
        ).json()


def build_timeout(
    *,
    total: float | None = None,
    connect: float | None = None,
    read: float | None = None,
    write: float | None = None,
    pool: float | None = None,
) -> httpx.Timeout:
    return httpx.Timeout(
        timeout=total or settings.EXTERNAL_TOTAL_TIMEOUT_SECONDS,
        connect=connect or settings.EXTERNAL_CONNECT_TIMEOUT_SECONDS,
        read=read or settings.EXTERNAL_READ_TIMEOUT_SECONDS,
        write=write or settings.EXTERNAL_WRITE_TIMEOUT_SECONDS,
        pool=pool or settings.EXTERNAL_POOL_TIMEOUT_SECONDS,
    )


def weather_timeout() -> httpx.Timeout:
    return build_timeout(
        total=settings.WEATHER_TIMEOUT_SECONDS,
        connect=settings.WEATHER_CONNECT_TIMEOUT_SECONDS,
        read=settings.WEATHER_READ_TIMEOUT_SECONDS,
    )


def ai_timeout() -> httpx.Timeout:
    return build_timeout(
        total=settings.AI_TIMEOUT_SECONDS,
        connect=settings.EXTERNAL_CONNECT_TIMEOUT_SECONDS,
        read=settings.AI_TIMEOUT_SECONDS,
        write=settings.EXTERNAL_WRITE_TIMEOUT_SECONDS,
    )


def _retry_after_seconds(exc: Exception | None) -> float | None:
    """Return the Retry-After value (seconds) if exc is a 429 HTTPStatusError, else None."""
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
        header = exc.response.headers.get("retry-after") or exc.response.headers.get("Retry-After")
        if header:
            try:
                return float(header)
            except ValueError:
                pass
    return None


def _sleep_backoff(attempt: int, backoff: float, last_error: Exception | None = None) -> None:
    wait = _retry_after_seconds(last_error)
    if wait is not None:
        logger.warning("[resilience] 429 — honouring Retry-After: %.0fs", wait)
        time.sleep(wait)
    elif backoff > 0:
        time.sleep(backoff * (2 ** attempt))


async def _async_sleep_backoff(attempt: int, backoff: float, last_error: Exception | None = None) -> None:
    wait = _retry_after_seconds(last_error)
    if wait is not None:
        logger.warning("[resilience] 429 — honouring Retry-After: %.0fs", wait)
        await asyncio.sleep(wait)
    elif backoff > 0:
        await asyncio.sleep(backoff * (2 ** attempt))


def resilient_request(
    method: str,
    url: str,
    *,
    service_name: str = "external",
    timeout: httpx.Timeout | float | None = None,
    retries: int | None = None,
    backoff: float | None = None,
    follow_redirects: bool = True,
    **kwargs: Any,
) -> ExternalResponse:
    attempts = max((settings.EXTERNAL_RETRY_COUNT if retries is None else retries) + 1, 1)
    retry_backoff = settings.EXTERNAL_BACKOFF_SECONDS if backoff is None else backoff
    request_timeout = timeout or build_timeout()
    last_error: Exception | None = None
    timed_out = False

    for attempt in range(attempts):
        started = time.monotonic()
        try:
            with httpx.Client(timeout=request_timeout, follow_redirects=follow_redirects) as client:
                response = client.request(method, url, **kwargs)
            response.raise_for_status()
            return ExternalResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                text=response.text,
                content=response.content,
                url=str(response.url),
            )
        except httpx.TimeoutException as exc:
            timed_out = True
            last_error = exc
            logger.warning(
                "[%s] timeout attempt %s/%s url=%s elapsed=%.2fs",
                service_name,
                attempt + 1,
                attempts,
                url,
                time.monotonic() - started,
            )
        except Exception as exc:
            last_error = exc
            logger.warning(
                "[%s] request failed attempt %s/%s url=%s error=%s",
                service_name,
                attempt + 1,
                attempts,
                url,
                exc,
            )
        if attempt < attempts - 1:
            _sleep_backoff(attempt, retry_backoff, last_error)

    raise ExternalServiceError(
        f"{service_name} request failed after {attempts} attempt(s): {last_error}",
        timeout=timed_out,
        service_name=service_name,
    ) from last_error


async def resilient_async_request(
    method: str,
    url: str,
    *,
    service_name: str = "external",
    timeout: httpx.Timeout | float | None = None,
    retries: int | None = None,
    backoff: float | None = None,
    follow_redirects: bool = True,
    **kwargs: Any,
) -> ExternalResponse:
    attempts = max((settings.EXTERNAL_RETRY_COUNT if retries is None else retries) + 1, 1)
    retry_backoff = settings.EXTERNAL_BACKOFF_SECONDS if backoff is None else backoff
    request_timeout = timeout or build_timeout()
    last_error: Exception | None = None
    timed_out = False

    for attempt in range(attempts):
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=request_timeout, follow_redirects=follow_redirects) as client:
                response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return ExternalResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                text=response.text,
                content=response.content,
                url=str(response.url),
            )
        except httpx.TimeoutException as exc:
            timed_out = True
            last_error = exc
            logger.warning(
                "[%s] async timeout attempt %s/%s url=%s elapsed=%.2fs",
                service_name,
                attempt + 1,
                attempts,
                url,
                time.monotonic() - started,
            )
        except Exception as exc:
            last_error = exc
            logger.warning(
                "[%s] async request failed attempt %s/%s url=%s error=%s",
                service_name,
                attempt + 1,
                attempts,
                url,
                exc,
            )
        if attempt < attempts - 1:
            await _async_sleep_backoff(attempt, retry_backoff, last_error)

    raise ExternalServiceError(
        f"{service_name} request failed after {attempts} attempt(s): {last_error}",
        timeout=timed_out,
        service_name=service_name,
    ) from last_error
