from datetime import datetime
from typing import Any

from app.core.config import settings
from app.core.real_data import normalize_cache_status


SOURCE_REALTIME = "realtime_api"
SOURCE_DATABASE = "database"
SOURCE_AI = "ai_generated"
SOURCE_CACHED = "cache"
SOURCE_MOCK = "mock"
SOURCE_LEGACY = "legacy"
REALTIME_ERROR_MESSAGE = "Không thể lấy dữ liệu realtime. Vui lòng thử lại sau."
CACHE_WARNING_MESSAGE = "Dữ liệu realtime đang chậm. Đang hiển thị dữ liệu cache gần nhất."


def _normalized_source(
    source: str | None,
    *,
    is_realtime: bool = False,
    is_mock: bool = False,
    cache_status: str | None = None,
) -> str:
    raw = (source or "").lower()
    cache = (cache_status or "").lower()
    if raw in {"legacy", "old_api", "deprecated"}:
        return SOURCE_LEGACY
    if is_mock or raw in {"mock", "demo"} or cache == "mock":
        return SOURCE_MOCK
    if raw in {"ai", "ai_generated", "rule", "rule_based_ai", "explainable_rule_ai"}:
        return SOURCE_AI
    if is_realtime or cache in {"live", "realtime", "refreshed"} or raw in {"realtime", "realtime_api", "open-meteo", "rss"}:
        return SOURCE_REALTIME
    if raw in {"cached", "cache", "fallback"}:
        return SOURCE_CACHED
    if cache in {"cached", "hit", "from_cache", "from_db", "db", "stale", "fresh_cache", "stale_cache"}:
        return SOURCE_CACHED if cache in {"cached", "hit", "from_cache", "stale", "fresh_cache", "stale_cache"} else SOURCE_DATABASE
    if raw in {"database", "db", "market_db"}:
        return SOURCE_DATABASE
    return raw or SOURCE_DATABASE


def dedupe_messages(messages: list[str | None] | tuple[str | None, ...] | None = None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for message in messages or []:
        if not message:
            continue
        text = str(message).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def success_response(
    data: Any,
    *,
    source: str = SOURCE_REALTIME,
    is_realtime: bool = True,
    is_cache: bool = False,
    warning: str | list[str] | None = None,
    source_name: str | None = None,
    fetched_at: datetime | None = None,
    updated_at: datetime | None = None,
    confidence: float | None = None,
    message: str = "OK",
    meta: dict | None = None,
) -> dict:
    warning_items = warning if isinstance(warning, list) else [warning]
    clean_warning = " | ".join(dedupe_messages(warning_items))
    payload = {
        "success": True,
        "data": data,
        "source": source,
        "source_name": source_name or source,
        "is_realtime": bool(is_realtime),
        "is_cache": bool(is_cache),
        "is_mock": False,
        "cache_status": normalize_cache_status("live" if is_realtime else "fresh_cache"),
        "warning": clean_warning or None,
        "error": None,
        "message": message,
        "fetched_at": fetched_at or updated_at or datetime.now(),
        "updated_at": updated_at or fetched_at or datetime.now(),
        "confidence": confidence,
    }
    payload["meta"] = {
        "source": payload["source"],
        "source_name": payload["source_name"],
        "is_realtime": payload["is_realtime"],
        "is_cache": payload["is_cache"],
        "is_mock": False,
        "cache_status": payload["cache_status"],
        "warning": payload["warning"],
        "error": None,
        "fetched_at": payload["fetched_at"],
        "updated_at": payload["updated_at"],
        "confidence": payload["confidence"],
        **(meta or {}),
    }
    return payload


def error_response(
    message: str = REALTIME_ERROR_MESSAGE,
    *,
    code: str = "REALTIME_API_FAILED",
    source: str = SOURCE_REALTIME,
    source_name: str | None = None,
    source_url: str | None = None,
) -> dict:
    now = datetime.now()
    return {
        "success": False,
        "data": None,
        "source": source,
        "source_name": source_name or source,
        "source_url": source_url,
        "is_realtime": False,
        "is_cache": False,
        "is_mock": False,
        "cache_status": "miss",
        "warning": None,
        "error": {
            "code": code,
            "message": message or REALTIME_ERROR_MESSAGE,
        },
        "message": message or REALTIME_ERROR_MESSAGE,
        "fetched_at": now,
        "last_updated": now,
        "updated_at": now,
        "data_age_minutes": None,
        "meta": {
            "source": source,
            "source_name": source_name or source,
            "source_url": source_url,
            "is_realtime": False,
            "is_cache": False,
            "is_mock": False,
            "cache_status": "miss",
            "warning": None,
            "error": {
                "code": code,
                "message": message or REALTIME_ERROR_MESSAGE,
            },
            "fetched_at": now,
            "last_updated": now,
            "updated_at": now,
            "data_age_minutes": None,
        },
    }


def _is_realtime_only() -> bool:
    return bool(settings.USE_REALTIME_ONLY) and not bool(settings.ALLOW_MOCK_DATA or settings.ALLOW_SAMPLE_DATA)


def api_response(
    data: Any,
    *,
    source: str = "database",
    source_name: str | None = None,
    is_realtime: bool = False,
    is_mock: bool = False,
    cache_status: str = "from_db",
    last_updated: datetime | None = None,
    fetched_at: datetime | None = None,
    confidence: float | None = None,
    message: str = "OK",
    fallback_used: bool | None = None,
    timeout: bool | None = None,
    error: str | None = None,
) -> dict:
    if isinstance(data, dict) and data.get("_api_error"):
        return error_response(
            data.get("error_message") or REALTIME_ERROR_MESSAGE,
            code=data.get("error_code") or "REALTIME_API_FAILED",
            source=data.get("source") or SOURCE_REALTIME,
            source_name=data.get("source_name"),
            source_url=data.get("source_url"),
        )

    source_url = None
    if isinstance(data, dict):
        source = data.get("source") or source
        source_name = source_name or data.get("source_name") or data.get("source") or source
        source_url = data.get("source_url")
        last_updated = last_updated or data.get("last_updated") or data.get("updated_at") or data.get("created_at")
        fetched_at = fetched_at or data.get("fetched_at")
        confidence = confidence if confidence is not None else data.get("confidence")
        is_realtime = is_realtime or bool(data.get("is_realtime"))
        is_mock = is_mock or bool(data.get("is_mock"))
        cache_status = data.get("cache_status") or cache_status
        fallback_used = bool(data.get("fallback_used")) if fallback_used is None else fallback_used
        timeout = bool(data.get("timeout")) if timeout is None else timeout
        error = error or data.get("error")
        if _is_realtime_only() and str(data.get("status") or "").lower() in {"mock_sent", "mock", "failed"}:
            return error_response(
                data.get("error") or "Không thể lấy dữ liệu realtime. Vui lòng thử lại sau.",
                code="REALTIME_API_FAILED" if str(data.get("status") or "").lower() == "failed" else "MOCK_DATA_BLOCKED",
                source=SOURCE_REALTIME,
            )

    cache_status = normalize_cache_status(cache_status, default="fresh_cache")
    fetched_at = fetched_at or last_updated or datetime.now()
    updated_at = last_updated or fetched_at

    data_age_minutes = None
    try:
        fetched_dt = fetched_at if isinstance(fetched_at, datetime) else datetime.fromisoformat(str(fetched_at).replace("Z", "+00:00")).replace(tzinfo=None)
        data_age_minutes = max(int((datetime.now() - fetched_dt).total_seconds() // 60), 0)
    except Exception:
        data_age_minutes = None

    # Service nào tự tính tuổi thì giữ nguyên. Tính ở đây là đo LÚC TA GỌI API,
    # không phải lúc dữ liệu được ghi nhận — sinh ra phản hồi tự cãi nhau:
    # cache_status="miss" (giá đã 37 ngày) đi kèm data_age_minutes=2.
    if isinstance(data, dict) and isinstance(data.get("data_age_minutes"), (int, float)):
        data_age_minutes = int(data["data_age_minutes"])

    fallback_used = bool(fallback_used)
    timeout = bool(timeout)
    if is_mock and _is_realtime_only():
        return error_response(
            REALTIME_ERROR_MESSAGE,
            code="MOCK_DATA_BLOCKED",
            source=SOURCE_REALTIME,
        )

    normalized_source = _normalized_source(
        source,
        is_realtime=is_realtime,
        is_mock=is_mock,
        cache_status=cache_status,
    )
    is_cache = (not is_realtime) and not is_mock and (
        normalized_source in {SOURCE_CACHED, SOURCE_DATABASE}
        or (cache_status or "").lower() in {"fresh_cache", "stale_cache"}
    )
    if is_cache and (fallback_used or timeout or (cache_status or "").lower() in {"stale", "stale_cache"}):
        normalized_source = SOURCE_CACHED
    warning_items: list[str | None] = []
    if isinstance(data, dict):
        warning_items.extend([
            data.get("warning"),
            data.get("message") if fallback_used or timeout or (cache_status or "").lower() in {"stale", "stale_cache"} else None,
        ])
    if fallback_used or timeout or (cache_status or "").lower() in {"stale", "stale_cache"}:
        warning_items.append(CACHE_WARNING_MESSAGE)
    warning = " | ".join(dedupe_messages(warning_items)) or None

    response = dict(data) if isinstance(data, dict) else {}
    response.update({
        "success": True,
        "data": data,
        "source": normalized_source,
        "source_name": source_name or source,
        "source_url": source_url if isinstance(data, dict) else None,
        "is_realtime": bool(is_realtime),
        "is_cache": bool(is_cache),
        "is_mock": bool(is_mock),
        "cache_status": cache_status,
        "warning": warning,
        "error": None,
        "fetched_at": fetched_at,
        "last_updated": updated_at,
        "updated_at": updated_at,
        "data_age_minutes": data_age_minutes,
        "confidence": confidence,
        "message": message,
        "meta": {
            "source": normalized_source,
            "source_name": source_name or source,
            "source_url": source_url if isinstance(data, dict) else None,
            "is_realtime": is_realtime,
            "is_cache": is_cache,
            "is_mock": bool(is_mock),
            "warning": warning,
            "fallback_used": fallback_used,
            "timeout": timeout,
            "error": None,
            "cache_status": cache_status,
            "last_updated": updated_at,
            "fetched_at": fetched_at,
            "updated_at": updated_at,
            "data_age_minutes": data_age_minutes,
            "confidence": confidence,
        },
    })
    return response
