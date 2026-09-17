from __future__ import annotations

from datetime import datetime
from statistics import mean
from typing import Any
import json

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.real_data import OFFICIAL_AGRI_SOURCE_NAME, OFFICIAL_PRICE_URL, age_minutes, cache_status_for, realtime_error
from app.models.market import MarketAnalysisResult
from app.services.market_news_service import market_news_service
from app.services.pricing_service import pricing_service
from app.services.retail_price_service import retail_price_service
from app.services.weather_service import weather_service


class MarketAnalysisService:
    """Service phân tích thị trường (rule-based + dữ liệu thật).

    Spec yêu cầu:
    - Không bịa giá/tin.
    - Chỉ phân tích dựa trên dữ liệu thật có source_url.
    - Nếu thiếu retail_prices: vẫn trả official_market_price và cảnh báo.
    - Output KHỚP format spec (chỉ các field được liệt kê).
    """

    ANALYSIS_CACHE_TTL_SECONDS = 60 * 30  # 30 phút

    # In-process cache (đủ dùng cho demo / GET hiện tại)
    _analysis_cache: dict[str, dict[str, Any]] = {}

    def get_analysis(
        self,
        db: Session,
        *,
        crop_name: str,
        region: str,
        quantity: float | None = None,
        quality_grade: str | None = None,
    ) -> dict:
        crop = self._clean_crop(crop_name)
        reg = self._clean_region(region)
        cached = self._latest_cached_analysis(db, crop, reg)
        if cached:
            status = cache_status_for(cached.FetchedAt, "market_analysis")
            if status in {"fresh_cache", "stale_cache"}:
                try:
                    payload = json.loads(cached.PayloadJSON)
                except Exception:
                    payload = {}
                payload.update(
                    {
                        "source_name": cached.SourceName,
                        "source_url": cached.SourceURL,
                        "is_realtime": False,
                        "is_mock": False,
                        "cache_status": status,
                        "fetched_at": cached.FetchedAt,
                        "last_updated": cached.FetchedAt,
                        "data_age_minutes": age_minutes(cached.FetchedAt),
                    }
                )
                return self._format_output(payload)

        # Cache miss: compute on-demand instead of returning an error
        computed = self._compute_analysis(db, crop_name=crop, region=reg, quantity=quantity, quality_grade=quality_grade)
        if computed.get("_api_error"):
            return computed
        row = self._save_analysis(db, crop, reg, computed)
        primary_source = (computed.get("sources") or [{}])[0]
        computed.update(
            {
                "source_name": primary_source.get("source_name") if primary_source else None,
                "source_url": primary_source.get("source_url") if primary_source else None,
                "is_realtime": False,
                "is_mock": False,
                "cache_status": "database",
                "fetched_at": row.FetchedAt if row else datetime.utcnow(),
                "last_updated": row.FetchedAt if row else datetime.utcnow(),
                "data_age_minutes": 0,
            }
        )
        return self._format_output(computed)

    def refresh_analysis(
        self,
        db: Session,
        *,
        crop_name: str,
        region: str,
        quantity: float | None = None,
        quality_grade: str | None = None,
    ) -> dict:
        crop = self._clean_crop(crop_name)
        reg = self._clean_region(region)
        computed = self._compute_analysis(
            db,
            crop_name=crop,
            region=reg,
            quantity=quantity,
            quality_grade=quality_grade,
        )
        if computed.get("_api_error"):
            return computed
        row = self._save_analysis(db, crop, reg, computed)
        primary_source = (computed.get("sources") or [{}])[0]
        computed.update(
            {
                "source_name": primary_source.get("source_name") if primary_source else None,
                "source_url": primary_source.get("source_url") if primary_source else None,
                "is_realtime": False,
                "is_mock": False,
                "cache_status": "database",
                "fetched_at": row.FetchedAt if row else datetime.utcnow(),
                "last_updated": row.FetchedAt if row else datetime.utcnow(),
                "data_age_minutes": 0,
            }
        )
        return self._format_output(computed)

    def _compute_analysis(
        self,
        db: Session,
        *,
        crop_name: str,
        region: str,
        quantity: float | None,
        quality_grade: str | None,
    ) -> dict:
        current = pricing_service.get_current_price(
            db,
            crop_name,
            region,
            quality_grade or "grade_1",
            include_weather=False,
        )
        if current.get("_api_error"):
            return current

        history_30 = pricing_service.get_price_history(db, crop_name, region, 30)
        history_7 = pricing_service.get_price_history(db, crop_name, region, 7)

        # Retail prices only from cached snapshot
        retail_bundle = retail_price_service.get_cached_retail_prices(db, crop_name, limit=10)
        retail_items = retail_bundle.get("retail_prices", []) if isinstance(retail_bundle, dict) else []

        # Market news (official + Tavily)
        news_bundle = market_news_service.get_market_news(db, crop=crop_name, region=region, limit=5)
        news_items = news_bundle.get("news", []) if isinstance(news_bundle, dict) else []

        # Weather (optional)
        weather = weather_service.get_current_weather(db, region)

        official_price = self._safe_float(current.get("current_price"))

        retail_prices: list[float] = []
        for item in (retail_items or []):
            # anti-bịa: chỉ dùng nếu có source_url
            if not item.get("source_url"):
                continue
            p = self._safe_float(item.get("price") or item.get("retail_price"))
            if p is not None:
                retail_prices.append(p)

        average_retail_price = round(mean(retail_prices), 2) if retail_prices else None

        retail_margin_percent = None
        if average_retail_price is not None and official_price is not None and official_price != 0:
            retail_margin_percent = round(((average_retail_price - official_price) / official_price) * 100, 1)

        price_gap_level = self._gap_level(retail_margin_percent)

        trend_7d = self._trend_summary(history_7)
        trend_30d = self._trend_summary(history_30)
        news_impact_level = self._news_impact_level(news_items)
        weather_signal = self._weather_signal(weather)

        market_signal = self._market_signal(
            has_retail=average_retail_price is not None,
            price_gap_level=price_gap_level,
            trend_7d=trend_7d,
            trend_30d=trend_30d,
            news_impact_level=news_impact_level,
            weather_signal=weather_signal,
        )

        recommendations = self._recommendations(
            official_price=official_price,
            average_retail_price=average_retail_price,
            retail_margin_percent=retail_margin_percent,
            price_gap_level=price_gap_level,
            has_retail=average_retail_price is not None,
            trend_7d=trend_7d,
            trend_30d=trend_30d,
            news_impact_level=news_impact_level,
            weather_signal=weather_signal,
            quantity=quantity,
            quality_grade=quality_grade,
        )

        sources = self._build_sources(
            current=current,
            news_bundle=news_bundle,
            retail_bundle=retail_bundle,
            weather=weather,
        )

        return {
            "crop_name": crop_name,
            "region": region,
            "official_market_price": int(official_price) if official_price is not None else None,
            "average_retail_price": average_retail_price,
            "retail_margin_percent": retail_margin_percent,
            "price_gap_level": price_gap_level,
            "market_signal": market_signal,
            "recommendations": recommendations,
            "sources": sources,
            "_computed_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _format_output(payload: dict) -> dict:
        official_price = payload.get("official_market_price")
        has_price = official_price is not None
        source_name = payload.get("source_name") if has_price else None
        source_url = payload.get("source_url") if has_price else None
        # Enforce exact spec shape
        return {
            "crop_name": payload.get("crop_name"),
            "region": payload.get("region"),
            "official_market_price": official_price,
            "current_price": official_price,  # alias so FE MarketPage can read analysis.current_price
            "market_price": official_price,
            "price": official_price,
            "average_retail_price": payload.get("average_retail_price"),
            "retail_margin_percent": payload.get("retail_margin_percent"),
            "price_gap_level": payload.get("price_gap_level"),
            "market_signal": payload.get("market_signal"),
            "recommendations": payload.get("recommendations"),
            "sources": payload.get("sources", []),
            "source_name": source_name,
            "source_url": source_url,
            "is_realtime": bool(payload.get("is_realtime", False)),
            "is_mock": False,
            "cache_status": payload.get("cache_status", "fresh_cache") if has_price else "miss",
            "fetched_at": payload.get("fetched_at"),
            "last_updated": payload.get("last_updated") or payload.get("fetched_at"),
            "data_age_minutes": payload.get("data_age_minutes"),
            "confidence_score": 0.72 if official_price else 0.0,
            "confidence": 0.72 if official_price else 0.0,
            "warning": payload.get("warning") or ("Chưa có giá thị trường đã kiểm chứng cho lựa chọn này." if not has_price else None),
        }

    def _is_cache_valid(self, cached: dict[str, Any]) -> bool:
        cached_at = cached.get("cached_at")
        if not cached_at:
            return False
        age = datetime.utcnow().timestamp() - float(cached_at)
        return age <= self.ANALYSIS_CACHE_TTL_SECONDS

    @staticmethod
    def _analysis_cache_key(crop_name: str, region: str) -> str:
        return f"{crop_name.strip().lower()}::{region.strip().lower()}"

    def _latest_cached_analysis(self, db: Session, crop_name: str, region: str) -> MarketAnalysisResult | None:
        try:
            return (
                db.query(MarketAnalysisResult)
                .filter(
                    MarketAnalysisResult.CropName == crop_name,
                    MarketAnalysisResult.Region == region,
                    MarketAnalysisResult.IsMock == False,  # noqa: E712
                    MarketAnalysisResult.Status == "ready",
                )
                .order_by(desc(MarketAnalysisResult.FetchedAt), desc(MarketAnalysisResult.CreatedAt))
                .first()
            )
        except Exception:
            db.rollback()
            return None

    def _save_analysis(self, db: Session, crop_name: str, region: str, payload: dict) -> MarketAnalysisResult | None:
        try:
            row = MarketAnalysisResult(
                CropName=crop_name,
                Region=region,
                PayloadJSON=json.dumps(payload, ensure_ascii=False, default=str),
                SourceName="Market analysis cache",
                SourceURL=OFFICIAL_PRICE_URL,
                FetchedAt=datetime.utcnow(),
                IsRealtime=False,
                IsMock=False,
                Status="ready",
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row
        except Exception:
            db.rollback()
            return None

    def _build_sources(self, *, current: dict, news_bundle: dict, retail_bundle: dict, weather: dict) -> list[dict]:
        sources: list[dict] = []

        if current.get("source_url"):
            sources.append(
                {
                    "source_name": current.get("source_name") or OFFICIAL_AGRI_SOURCE_NAME,
                    "source_url": current.get("source_url") or OFFICIAL_PRICE_URL,
                    "fetched_at": current.get("fetched_at") or current.get("last_updated"),
                }
            )

        if news_bundle and news_bundle.get("source_url"):
            sources.append(
                {
                    "source_name": news_bundle.get("source_name") or "Thông tin thị trường nông sản",
                    "source_url": news_bundle.get("source_url"),
                    "fetched_at": news_bundle.get("fetched_at") or news_bundle.get("last_updated"),
                }
            )

        if retail_bundle and retail_bundle.get("source_url"):
            sources.append(
                {
                    "source_name": retail_bundle.get("source_name") or "Vietnam retail websites",
                    "source_url": retail_bundle.get("source_url"),
                    "fetched_at": retail_bundle.get("fetched_at") or retail_bundle.get("last_updated"),
                }
            )

        if weather and not weather.get("_api_error") and weather.get("source_url"):
            sources.append(
                {
                    "source_name": weather.get("source_name") or "Open-Meteo",
                    "source_url": weather.get("source_url"),
                    "fetched_at": weather.get("fetched_at") or weather.get("last_updated"),
                }
            )

        # Ensure every source has source_url
        return [s for s in sources if s.get("source_url")]

    # ---------------- Rules/helpers ----------------
    @staticmethod
    def _safe_float(value: Any) -> float | None:
        try:
            if value is None:
                return None
            v = float(value)
            if v != v:
                return None
            return v
        except Exception:
            return None

    @staticmethod
    def _trend_summary(history: list[dict]) -> dict:
        if len(history) < 2:
            return {"direction": "stable", "percent": 0.0}
        first = float(history[0].get("avg_price") or 0)
        last = float(history[-1].get("avg_price") or 0)
        if first == 0:
            return {"direction": "stable", "percent": 0.0}
        percent = round(((last - first) / first) * 100, 2)
        direction = "up" if percent > 1 else "down" if percent < -1 else "stable"
        return {"direction": direction, "percent": percent}

    @staticmethod
    def _news_impact_level(news_items: list[dict]) -> str:
        if not news_items:
            return "neutral"
        score = 0.0
        for item in news_items:
            sentiment = str(item.get("sentiment") or item.get("impact") or "neutral").lower()
            if sentiment == "positive":
                score += float(item.get("impact_score") or 0.5)
            elif sentiment == "negative":
                score -= float(item.get("impact_score") or 0.5)
        avg = score / max(len(news_items), 1)
        if avg > 0.15:
            return "positive"
        if avg < -0.15:
            return "negative"
        return "neutral"

    @staticmethod
    def _weather_signal(weather: dict) -> str:
        if not weather or weather.get("_api_error"):
            return "none"
        warnings = weather.get("warnings") or []
        if isinstance(warnings, list) and warnings:
            return "risk"
        return "ok"

    @staticmethod
    def _gap_level(retail_margin_percent: float | None) -> str:
        if retail_margin_percent is None:
            return "unknown"
        if retail_margin_percent >= 60:
            return "high"
        if retail_margin_percent >= 30:
            return "medium"
        return "low"

    def _market_signal(
        self,
        *,
        has_retail: bool,
        price_gap_level: str,
        trend_7d: dict,
        trend_30d: dict,
        news_impact_level: str,
        weather_signal: str,
    ) -> str:
        if not has_retail:
            return "Thiếu dữ liệu bán lẻ, nên chỉ có thể đánh giá dựa trên giá thị trường chính thức."

        if price_gap_level == "high":
            return "Giá bán lẻ cao hơn nhiều so với giá thị trường, có thể có chênh lệch trung gian lớn."

        # Keep one-string style (qualitative)
        parts: list[str] = []
        if trend_7d.get("direction") == "up" or trend_30d.get("direction") == "up":
            parts.append("Xu hướng giá cải thiện theo dữ liệu lịch sử.")
        if trend_7d.get("direction") == "down" and trend_30d.get("direction") == "down":
            parts.append("Xu hướng giá giảm kéo dài theo dữ liệu lịch sử.")
        if news_impact_level == "positive":
            parts.append("Tin tức có xu hướng hỗ trợ giá.")
        elif news_impact_level == "negative":
            parts.append("Tin tức có xu hướng tạo áp lực giá.")
        if weather_signal == "risk":
            parts.append("Thời tiết có cảnh báo/rủi ro theo dữ liệu hiện có.")

        if not parts:
            return "Giá khá ổn định, chưa có tín hiệu cực đoan rõ ràng."
        return parts[0]

    def _recommendations(
        self,
        *,
        official_price: float | None,
        average_retail_price: float | None,
        retail_margin_percent: float | None,
        price_gap_level: str,
        has_retail: bool,
        trend_7d: dict,
        trend_30d: dict,
        news_impact_level: str,
        weather_signal: str,
        quantity: float | None,
        quality_grade: str | None,
    ) -> list[str]:
        recs: list[str] = []

        # Spec example recommends always 2 points; we try to comply.
        recs.append("Nên so sánh nhiều kênh bán trước khi chốt giá.")

        if not has_retail:
            recs.append("Nếu có dữ liệu bán lẻ sau, hãy đối chiếu retail_prices để đánh giá đúng chênh lệch.")
            return recs

        if price_gap_level in {"high", "medium"}:
            recs.append("Nếu có đầu ra trực tiếp, có thể ưu tiên bán qua kênh bán lẻ/HTX.")
        else:
            recs.append("Giữ chiến lược giá dựa trên biến động gần đây và theo dõi thêm tin tức.")

        if weather_signal == "risk":
            recs.append("Thời tiết có rủi ro theo dữ liệu hiện có; cân nhắc tiến độ thu hoạch/đầu ra.")

        if news_impact_level == "positive":
            recs.append("Tin tức có xu hướng hỗ trợ giá.")
        elif news_impact_level == "negative":
            recs.append("Tin tức có xu hướng tạo áp lực giá.")

        if quantity:
            recs.append(f"Với sản lượng {quantity:g} kg, nên chia theo nhiều kênh để tối ưu đầu ra.")

        if quality_grade:
            recs.append(f"Định giá đã cân nhắc chất lượng {quality_grade}.")

        # ensure at least 2
        if len(recs) < 2:
            recs.append("Chưa đủ tín hiệu mạnh, nên tiếp tục theo dõi giá và kênh bán.")

        return recs[:6]

    @staticmethod
    def _clean_crop(crop_name: str | None) -> str:
        return (crop_name or "lua").strip().lower() or "lua"

    @staticmethod
    def _clean_region(region: str | None) -> str:
        return " ".join((region or "Ha Noi").strip().split()) or "Ha Noi"


market_analysis_service = MarketAnalysisService()

