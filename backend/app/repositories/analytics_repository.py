"""
Analytical queries on MarketPrice / PriceHistory / WeatherData.

Public interface:
    get_price_trend(db, crop_name, region, days) -> dict
    get_monthly_price_by_region(db, crop_name, months) -> list[dict]
    get_weather_price_correlation(db, crop_name, region, days) -> dict
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import numpy as np
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models.price import PriceHistory
from app.models.weather import WeatherData
from app.repositories.common import ensure_crop, normalize_text

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Price trend
# ---------------------------------------------------------------------------

def get_price_trend(
    db: Session,
    crop_name: str,
    region: str,
    days: int = 30,
) -> dict:
    """
    Compute price trend for a crop+region over the last `days` days.

    Returns:
        direction   : "up" | "down" | "stable"
        change_pct  : week-over-week % change (last 7d avg vs prior 7d avg)
        avg_7d      : average price last 7 days
        avg_30d     : average price last `days` days
        data_points : number of daily records used
        series      : list of {date, avg_price} sorted ascending
    """
    start = date.today() - timedelta(days=days)
    try:
        crop = ensure_crop(db, crop_name)
    except Exception:
        return _empty_trend()

    target = normalize_text(region)
    rows = (
        db.query(PriceHistory)
        .filter(PriceHistory.CropID == crop.CropID, PriceHistory.RecordDate >= start)
        .order_by(PriceHistory.RecordDate)
        .all()
    )
    rows = [r for r in rows if normalize_text(r.Region) == target]

    if not rows:
        return _empty_trend()

    series = [{"date": r.RecordDate.isoformat(), "avg_price": r.AvgPrice} for r in rows]
    prices = [r.AvgPrice for r in rows]

    avg_30d = sum(prices) / len(prices)
    recent = [r.AvgPrice for r in rows if r.RecordDate >= date.today() - timedelta(days=7)]
    prior = [r.AvgPrice for r in rows if date.today() - timedelta(days=14) <= r.RecordDate < date.today() - timedelta(days=7)]

    avg_7d = sum(recent) / len(recent) if recent else avg_30d
    avg_prev_7d = sum(prior) / len(prior) if prior else avg_30d

    if avg_prev_7d:
        change_pct = round((avg_7d - avg_prev_7d) / avg_prev_7d * 100, 2)
    else:
        change_pct = 0.0

    if change_pct > 1.0:
        direction = "up"
    elif change_pct < -1.0:
        direction = "down"
    else:
        direction = "stable"

    return {
        "direction": direction,
        "change_pct": change_pct,
        "avg_7d": round(avg_7d, 0),
        "avg_30d": round(avg_30d, 0),
        "data_points": len(rows),
        "series": series,
    }


def _empty_trend() -> dict:
    return {
        "direction": "stable",
        "change_pct": 0.0,
        "avg_7d": None,
        "avg_30d": None,
        "data_points": 0,
        "series": [],
    }


# ---------------------------------------------------------------------------
# Region / month aggregation
# ---------------------------------------------------------------------------

def get_monthly_price_by_region(
    db: Session,
    crop_name: str,
    months: int = 6,
) -> list[dict]:
    """
    Aggregate PriceHistory by region × month for the last `months` months.

    Returns list of:
        { region, year, month, avg_price, min_price, max_price, data_points }
    sorted by region, year, month.
    """
    start = date.today().replace(day=1) - timedelta(days=months * 31)
    try:
        crop = ensure_crop(db, crop_name)
    except Exception:
        return []

    year_col = extract("year", PriceHistory.RecordDate).label("year")
    month_col = extract("month", PriceHistory.RecordDate).label("month")

    rows = (
        db.query(
            PriceHistory.Region,
            year_col,
            month_col,
            func.avg(PriceHistory.AvgPrice).label("avg_price"),
            func.min(PriceHistory.MinPrice).label("min_price"),
            func.max(PriceHistory.MaxPrice).label("max_price"),
            func.count(PriceHistory.HistoryID).label("data_points"),
        )
        .filter(PriceHistory.CropID == crop.CropID, PriceHistory.RecordDate >= start)
        .group_by(PriceHistory.Region, year_col, month_col)
        .order_by(PriceHistory.Region, year_col, month_col)
        .all()
    )

    return [
        {
            "region": r.Region,
            "year": int(r.year),
            "month": int(r.month),
            "avg_price": round(float(r.avg_price), 0) if r.avg_price else None,
            "min_price": round(float(r.min_price), 0) if r.min_price else None,
            "max_price": round(float(r.max_price), 0) if r.max_price else None,
            "data_points": int(r.data_points),
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Weather–price correlation
# ---------------------------------------------------------------------------

def get_weather_price_correlation(
    db: Session,
    crop_name: str,
    region: str,
    days: int = 90,
) -> dict:
    """
    Pearson correlation between weather variables and daily average price.

    Joins PriceHistory with WeatherData on (Region, RecordDate).
    Returns correlation coefficients for: rainfall, temp_max, humidity.

    Result keys:
        rainfall_r    : float | None
        temp_max_r    : float | None
        humidity_r    : float | None
        data_points   : int
        interpretation: short human-readable summary
    """
    start = date.today() - timedelta(days=days)
    try:
        crop = ensure_crop(db, crop_name)
    except Exception:
        return _empty_corr()

    target = normalize_text(region)

    price_rows = (
        db.query(PriceHistory)
        .filter(PriceHistory.CropID == crop.CropID, PriceHistory.RecordDate >= start)
        .all()
    )
    price_rows = [r for r in price_rows if normalize_text(r.Region) == target]

    if len(price_rows) < 5:
        return _empty_corr()

    price_by_date = {r.RecordDate: r.AvgPrice for r in price_rows}

    weather_rows = (
        db.query(WeatherData)
        .filter(WeatherData.Region == region, WeatherData.RecordDate >= start)
        .all()
    )
    # fuzzy region match for weather too
    weather_rows = [r for r in weather_rows if normalize_text(r.Region) == target]
    weather_by_date = {r.RecordDate: r for r in weather_rows}

    # Keep only dates present in both datasets
    common_dates = sorted(set(price_by_date) & set(weather_by_date))
    if len(common_dates) < 5:
        return _empty_corr()

    prices = np.array([price_by_date[d] for d in common_dates], dtype=float)
    rainfall = np.array([weather_by_date[d].Rainfall or 0.0 for d in common_dates], dtype=float)
    temp_max = np.array([weather_by_date[d].TempMax or 0.0 for d in common_dates], dtype=float)
    humidity = np.array([weather_by_date[d].Humidity or 0.0 for d in common_dates], dtype=float)

    def _pearson(x: np.ndarray, y: np.ndarray) -> float | None:
        if x.std() == 0 or y.std() == 0:
            return None
        return round(float(np.corrcoef(x, y)[0, 1]), 3)

    rainfall_r = _pearson(rainfall, prices)
    temp_max_r = _pearson(temp_max, prices)
    humidity_r = _pearson(humidity, prices)

    interpretation = _interpret_correlations(rainfall_r, temp_max_r, humidity_r)

    return {
        "rainfall_r": rainfall_r,
        "temp_max_r": temp_max_r,
        "humidity_r": humidity_r,
        "data_points": len(common_dates),
        "interpretation": interpretation,
    }


def _empty_corr() -> dict:
    return {
        "rainfall_r": None,
        "temp_max_r": None,
        "humidity_r": None,
        "data_points": 0,
        "interpretation": "Không đủ dữ liệu để phân tích tương quan.",
    }


def _interpret_correlations(
    rainfall_r: float | None,
    temp_max_r: float | None,
    humidity_r: float | None,
) -> str:
    parts: list[str] = []
    if rainfall_r is not None and abs(rainfall_r) >= 0.3:
        direction = "tăng" if rainfall_r > 0 else "giảm"
        strength = "mạnh" if abs(rainfall_r) >= 0.6 else "nhẹ"
        parts.append(f"lượng mưa tương quan {strength} với giá ({direction}, r={rainfall_r})")
    if temp_max_r is not None and abs(temp_max_r) >= 0.3:
        direction = "tăng" if temp_max_r > 0 else "giảm"
        strength = "mạnh" if abs(temp_max_r) >= 0.6 else "nhẹ"
        parts.append(f"nhiệt độ cao nhất tương quan {strength} với giá ({direction}, r={temp_max_r})")
    if humidity_r is not None and abs(humidity_r) >= 0.3:
        direction = "tăng" if humidity_r > 0 else "giảm"
        strength = "mạnh" if abs(humidity_r) >= 0.6 else "nhẹ"
        parts.append(f"độ ẩm tương quan {strength} với giá ({direction}, r={humidity_r})")
    if not parts:
        return "Không phát hiện tương quan đáng kể giữa thời tiết và giá."
    return "Khi " + "; ".join(parts) + "."
