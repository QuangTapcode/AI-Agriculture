"""
TDD: cache thiếu ngày không được cắt ngắn dự báo.

Bug: `get_forecast(days=7)` chỉ kiểm tra cache có "fresh/stale" hay không, mà
không kiểm tra cache có ĐỦ 7 ngày. Trong luồng agriculture, get_current_weather
ghi trước 1 dòng cho hôm nay => get_forecast thấy 1 dòng fresh => trả 1 ngày,
và người dùng nhận "dự báo 7 ngày" chỉ có đúng hôm nay.
"""
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

from app.core.database import SessionLocal
from app.repositories.weather_repository import upsert_weather_cache
from app.services.weather_service import WeatherService, _normalize_region

REGION = "Bac Ninh Test"


def _live_days(n: int) -> list[dict]:
    """Payload giống Open-Meteo trả về n ngày."""
    today = date.today()
    return [
        {
            "date": (today + timedelta(days=i)).isoformat(),
            "temp_max": 30.0 + i,
            "temp_min": 24.0,
            "rainfall": 0.0,
            "humidity": 75.0,
        }
        for i in range(n)
    ]


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def test_partial_cache_still_returns_full_forecast(db):
    """Cache chỉ có hôm nay => phải fetch bù cho đủ 7 ngày, không trả 1."""
    norm = _normalize_region(REGION)
    upsert_weather_cache(
        db,
        region=norm,
        record_date=date.today(),
        temp_min=24.0,
        temp_max=31.0,
        rainfall=0.0,
        humidity=80.0,
        condition="clear",
        source_updated_at=datetime.now(),
        fetched_at=datetime.now(),
    )

    with patch(
        "app.services.weather_service._weather_client.get_forecast",
        return_value=_live_days(7),
    ):
        result = WeatherService().get_forecast(db, REGION, days=7)

    assert len(result) == 7, f"Cache 1 ngày đã cắt ngắn dự báo còn {len(result)} ngày"
