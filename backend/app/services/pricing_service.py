"""
Pricing Service
- Chuẩn hoá luồng giá hiện tại, lịch sử, dự báo, so sánh vùng miền và phân tích thị trường.
- Mọi điểm gọi nên đi qua service này thay vì tự mock rải rác ở controller/frontend.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import json
from typing import Any
from unicodedata import normalize as unicode_normalize
import unicodedata

from datetime import date as date_type

from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.price import MarketPrice
from app.repositories.common import ensure_crop, normalize_text, to_db_grade
from app.repositories.price_repository import (
    create_pricing_request,
    get_latest_prices_by_crop,
    get_price_history,
    get_recent_market_prices,
)
from app.schemas.price_schema import PricingSuggestRequest
from app.services.price_aggregator_service import price_aggregator_service
from app.core.real_data import OFFICIAL_AGRI_SOURCE_NAME, OFFICIAL_PRICE_URL, cache_status_for


def _to_public_cache_status(internal_status: str | None) -> str:
    """Chuyển đổi cache_status nội bộ sang giá trị public API theo spec.

    Public API chỉ dùng: "hit", "miss", "stale_cache"
    - "hit"         : dữ liệu cache còn tươi (live / fresh_cache / from_db / computed)
    - "stale_cache" : dữ liệu cache cũ nhưng vẫn dùng được
    - "miss"        : không có dữ liệu cache
    """
    mapping = {
        "live": "hit",
        "realtime": "hit",
        "refreshed": "hit",
        "fresh_cache": "hit",
        "fresh": "hit",
        "from_db": "hit",
        "database": "hit",
        "computed": "hit",
        "cache": "hit",
        "hit": "hit",
        "stale_cache": "stale_cache",
        "stale": "stale_cache",
        "miss": "miss",
        "empty": "miss",
        "no_data": "miss",
        "error": "miss",
        "failed": "miss",
    }
    return mapping.get(str(internal_status or "").strip().lower(), "miss")


GRADE_MULTIPLIERS = {
    "grade_1": 1.0,
    "grade_2": 0.88,
    "grade_3": 0.76,
    "Loai 1": 1.0,
    "Loai 2": 0.88,
    "Loai 3": 0.76,
    "loai_1": 1.0,
    "loai_2": 0.88,
    "loai_3": 0.76,
    "Loại 1": 1.0,
    "Loại 2": 0.88,
    "Loại 3": 0.76,
}

KNOWN_CROP_KEYS = (
    "lua",
    "gao",
    "ngo",
    "ca chua",
    "dua chuot",
    "rau",
    "rau muong",
    "ca phe",
    "ho tieu",
    "tieu",
    "sau rieng",
    "xoai",
    "thanh long",
    "chuoi",
    "dua hau",
    "khoai lang",
    "khoai tay",
)

REGION_DISPLAY_ALIASES = {
    "ha noi": "Hà Nội",
    "hanoi": "Hà Nội",
    "hn": "Hà Nội",
    "tp hcm": "TP.HCM",
    "tphcm": "TP.HCM",
    "tp.hcm": "TP.HCM",
    "ho chi minh": "TP.HCM",
    "sai gon": "TP.HCM",
    "saigon": "TP.HCM",
    "hcm": "TP.HCM",
    "da nang": "Đà Nẵng",
    "danang": "Đà Nẵng",
    "dak lak": "Đắk Lắk",
    "daklak": "Đắk Lắk",
    "dak nong": "Đắk Nông",
    "daknong": "Đắk Nông",
    "lam dong": "Lâm Đồng",
    "lamdong": "Lâm Đồng",
    "can tho": "Cần Thơ",
    "cantho": "Cần Thơ",
    "dong nai": "Đồng Nai",
    "dongnai": "Đồng Nai",
    "gia lai": "Gia Lai",
    "gialai": "Gia Lai",
}


def quantity_discount(qty: float) -> float:
    if qty >= 1000:
        return 0.92
    if qty >= 500:
        return 0.95
    if qty >= 100:
        return 0.97
    return 1.0


class PricingService:
    """Service xử lý giá nông sản và phân tích thị trường.

    Anti-timeout & anti-mock:
    - Không sinh dữ liệu (không synthetic/mock) từ DB.
    - DB chỉ là cache dữ liệu thật đã crawl/API trước đó.
    """
    quality_multipliers = GRADE_MULTIPLIERS
    # Legacy callers use this for crop detection only. Values are deliberately
    # not prices so no synthetic/mock price can be generated from it.
    crop_base_prices = {crop: None for crop in KNOWN_CROP_KEYS}

    def get_current_price(
        self,
        db: Session,
        crop_name: str,
        region: str,
        quality_grade: str = "grade_1",
        include_weather: bool = True,
        force_refresh: bool = False,
    ) -> dict:
        selected_crop = self._clean_crop(crop_name)
        selected_region = self._clean_region(region)
        selected_grade = self._clean_grade(quality_grade)

        result = price_aggregator_service.get_best_current_price(
            db,
            selected_crop,
            selected_region,
            force_refresh=force_refresh,
        )

        # Anti-mock: nếu không có dữ liệu thật, aggregator phải trả _api_error => propagate trực tiếp.
        if result.get("_api_error"):
            return result

        raw_market_price = result.get("current_price")
        if raw_market_price is None:
            raw_market_price = result.get("price")
        if raw_market_price is None:
            raw_market_price = result.get("market_price")

        if raw_market_price is not None:
            try:
                raw_market_price = round(float(raw_market_price), 2)
            except (TypeError, ValueError):
                return {
                    "_api_error": True,
                    "error_code": "INVALID_PRICE_DATA",
                    "error_message": "Dữ liệu giá từ nguồn upstream không hợp lệ.",
                    "crop_name": crop_name.strip(),
                    "region": selected_region,
                    "is_mock": False,
                }
        multiplier = self.quality_multipliers.get(selected_grade, 1.0)
        adjusted_price = raw_market_price
        if raw_market_price is not None and multiplier != 1.0:
            adjusted_price = round(float(raw_market_price) * multiplier, 2)

        if raw_market_price is not None:
            result["base_market_price"] = raw_market_price
            result["official_price"] = raw_market_price
            result["current_price"] = adjusted_price
            result["market_price"] = adjusted_price
            result["price"] = adjusted_price

        result.update(
            {
                "crop_name": crop_name.strip(),
                "crop": crop_name.strip(),
                "region": selected_region,
                "quality_grade": selected_grade,
                "quality_multiplier": multiplier,
                # Aggregator đã tính tuổi từ NGÀY GIÁ. Tính lại theo fetched_at
                # là đo lúc ta gọi API — giá của tháng trước sẽ thành "2 phút".
                "data_age_minutes": result.get("data_age_minutes")
                if result.get("data_age_minutes") is not None
                else self._age_minutes(result.get("fetched_at") or result.get("last_updated")),
            }
        )

        if include_weather:
            # Weather adjustment là rule-based, không tạo dữ liệu giá mới.
            result.update(
                self._safe_weather_adjustment(
                    db,
                    selected_crop,
                    selected_region,
                    float(result.get("current_price") or 0),
                )
            )

        return result

    def refresh_current_price(self, db: Session, crop_name: str, region: str, quality_grade: str = "grade_1") -> dict:
        selected_crop = self._clean_crop(crop_name)
        selected_region = self._clean_region(region)
        selected_grade = self._clean_grade(quality_grade)

        refresh_result = price_aggregator_service.refresh_price_for_crop_region(db, selected_crop, selected_region)
        current = self.get_current_price(
            db,
            selected_crop,
            selected_region,
            selected_grade,
            include_weather=False,
            force_refresh=False,
        )
        current["refresh_result"] = refresh_result
        if refresh_result.get("records_fetched") and not current.get("is_mock"):
            current["source"] = "realtime"
            current["cache_status"] = "refreshed"
            current["is_realtime"] = True
        else:
            current["source"] = current.get("source") or ("database" if not current.get("is_mock") else "mock")
        current["source_type"] = current["source"]
        current["message"] = (
            "Đã làm mới giá từ nguồn thực tế"
            if refresh_result.get("status") == "success" and not current.get("is_mock")
            else "Chưa lấy được giá thực tế, đang hiển thị dữ liệu cache nếu có"
        )
        return current

    def suggest_price(self, db: Session, request: PricingSuggestRequest) -> dict:
        selected_grade = self._clean_grade(request.quality_grade)
        current = self.get_current_price(
            db,
            request.crop_name,
            request.region,
            selected_grade,
            include_weather=True,
        )
        if current.get("_api_error"):
            return current

        return self._build_suggest_price_result(db, current, request, selected_grade)

    def _build_suggest_price_result(
        self,
        db: Session,
        current: dict,
        request: PricingSuggestRequest,
        selected_grade: str,
    ) -> dict:
        base_market_price = current.get("base_market_price")
        if base_market_price is None:
            base_market_price = current.get("official_price")
        if base_market_price is None:
            raw_price = current.get("current_price") or current.get("price") or current.get("market_price")
            base_market_price = float(raw_price) if raw_price is not None else None

        if base_market_price is None:
            return {
                "_api_error": True,
                "error_code": "PRICE_UNAVAILABLE",
                "message": "Không có dữ liệu giá để tính toán. Vui lòng thử lại sau.",
                "crop_name": request.crop_name,
                "region": request.region,
                "is_mock": False,
            }

        base_market_price = float(base_market_price)
        discount = quantity_discount(request.quantity)
        multiplier = GRADE_MULTIPLIERS.get(selected_grade, 1.0)

        # get_current_price(...) đã áp quality multiplier vào current/current_price.
        # Ở đây chỉ tái sử dụng giá đã scale để tránh nhân hệ số chất lượng 2 lần.
        grade_adjusted_price = current.get("current_price")
        if grade_adjusted_price is None:
            grade_adjusted_price = round(base_market_price * multiplier, 2)
        else:
            grade_adjusted_price = round(float(grade_adjusted_price), 2)

        suggested_price = round(grade_adjusted_price * discount, 2)
        min_price = round(suggested_price * 0.92, 2)
        max_price = round(suggested_price * 1.08, 2)

        weather_factor = float(current.get("weather_factor", 1.0))
        weather_suggested = round(suggested_price * weather_factor, 2)
        weather_min = round(min_price * weather_factor, 2)
        weather_max = round(max_price * weather_factor, 2)

        nearby_prices = self._nearby_region_prices(db, request.crop_name, request.region)

        weather_summary = current.get("weather_summary", "")
        weather_explanation = current.get("weather_explanation", "")
        weather_impact = {
            "factor": weather_factor,
            "description": weather_explanation or weather_summary or "Không có dữ liệu thời tiết",
        }

        news_impact = {"level": "neutral", "description": "Chưa có tin tức thị trường mới đủ liên quan."}
        try:
            from app.services.market_news_service import market_news_service

            news_bundle = market_news_service.get_market_news(
                db,
                crop=self._clean_crop(request.crop_name),
                region=self._clean_region(request.region),
                limit=5,
            )
            related_news = news_bundle.get("news", [])
            if related_news:
                impact_summary = self._news_impact_summary(related_news)
                news_impact = {
                    "level": impact_summary.get("level", "neutral"),
                    "description": impact_summary.get("summary", "Tin tức liên quan đang ở mức trung tính."),
                }
        except Exception:
            pass

        retail_price_diff = None
        retail_ref = current.get("retail_reference") or current.get("retail_price")
        if retail_ref and isinstance(retail_ref, (int, float)):
            retail_price_diff = round(float(retail_ref) - weather_suggested, 2)

        suggested_price_range = {"min": weather_min, "max": weather_max}

        official_price_source = {
            "name": current.get("source_name") or OFFICIAL_AGRI_SOURCE_NAME,
            "url": current.get("source_url") or OFFICIAL_PRICE_URL,
        }

        create_pricing_request(
            db,
            crop_name=request.crop_name,
            region=self._clean_region(request.region),
            quantity=request.quantity,
            quality_grade=selected_grade,
            suggested_price=weather_suggested if self._has_positive_price(weather_suggested) else None,
            min_price=weather_min if self._has_positive_price(weather_min) else None,
            max_price=weather_max if self._has_positive_price(weather_max) else None,
        )

        return {
            "crop_name": request.crop_name,
            "region": self._clean_region(request.region),
            "quantity": request.quantity,
            "quality_grade": selected_grade,
            "min_price": min_price,
            "suggested_price": suggested_price,
            "max_price": max_price,
            "weather_min_price": weather_min,
            "weather_suggested_price": weather_suggested,
            "weather_max_price": weather_max,
            "weather_factor": weather_factor,
            "weather_summary": weather_summary,
            "weather_explanation": weather_explanation,
            "price_change_pct": current.get("price_change_percent", 0.0),
            "unit": "VNĐ/kg",
            "nearby_region_prices": nearby_prices,
            "official_price": round(base_market_price, 2),
            "quality_coefficient": multiplier,
            "quality_adjusted_price": grade_adjusted_price,
            "weather_impact": weather_impact,
            "news_impact": news_impact,
            "retail_price_diff": retail_price_diff,
            "suggested_price_range": suggested_price_range,
            "official_price_source": official_price_source,
            "source": current.get("source", "database"),
            "source_name": current.get("source_name"),
            "source_url": current.get("source_url") or OFFICIAL_PRICE_URL,
            "last_updated": current.get("last_updated"),
            "is_mock": current.get("is_mock", False),
            "cache_status": _to_public_cache_status(current.get("cache_status", "from_db")),
            # Mang theo tuổi thật, nếu không lớp bọc api_response sẽ tự tính
            # theo lúc gọi API và mâu thuẫn với cache_status.
            "data_age_minutes": current.get("data_age_minutes"),
            "confidence": current.get("confidence", 0.7),
            "message": "Giá đề xuất đã được điều chỉnh theo dữ liệu giá hiện tại và thời tiết.",
        }

    def forecast_price(
        self,
        db_or_crop_name: Session | str,
        crop_name: str | None = None,
        region: str | None = None,
        days: int = 7,
    ) -> dict:
        """Backward-compatible wrapper.

        Hỗ trợ cả 2 cách gọi cũ/mới:
        - forecast_price(db, crop_name, region, days)
        - forecast_price(crop_name, region, days) -> trả lỗi rõ vì thiếu DB session
        """
        if isinstance(db_or_crop_name, Session):
            return self.forecast_price_with_db(db_or_crop_name, crop_name or "", region or "", days)

        # old signature: forecast_price(crop_name, region, days)
        inferred_crop_name = db_or_crop_name
        inferred_region = crop_name or ""
        inferred_days = region if isinstance(region, int) else days
        return {
            "_api_error": True,
            "error_code": "INSUFFICIENT_PRICE_HISTORY",
            "error_message": (
                "Không thể dự báo giá: cần ít nhất 7 ngày lịch sử giá thật trong DB. "
                "Vui lòng gọi forecast_price(db, crop_name, region, days) hoặc forecast_price_with_db(...)."
            ),
            "crop_name": inferred_crop_name,
            "region": inferred_region,
            "forecast_data": [],
            "recommendation": "Chưa đủ dữ liệu hoặc thiếu DB session để dự báo.",
            "source": "realtime_api",
            "source_name": OFFICIAL_AGRI_SOURCE_NAME,
            "source_url": OFFICIAL_PRICE_URL,
            "is_realtime": False,
            "is_mock": False,
            "cache_status": "miss",
            "fetched_at": None,
            "last_updated": datetime.now().isoformat(),
            "data_age_minutes": None,
            "days": inferred_days,
        }

    def forecast_price_with_db(self, db: Session, crop_name: str, region: str, days: int = 7) -> dict:
        """Dự báo giá dựa trên lịch sử giá thật từ DB.

        Yêu cầu ít nhất 7 ngày lịch sử giá thật.
        Nếu không đủ dữ liệu, trả lỗi rõ ràng với error_code="INSUFFICIENT_PRICE_HISTORY".
        Không bao giờ tự bịa giá.
        """
        MIN_HISTORY_DAYS = 7
        selected_crop = self._clean_crop(crop_name)
        selected_region = self._clean_region(region)

        history = self.get_price_history(db, selected_crop, selected_region, max(days, MIN_HISTORY_DAYS) + 7)
        real_history = [item for item in history if not item.get("is_mock")]

        if len(real_history) < MIN_HISTORY_DAYS:
            return {
                "_api_error": True,
                "error_code": "INSUFFICIENT_PRICE_HISTORY",
                "error_message": (
                    f"Không đủ dữ liệu lịch sử giá để dự báo. "
                    f"Cần ít nhất {MIN_HISTORY_DAYS} ngày dữ liệu thật, "
                    f"hiện có {len(real_history)} ngày."
                ),
                "crop_name": crop_name,
                "region": selected_region,
                "required_days": MIN_HISTORY_DAYS,
                "available_days": len(real_history),
                "forecast_data": [],
                "recommendation": "Chưa đủ dữ liệu lịch sử giá để đưa ra khuyến nghị dự báo.",
                "source": "database",
                "source_name": OFFICIAL_AGRI_SOURCE_NAME,
                "source_url": OFFICIAL_PRICE_URL,
                "is_realtime": False,
                "is_mock": False,
                "cache_status": "miss",
                "fetched_at": None,
                "last_updated": datetime.now().isoformat(),
                "data_age_minutes": None,
            }

        recent = real_history[-MIN_HISTORY_DAYS:]
        prices = [float(item.get("avg_price") or 0) for item in recent]

        diffs = []
        for i in range(1, len(prices)):
            prev = prices[i - 1]
            cur = prices[i]
            if prev != 0:
                diffs.append((cur - prev) / prev)

        last_diff = diffs[-1] if diffs else 0.0
        avg_diff = sum(diffs[-3:]) / max(len(diffs[-3:]), 1) if diffs else 0.0

        if len(prices) >= 2 and prices[0]:
            overall_pct = (prices[-1] - prices[0]) / prices[0] * 100
        else:
            overall_pct = 0.0

        if overall_pct > 1:
            trend = "increasing"
            growth_rate = (avg_diff + last_diff) / 2
        elif overall_pct < -1:
            trend = "decreasing"
            growth_rate = (avg_diff + last_diff) / 2
        else:
            trend = "stable"
            growth_rate = avg_diff / 4 if avg_diff else 0.0

        last_price = prices[-1]
        forecast_data = []
        for offset in range(1, days + 1):
            est = float(last_price) * ((1 + growth_rate) ** offset)
            est = round(est, 2)
            conf = "high" if offset <= 3 else "medium"
            lower = round(est * 0.92, 2)
            upper = round(est * 1.08, 2)
            forecast_data.append({
                "date": (datetime.now() + timedelta(days=offset)).strftime("%Y-%m-%d"),
                "estimated_price": est,
                "predicted_price": est,
                "forecast_price": est,
                "min_price": lower,
                "max_price": upper,
                "confidence_lower": lower,
                "confidence_upper": upper,
                "confidence": conf,
                "trend": "up" if growth_rate >= 0 else "down",
                "reason_codes": ["price_history_db", "deterministic_estimation"],
                "source": "estimated_from_history",
                "source_name": "PriceHistory DB (estimated)",
                "is_mock": False,
                "estimated": True,
            })

        recommendation_map = {
            "increasing": "Xu hướng giá đang tăng, có thể cân nhắc chờ thêm nếu bảo quản tốt.",
            "decreasing": "Xu hướng giá đang giảm, nên ưu tiên theo dõi sát và cân nhắc bán sớm.",
            "stable": "Giá dự báo tương đối ổn định, có thể bán theo kế hoạch bình thường.",
        }

        return {
            "crop_name": crop_name,
            "region": selected_region,
            "days": days,
            "trend": trend,
            "growth_rate_per_day": round(growth_rate * 100, 4),
            "base_price": last_price,
            "forecast_data": forecast_data,
            "forecast_price_7d": forecast_data[min(6, len(forecast_data) - 1)]["estimated_price"] if forecast_data else None,
            "history_points_used": len(recent),
            "recommendation": recommendation_map.get(trend, recommendation_map["stable"]),
            "source": "database",
            "source_name": OFFICIAL_AGRI_SOURCE_NAME,
            "source_url": OFFICIAL_PRICE_URL,
            "is_realtime": False,
            "is_mock": False,
            "cache_status": "from_db",
            "fetched_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "data_age_minutes": 0,
            "confidence": 0.68,
            "forecast_status": "estimated_from_real_history",
        }

    def get_price_history(self, db: Session, crop_name: str, region: str, days: int = 30) -> list[dict]:
        history = get_price_history(db, crop_name, region, days)
        if history:
            return [
                {
                    "date": item.record_date.isoformat(),
                    "avg_price": float(item.avg_price),
                    "min_price": float(item.min_price or item.avg_price),
                    "max_price": float(item.max_price or item.avg_price),
                    "source": "database",
                    "source_name": "PriceHistory DB",
                    "fetched_at": datetime.now().isoformat(),
                    "updated_at": item.record_date.isoformat(),
                    "confidence": 0.7,
                    "is_mock": False,
                }
                for item in history
            ]
        return self._market_price_history(db, crop_name, region, days)

    def _market_price_history(self, db: Session, crop_name: str, region: str, days: int) -> list[dict]:
        """Aggregate MarketPrice rows by PriceDate as fallback when PriceHistory is empty."""
        try:
            start = date_type.today() - timedelta(days=days)
            crop = ensure_crop(db, crop_name)
            target_region = normalize_text(self._clean_region(region))
            rows = (
                db.query(MarketPrice)
                .filter(
                    MarketPrice.CropID == crop.CropID,
                    MarketPrice.PriceDate >= start,
                    MarketPrice.IsMock == False,  # noqa: E712
                )
                .order_by(MarketPrice.PriceDate)
                .all()
            )
            # Filter by region (exact match first, then all)
            region_rows = [r for r in rows if normalize_text(r.Region) == target_region]
            if not region_rows:
                region_rows = rows  # fallback: any region

            # Group by PriceDate
            by_date: dict[date_type, list[float]] = {}
            for row in region_rows:
                key = row.PriceDate
                if key is None:
                    continue
                by_date.setdefault(key, []).append(float(row.PricePerKg))

            result = []
            for d in sorted(by_date):
                prices = by_date[d]
                avg = sum(prices) / len(prices)
                result.append({
                    "date": d.isoformat(),
                    "avg_price": round(avg, 2),
                    "min_price": round(min(prices), 2),
                    "max_price": round(max(prices), 2),
                    "source": "database",
                    "source_name": "MarketPrices DB",
                    "fetched_at": datetime.now().isoformat(),
                    "updated_at": d.isoformat(),
                    "confidence": 0.65,
                    "is_mock": False,
                })
            return result
        except Exception:
            db.rollback()
            return []

    def analyze_price_trend(self, db: Session, crop_name: str, region: str) -> str:
        recent_prices = get_recent_market_prices(db, crop_name, region)
        if len(recent_prices) >= 2:
            prices = [float(item.price) for item in reversed(recent_prices)]
        else:
            prices = self._get_recent_prices_from_db(db, crop_name, region)

        if len(prices) < 2:
            return "stable"

        mid = max(len(prices) // 2, 1)
        first_avg = sum(prices[:mid]) / mid
        second_avg = sum(prices[mid:]) / max(len(prices) - mid, 1)
        change = ((second_avg - first_avg) / first_avg) * 100

        if change > 5:
            return "increasing"
        if change < -5:
            return "decreasing"
        return "stable"

    # ─── Seasonality factors cho các nhóm cây trồng Việt Nam ────────────────
    _SEASONALITY: dict[str, dict[int, float]] = {
        "lua":       {1: 1.04, 2: 1.06, 3: 1.03, 4: 1.00, 5: 0.98, 6: 0.97,
                      7: 0.97, 8: 0.99, 9: 1.01, 10: 1.05, 11: 1.04, 12: 1.02},
        "gao":       {1: 1.04, 2: 1.05, 3: 1.03, 4: 1.00, 5: 0.98, 6: 0.97,
                      7: 0.97, 8: 0.99, 9: 1.01, 10: 1.04, 11: 1.04, 12: 1.02},
        "ca phe":    {1: 0.97, 2: 0.97, 3: 0.99, 4: 1.01, 5: 1.02, 6: 1.02,
                      7: 1.02, 8: 1.01, 9: 1.00, 10: 0.99, 11: 0.96, 12: 0.97},
        "ho tieu":   {1: 1.02, 2: 1.04, 3: 1.05, 4: 1.04, 5: 1.02, 6: 1.00,
                      7: 0.99, 8: 0.98, 9: 0.98, 10: 0.99, 11: 1.00, 12: 1.01},
        "sau rieng": {1: 0.96, 2: 0.97, 3: 0.99, 4: 1.01, 5: 1.03, 6: 1.06,
                      7: 1.08, 8: 1.07, 9: 1.04, 10: 1.02, 11: 0.99, 12: 0.97},
        "xoai":      {1: 1.00, 2: 1.02, 3: 1.05, 4: 1.06, 5: 1.04, 6: 1.02,
                      7: 1.00, 8: 0.99, 9: 0.98, 10: 0.98, 11: 0.99, 12: 1.00},
        "thanh long":{1: 0.97, 2: 0.98, 3: 1.00, 4: 1.02, 5: 1.05, 6: 1.06,
                      7: 1.06, 8: 1.05, 9: 1.04, 10: 1.03, 11: 1.01, 12: 0.98},
    }
    _DEFAULT_SEASONALITY = {m: 1.0 for m in range(1, 13)}

    def _seasonality_factor(self, crop_name: str, month: int) -> float:
        table = self._SEASONALITY.get(self._clean_crop(crop_name), self._DEFAULT_SEASONALITY)
        return table.get(month, 1.0)

    @staticmethod
    def _news_sentiment_factor(news_items: list[dict]) -> tuple[float, str]:
        """Tính hệ số tác động từ sentiment tin tức → (factor, label)."""
        if not news_items:
            return 1.0, "Chưa có dữ liệu tin tức."
        pos = sum(1 for n in news_items if (n.get("sentiment") or "").lower() == "positive")
        neg = sum(1 for n in news_items if (n.get("sentiment") or "").lower() == "negative")
        total = len(news_items)
        net = (pos - neg) / total
        factor = round(1.0 + net * 0.03, 4)
        if net > 0.2:
            label = f"Tin tức tích cực ({pos}/{total} bài): kỳ vọng giá nhích tăng."
        elif net < -0.2:
            label = f"Tin tức tiêu cực ({neg}/{total} bài): rủi ro giá giảm, nên bán sớm."
        else:
            label = "Tin tức thị trường trung lập, biến động ít."
        return factor, label

    def build_pricing_engine(
        self,
        db: Session,
        *,
        crop_name: str,
        region: str,
        quantity: float = 1,
        quality_grade: str = "grade_1",
        days: int = 7,
    ) -> dict:
        from datetime import date as _date
        selected_grade = self._clean_grade(quality_grade)
        current = self.get_current_price(db, crop_name, region, selected_grade)
        if current.get("_api_error"):
            return current
        forecast = self.forecast_price_with_db(db, crop_name, region, days)
        if forecast.get("_api_error"):
            return forecast
        suggestion = self._build_suggest_price_result(
            db,
            current,
            PricingSuggestRequest(
                crop_name=crop_name,
                region=region,
                quantity=max(float(quantity or 1), 1),
                quality_grade=selected_grade,
            ),
            selected_grade,
        )
        if suggestion.get("_api_error"):
            return suggestion
        history = self.get_price_history(db, crop_name, region, 30)

        market_price = float(current["current_price"])
        source_label = current.get("source_name") or "hệ thống"
        trend = current.get("price_trend") or forecast.get("trend") or "stable"
        trend_label = {"stable": "ổn định", "increasing": "tăng", "decreasing": "giảm"}.get(trend, trend)

        month = _date.today().month
        seasonality = self._seasonality_factor(crop_name, month)
        season_label = (
            f"Tháng {month} là cao điểm mùa vụ cho {crop_name}, kỳ vọng giá cao hơn."
            if seasonality > 1.02
            else f"Tháng {month} ngoài mùa vụ cao điểm, giá có thể thấp hơn."
            if seasonality < 0.98
            else f"Tháng {month} ở mức trung bình theo mùa vụ."
        )

        try:
            from app.services.market_news_service import market_news_service as _news_svc
            news_bundle = _news_svc.get_market_news(db, crop=self._clean_crop(crop_name), region=region, limit=10)
            news_items = news_bundle.get("news", [])
        except Exception:
            news_items = []
        news_factor, news_label = self._news_sentiment_factor(news_items)

        best_platform_price = None
        best_platform_source = None
        try:
            from app.integrations.tavily_client import search_prices as _tavily_px
            from app.services.price_aggregator_service import PriceAggregatorService
            raw = _tavily_px(max_queries=2)
            candidates = PriceAggregatorService._tavily_raw_to_results(raw, crop_name, region)
            if candidates:
                best = max(candidates, key=lambda r: r.price)
                best_platform_price = best.price
                best_platform_source = best.source_name or "sàn nông sản trực tuyến"
        except Exception:
            pass

        weather_factor = float(suggestion.get("weather_factor", 1.0))

        combined_factor = round(seasonality * news_factor * weather_factor, 4)
        suggested_price = float(
            suggestion.get("weather_suggested_price")
            or suggestion.get("suggested_price")
            or market_price
        )
        ai_suggested_price = round(suggested_price * max(seasonality * news_factor, 0), 2)
        forecast_price_7d_raw = float(forecast.get("forecast_price_7d") or market_price)
        ai_forecast_7d = round(forecast_price_7d_raw * seasonality * news_factor, 2)

        reasons = [
            f"Giá thị trường từ {source_label}: {market_price:,.0f} VNĐ/kg",
            f"Xu hướng {trend_label} dựa trên tín hiệu lịch sử giá gần đây.",
            season_label,
            news_label,
        ]
        if (
            best_platform_price
            and market_price > 0
            and abs(best_platform_price - market_price) / market_price > 0.05
        ):
            reasons.append(
                f"Sàn nông sản trực tuyến ({best_platform_source}) có giá {best_platform_price:,.0f} VNĐ/kg"
                f" — chênh lệch {(best_platform_price - market_price) / market_price * 100:+.1f}%."
            )
        if suggestion.get("weather_summary"):
            reasons.append(suggestion["weather_summary"])
        reasons.append(
            f"Hệ số tổng hợp (mùa vụ × tin tức × thời tiết) = {combined_factor:.3f}."
        )

        recommendation_map = {
            "stable":     "Thị trường ổn định: nên bán theo từng đợt nhỏ, bật cảnh báo giá để không bỏ lỡ đỉnh.",
            "increasing": "Xu hướng tăng: có thể giữ lại một phần hàng 5-7 ngày nếu bảo quản được.",
            "decreasing": "Xu hướng giảm: nên ưu tiên bán sớm hoặc chốt cam kết giá với người mua ngay hôm nay.",
        }
        recommendation = recommendation_map.get(trend, recommendation_map["stable"])
        if seasonality > 1.02:
            recommendation += " Đang vào mùa cao điểm — có lợi cho bên bán."
        elif seasonality < 0.98:
            recommendation += " Ngoài mùa vụ chính — nên đa dạng kênh tiêu thụ."

        is_mock = bool(current.get("is_mock")) or bool(forecast.get("is_mock"))
        confidence = min(0.88, 0.62 + (0.08 if not is_mock else 0) + (0.08 if news_items else 0) + (0.05 if best_platform_price else 0))

        return {
            "crop": crop_name,
            "crop_name": crop_name,
            "region": self._clean_region(region),
            "market_price": market_price,
            "current_price": market_price,
            "forecast_price_7d": ai_forecast_7d,
            "suggested_price": ai_suggested_price,
            "base_suggested_price": suggested_price,
            "trend": trend,
            "confidence": round(confidence, 2),
            "factors": {
                "seasonality": seasonality,
                "news_sentiment": news_factor,
                "weather": weather_factor,
                "combined": combined_factor,
                "best_platform_price": best_platform_price,
                "best_platform_source": best_platform_source,
            },
            "reasons": reasons,
            "recommendation": recommendation,
            "history": history,
            "forecast": forecast.get("forecast_data", []),
            "nearby_region_prices": suggestion.get("nearby_region_prices", []),
            "source": "ai_generated" if not is_mock else "mock",
            "source_name": "AI Pricing Engine (thitruongnongsan + Tavily + weather + seasonality)",
            "is_mock": is_mock,
            "cache_status": current.get("cache_status", "computed"),
            "last_updated": datetime.now().isoformat(),
        }

    def compare_regions(self, db: Session, crop_name: str, region: str = "Ha Noi") -> dict:
        selected_crop = self._clean_crop(crop_name)
        selected_region = self._clean_region(region)
        base_current = self.get_current_price(db, selected_crop, selected_region, include_weather=False)
        if base_current.get("_api_error"):
            return base_current
        # Task 1.3: bỏ qua nếu dữ liệu base là mock
        if base_current.get("is_mock"):
            return {
                "_api_error": True,
                "error_code": "REALTIME_PRICE_FAILED",
                "error_message": "Không có dữ liệu thật cho vùng cơ sở. Vui lòng thử lại sau.",
                "crop_name": crop_name,
                "base_region": selected_region,
                "regions": [],
                "source": "realtime_api",
                "is_mock": False,
                "cache_status": "miss",
            }
        base_price = float(base_current.get("current_price") or 0)

        regions = [
            selected_region,
            "Lâm Đồng",
            "Gia Lai",
            "Đắk Lắk",
            "Đồng Nai",
            "Cần Thơ",
        ]
        items = []
        for item_region in regions:
            current = self.get_current_price(db, selected_crop, item_region, include_weather=False)
            if current.get("_api_error"):
                continue
            # Task 1.3: bỏ qua vùng có is_mock=True
            if current.get("is_mock"):
                continue
            price = float(current.get("current_price") or 0)
            difference_percent = ((price - base_price) / base_price * 100) if base_price else 0
            items.append(
                {
                    "region": item_region,
                    "price": round(price, 2),
                    "difference_percent": round(difference_percent, 2),
                    "source": current.get("source", "database"),
                    "source_name": current.get("source_name") or OFFICIAL_AGRI_SOURCE_NAME,
                    "source_url": current.get("source_url") or OFFICIAL_PRICE_URL,
                    "last_updated": current.get("last_updated"),
                    "is_mock": False,
                    "confidence": current.get("confidence", 0.7),
                }
            )

        if not items:
            return {
                "_api_error": True,
                "error_code": "REALTIME_PRICE_FAILED",
                "error_message": "Không thể tải giá realtime. Vui lòng thử lại sau.",
                "crop_name": crop_name,
                "base_region": selected_region,
                "regions": [],
                "source": "realtime_api",
                "is_mock": False,
                "cache_status": "miss",
            }
        return {
            "crop_name": crop_name,
            "crop": crop_name,
            "base_region": selected_region,
            "regions": items,
            "best_region": max(items, key=lambda item: item.get("price", 0), default=None),
            "source": "cache",
            "source_name": "Pricing comparison service",
            "is_mock": False,
            "cache_status": "computed",
            "confidence": 0.7,
            "last_updated": datetime.now(),
        }

    def explain_pricing(self, db: Session, crop_name: str, region: str, quality_grade: str = "grade_1") -> dict:
        engine = self.build_pricing_engine(
            db,
            crop_name=crop_name,
            region=region,
            quality_grade=quality_grade,
            quantity=1,
            days=7,
        )
        return {
            **engine,
            "explanation": {
                "summary": engine["recommendation"],
                "factors": engine["reasons"],
                "confidence_note": "Độ tin cậy giảm khi dữ liệu nguồn thực tế chưa sẵn sàng và hệ thống phải dùng fallback.",
            },
        }

    def get_price_forecast(self, db: Session, crop_name: str, region: str, days: int = 7) -> dict:
        return self.forecast_price_with_db(db, crop_name, region, days)

    def get_price_comparison(self, db: Session, crop_name: str, regions: list[str]) -> dict:
        regions = regions or ["Ha Noi", "TP.HCM", "Da Nang", "Can Tho"]
        # So vung thuong 6+, moi vung co the cham mang -> noi duoi rat cham.
        # Chay song song, MOI LUONG MOT SESSION RIENG vi SQLAlchemy Session
        # khong thread-safe.
        def _gia_vung(region: str) -> dict:
            sess = SessionLocal()
            try:
                return self.get_current_price(sess, crop_name, region, include_weather=False)
            except Exception:
                return {"_api_error": True, "region": region}
            finally:
                sess.close()

        with ThreadPoolExecutor(max_workers=min(len(regions), 8)) as pool:
            items = list(pool.map(_gia_vung, regions))
        items = [item for item in items if not item.get("_api_error")]
        items = [item for item in items if not item.get("is_mock")]
        has_real_data = bool(items)
        if not has_real_data:
            return {
                "_api_error": True,
                "error_code": "REALTIME_API_FAILED",
                "error_message": "Không thể tải giá realtime. Vui lòng thử lại sau.",
                "crop_name": crop_name,
                "regions": [],
                "source": "realtime_api",
                "is_mock": False,
                "cache_status": "miss",
            }
        return {
            "crop_name": crop_name,
            "crop": crop_name,
            "regions": items,
            "best_region": max(items, key=lambda item: item.get("current_price", 0), default=None),
            "source": "cache",
            "source_name": "Pricing comparison service",
            "is_mock": False,
            "cache_status": "computed",
            "confidence": 0.7,
            "last_updated": datetime.now(),
        }

    def get_ai_price_recommendation(
        self,
        db: Session,
        crop_name: str,
        region: str,
        quality_grade: str | None = None,
        quantity: float | None = None,
    ) -> dict:
        return self.build_pricing_engine(
            db,
            crop_name=crop_name,
            region=region,
            quantity=quantity or 1,
            quality_grade=quality_grade or "grade_1",
            days=7,
        )

    def analyze_market(
        self,
        db: Session,
        *,
        crop_name: str,
        region: str,
        quantity: float | None = None,
        quality_grade: str | None = None,
    ) -> dict:
        selected_crop = self._clean_crop(crop_name)
        selected_region = self._clean_region(region)
        selected_grade = self._clean_grade(quality_grade or "grade_2")
        current = self.get_current_price(db, selected_crop, selected_region, selected_grade, include_weather=False)
        if current.get("_api_error"):
            return current
        history_30 = self.get_price_history(db, selected_crop, selected_region, 30)
        history_7 = self.get_price_history(db, selected_crop, selected_region, 7)
        comparison = self.compare_regions(db, selected_crop, selected_region)
        try:
            from app.services.market_news_service import market_news_service

            news_bundle = market_news_service.get_market_news(
                db,
                crop=selected_crop,
                region=selected_region,
                limit=5,
            )
            related_news = news_bundle.get("news", [])
        except Exception:
            news_bundle = {"source": "database", "source_name": "Market news service", "cache_status": "unavailable"}
            related_news = []

        current_price = float(current.get("current_price") or 0)
        estimated_revenue = round(current_price * float(quantity or 0), 2) if quantity else None

        trend_7d = self._trend_summary(history_7, "7 ngày")
        trend_30d = self._trend_summary(history_30, "30 ngày")
        volatility = self._volatility_summary(history_30)
        news_impact = self._news_impact_summary(related_news)
        recommendation = self._market_recommendation(
            current_price=current_price,
            trend_7d=trend_7d,
            trend_30d=trend_30d,
            quality_grade=selected_grade,
            quantity=quantity,
        )

        confidence_score = self._market_confidence(history_30, current)

        data_sources = [
            {
                "source_type": current.get("source", "database"),
                "source_name": current.get("source_name") or "MarketPrices DB",
                "source_url": current.get("source_url"),
                "fetched_at": self._serialize_dt(current.get("fetched_at") or current.get("last_updated")),
            }
        ]
        if history_30:
            data_sources.append(
                {
                    "source_type": "database",
                    "source_name": "PriceHistory DB",
                    "fetched_at": self._serialize_dt(datetime.now()),
                }
            )
        if current.get("global_reference"):
            data_sources.append(
                {
                    "source_type": current["global_reference"].get("source_type", "global_commodity"),
                    "source_name": current["global_reference"].get("source_name", "Global commodity"),
                    "source_url": current["global_reference"].get("source_url"),
                    "fetched_at": self._serialize_dt(current["global_reference"].get("fetched_at")),
                }
            )
        if related_news:
            data_sources.append(
                {
                    "source_type": news_bundle.get("source", "database"),
                    "source_name": news_bundle.get("source_name", "Market news service"),
                    "fetched_at": self._serialize_dt(datetime.now()),
                }
            )

        result = {
            "crop_name": crop_name.strip(),
            "region": selected_region,
            "current_price": current_price,
            "unit": "VNĐ/kg",
            "estimated_revenue": estimated_revenue,
            "local_price": current.get("local_price") or {
                "price": current_price,
                "unit": current.get("unit", "VNĐ/kg"),
                "source_name": current.get("source_name"),
                "source_type": current.get("source_type"),
            },
            "global_reference": current.get("global_reference"),
            "trend_7d": trend_7d,
            "trend_30d": trend_30d,
            "volatility": volatility,
            "regional_comparison": comparison.get("regions", [])[:2],
            "news_impact": news_impact,
            "related_news": related_news,
            "recommendation": recommendation,
            "risk_level": volatility["level"],
            "confidence_score": confidence_score,
            "data_sources": data_sources,
            "history_7d": history_7,
            "history_30d": history_30,
            "source": current.get("source", "database"),
            "source_name": current.get("source_name"),
            "source_url": current.get("source_url"),
            "fetched_at": current.get("fetched_at"),
            "is_mock": current.get("is_mock", False),
            "cache_status": current.get("cache_status", "from_db"),
        }

        if not history_30:
            result["history_notice"] = "Chưa đủ dữ liệu lịch sử để tính xu hướng 30 ngày"
        if not history_7:
            result["history_notice_7d"] = "Chưa đủ dữ liệu lịch sử để tính xu hướng 7 ngày"

        return result

    def get_market_analysis(
        self,
        db: Session,
        crop_name: str,
        region: str,
        quantity: float | None = None,
        quality_grade: str | None = None,
    ) -> dict:
        from app.services.market_analysis_service import market_analysis_service

        return market_analysis_service.get_analysis(
            db,
            crop_name=crop_name,
            region=region,
            quantity=quantity,
            quality_grade=quality_grade,
        )

    def get_cached_market_analysis(
        self,
        db: Session,
        crop_name: str,
        region: str,
        quantity: float | None = None,
        quality_grade: str | None = None,
    ) -> dict:
        from app.services.market_analysis_service import market_analysis_service

        return market_analysis_service.get_analysis(
            db,
            crop_name=crop_name,
            region=region,
            quantity=quantity,
            quality_grade=quality_grade,
        )

    def refresh_market_analysis(
        self,
        db: Session,
        crop_name: str,
        region: str,
        quantity: float | None = None,
        quality_grade: str | None = None,
    ) -> dict:
        from app.services.market_analysis_service import market_analysis_service

        return market_analysis_service.refresh_analysis(
            db,
            crop_name=crop_name,
            region=region,
            quantity=quantity,
            quality_grade=quality_grade,
        )

    def _news_impact_summary(self, news_items: list[dict]) -> dict:
        if not news_items:
            return {
                "level": "neutral",
                "summary": "Chưa có tin tức thị trường mới đủ liên quan để đánh giá tác động.",
                "impact_score": 0.0,
            }
        score = 0.0
        for item in news_items:
            sentiment = str(item.get("sentiment") or item.get("impact") or "neutral").lower()
            weight = float(item.get("impact_score") or 0.5)
            if sentiment == "positive":
                score += weight
            elif sentiment == "negative":
                score -= weight
        average = score / max(len(news_items), 1)
        if average > 0.15:
            return {
                "level": "positive",
                "summary": "Tin tức thị trường đang hỗ trợ xu hướng tăng giá.",
                "impact_score": round(min(abs(average), 1), 2),
            }
        if average < -0.15:
            return {
                "level": "negative",
                "summary": "Tin tức thị trường có dấu hiệu gây áp lực giảm giá.",
                "impact_score": round(min(abs(average), 1), 2),
            }
        return {
            "level": "neutral",
            "summary": "Tin tức liên quan đang ở mức trung tính.",
            "impact_score": round(min(abs(average), 1), 2),
        }

    def _safe_weather_adjustment(self, db: Session, crop_name: str, region: str, current_price: float) -> dict:
        try:
            from app.services.weather_pricing_service import get_weather_adjusted_pricing

            weather_info = get_weather_adjusted_pricing(db, crop_name, region, current_price)
            return {
                "weather_adjusted_price": weather_info["adjusted_price"],
                "weather_factor": weather_info["weather_factor"],
                "weather_summary": weather_info["weather_summary"],
                "weather_explanation": weather_info["weather_explanation"],
                "price_change_pct": weather_info["price_change_pct"],
            }
        except Exception:
            return {
                "weather_adjusted_price": current_price,
                "weather_factor": 1.0,
                "weather_summary": "",
                "weather_explanation": "",
                "price_change_pct": 0.0,
            }

    def _trend_summary(self, history: list[dict], label: str) -> dict:
        if len(history) < 2:
            return {
                "direction": "stable",
                "percent": 0.0,
                "summary": f"Chưa đủ dữ liệu lịch sử để tính xu hướng {label.lower()}"
            }
        first_price = float(history[0]["avg_price"])
        last_price = float(history[-1]["avg_price"])
        if not first_price:
            percent = 0.0
        else:
            percent = round(((last_price - first_price) / first_price) * 100, 2)
        direction = "up" if percent > 1 else "down" if percent < -1 else "stable"
        summary = (
            f"Giá tăng nhẹ trong {label.lower()}"
            if direction == "up"
            else f"Giá giảm trong {label.lower()}"
            if direction == "down"
            else f"Giá ổn định trong {label.lower()}"
        )
        return {"direction": direction, "percent": percent, "summary": summary}

    def _volatility_summary(self, history: list[dict]) -> dict:
        if len(history) < 3:
            return {
                "level": "low",
                "summary": "Chưa đủ dữ liệu để đánh giá độ biến động",
            }
        prices = [float(item["avg_price"]) for item in history if item.get("avg_price") is not None]
        if len(prices) < 3:
            return {"level": "low", "summary": "Chưa đủ dữ liệu để đánh giá độ biến động"}
        average = sum(prices) / len(prices)
        variance = sum((price - average) ** 2 for price in prices) / len(prices)
        stdev_pct = ((variance ** 0.5) / average) * 100 if average else 0
        if stdev_pct >= 12:
            level = "high"
            summary = "Giá biến động mạnh, nên chia nhỏ sản lượng trước khi bán"
        elif stdev_pct >= 6:
            level = "medium"
            summary = "Giá có dao động nhưng chưa quá rủi ro"
        else:
            level = "low"
            summary = "Giá khá ổn định, rủi ro biến động thấp"
        return {"level": level, "summary": summary, "stdev_percent": round(stdev_pct, 2)}

    def _market_recommendation(
        self,
        *,
        current_price: float,
        trend_7d: dict,
        trend_30d: dict,
        quality_grade: str,
        quantity: float | None,
    ) -> dict:
        grade = self._clean_grade(quality_grade)
        if grade in {"grade_1", "Loai 1", "Loại 1"}:
            action = "sell_partially"
            title = "Nên bán một phần sản lượng"
            reason = (
                "Chất lượng loại 1 có thể giữ giá cao. "
                "Giá đang cải thiện nên nên bán 60-70% để chốt lợi nhuận và giữ phần còn lại nếu kho chứa tốt."
            )
        elif grade in {"grade_3", "Loai 3", "Loại 3"}:
            action = "sell_soon"
            title = "Nên bán sớm"
            reason = (
                "Chất lượng thấp dễ bị ép giá. "
                "Nên ưu tiên chốt đơn sớm, hạn chế để hàng tồn lâu."
            )
        else:
            action = "hold_and_monitor"
            title = "Có thể theo dõi thêm"
            reason = (
                "Chất lượng ở mức trung bình, nên theo dõi thêm 3-5 ngày trước khi quyết định."
            )

        if trend_7d["direction"] == "down" and trend_30d["direction"] == "down":
            action = "sell_soon"
            title = "Nên bán sớm"
            reason = (
                "Giá đang giảm ở cả 7 ngày và 30 ngày gần đây. "
                "Nên ưu tiên chốt giá để giảm rủi ro."
            )
        elif trend_7d["direction"] == "up" and trend_30d["direction"] == "up":
            action = "hold_partially"
            title = "Có thể giữ lại một phần"
            reason = (
                "Giá đang tăng ở cả ngắn và dài hạn. "
                "Có thể giữ lại 30-40% nếu có điều kiện bảo quản tốt để chờ giá tốt hơn."
            )

        if quantity and float(quantity) >= 1000 and action == "sell_partially":
            reason += " Sản lượng lớn nên chia 2-3 đợt bán để tránh áp lực giá."

        return {
            "action": action,
            "title": title,
            "reason": reason,
            "current_price_context": current_price,
        }

    def _market_confidence(self, history: list[dict], current: dict) -> float:
        confidence = 0.55
        if history:
            confidence += 0.18
        if len(history) >= 7:
            confidence += 0.12
        if not current.get("is_mock"):
            confidence += 0.1
        return round(min(confidence, 0.95), 2)

    def _nearby_region_prices(self, db: Session, crop_name: str, region: str) -> list[dict]:
        latest_prices = get_latest_prices_by_crop(db, crop_name, limit=10)
        result = []
        seen = {normalize_text(self._clean_region(region))}
        for item in latest_prices:
            normalized_region = normalize_text(item.Region)
            if normalized_region in seen:
                continue
            seen.add(normalized_region)
            result.append(
                {
                    "region": self._clean_region(item.Region),
                    "price": float(item.price),
                    "unit": getattr(item, "unit", "VNĐ/kg"),
                    "collected_at": self._serialize_dt(item.collected_at),
                    "source": "database",
                    "source_name": getattr(item, "source_name", None) or "MarketPrices DB",
                    "updated_at": self._serialize_dt(item.collected_at),
                    "confidence": 0.7,
                    "is_mock": False,
                }
            )
        return result

    def _get_price_from_crop_profile(
        self,
        db: Session,
        crop_name: str,
        region: str,
        quality_grade: str,
    ) -> float:
        # Anti-mock: TypicalPriceMin/Max trong CropType nếu không có dữ liệu thật realtime/cache thì cũng không được dùng để sinh giá.
        # Hiện tại giữ nguyên hàm nhưng không fallback synthetic.
        try:
            crop = ensure_crop(db, crop_name)
            if crop and crop.TypicalPriceMin and crop.TypicalPriceMax:
                base = (float(crop.TypicalPriceMin) + float(crop.TypicalPriceMax)) / 2
                return round(base * self.quality_multipliers.get(quality_grade, 1.0), 2)
        except Exception:
            pass
        raise ValueError("No real cached price available for this crop/region/grade.")

    def _previous_price(self, db: Session, crop_name: str, region: str, quality_grade: str) -> float | None:
        history = self.get_price_history(db, crop_name, region, 7)
        if len(history) < 2:
            return None
        return float(history[-2]["avg_price"])

    def _get_recent_prices_from_db(self, db: Session, crop_name: str, region: str) -> list[float]:
        try:
            from app.models.crop import CropType
            from app.models.price import MarketPrice

            crop = ensure_crop(db, self._clean_crop(crop_name))
            if not crop:
                return []
            rows = (
                db.query(MarketPrice)
                .filter(MarketPrice.CropID == crop.CropID)
                .order_by(MarketPrice.PriceDate.desc(), MarketPrice.UpdatedAt.desc())
                .limit(7)
                .all()
            )
            target_region = normalize_text(self._clean_region(region))
            rows = [row for row in rows if normalize_text(row.Region) == target_region]
            return [float(r.PricePerKg) for r in reversed(rows)]
        except Exception:
            return []

    def _mock_price(self, crop_name: str, region: str, quality_grade: str) -> float:
        raise RuntimeError("Mock/synthetic price is disabled by spec.")

    @staticmethod
    def _clean_region(region: str | None) -> str:
        raw = " ".join((region or "Ha Noi").strip().split()) or "Ha Noi"
        key = normalize_text(raw)
        return REGION_DISPLAY_ALIASES.get(key, raw)

    @staticmethod
    def _clean_crop(crop_name: str | None) -> str:
        return normalize_text(crop_name) or "lua"

    @staticmethod
    def _clean_grade(quality_grade: str | None) -> str:
        if not quality_grade:
            return "grade_1"
        grade = quality_grade.strip()
        return to_db_grade(grade) if grade.lower().startswith("grade") or "loai" in normalize_text(grade) else grade

    @staticmethod
    def _display_crop(crop_name: str) -> str:
        labels = {"lua": "Lúa", "gao": "Gạo", "ca phe": "Cà phê", "ho tieu": "Hồ tiêu"}
        return labels.get(crop_name, crop_name.title())

    @staticmethod
    def _cache_status(updated_at: datetime | None) -> str:
        if not updated_at:
            return "unknown"
        age = datetime.now() - updated_at
        if age <= timedelta(hours=24):
            return "fresh"
        return "stale"

    @staticmethod
    def _age_minutes(updated_at: datetime | None) -> int | None:
        if not updated_at:
            return None
        delta = datetime.now() - updated_at
        return max(int(delta.total_seconds() // 60), 0)

    @staticmethod
    def _trend_from_change(change_percent: float) -> str:
        if change_percent > 1:
            return "up"
        if change_percent < -1:
            return "down"
        return "stable"

    @staticmethod
    def _serialize_dt(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _normalize_key(value: str) -> str:
        normalized = unicode_normalize("NFD", value.strip().lower())
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        return normalized.replace("đ", "d").replace("Đ", "d").strip()

    @staticmethod
    def _realtime_only() -> bool:
        return bool(settings.USE_REALTIME_ONLY) and not bool(settings.ALLOW_MOCK_DATA or settings.ALLOW_SAMPLE_DATA)

    @staticmethod
    def _has_positive_price(value) -> bool:
        try:
            return value is not None and float(value) > 0
        except (TypeError, ValueError):
            return False

    def _trend_summary_text(self, direction: str, days: int) -> str:
        if direction == "up":
            return f"Giá tăng nhẹ trong {days} ngày gần đây"
        if direction == "down":
            return f"Giá giảm trong {days} ngày gần đây"
        return f"Giá ổn định trong {days} ngày gần đây"


pricing_service = PricingService()
