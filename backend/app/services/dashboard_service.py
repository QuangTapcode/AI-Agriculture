import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

from sqlalchemy import desc, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.repositories.common import normalize_text
from app.models.crop import CropType
from app.models.price import MarketPrice
from app.core.real_data import OFFICIAL_AGRI_SOURCE_NAME, OFFICIAL_NEWS_URL, OFFICIAL_PRICE_URL, OPEN_METEO_FORECAST_URL, OPEN_METEO_SOURCE_NAME, external_circuit_breaker, realtime_error
from app.core.redis_client import redis_client
from app.integrations.weather_client import WeatherClient
from app.models.crop import Crop
from app.models.market_news import MarketNews
from app.models.price import MarketPrice
from app.models.quality import QualityCheck
from app.models.season import Season
from app.models.user import User
from app.models.weather import WeatherData, WeatherObservation
from app.repositories.common import ensure_crop
from app.services.alert_service import alert_service
from app.services.market_news_service import market_news_service
from app.services.notification_center_service import notification_center_service
from app.services.price_aggregator_service import price_aggregator_service
from app.services.pricing_service import pricing_service
from app.services.weather_service import weather_service


DEFAULT_REGIONS = ["Ha Noi", "TP.HCM", "Da Nang", "Can Tho", "Lam Dong", "Dak Lak"]
logger = logging.getLogger(__name__)


def _gia_hoac_none(item: dict) -> float | None:
    """Giá thật, hoặc None khi thiếu — không bao giờ quy về 0."""
    for key in ("current_price", "market_price", "price"):
        gia = item.get(key)
        if gia is not None and gia != "":
            try:
                return float(gia)
            except (TypeError, ValueError):
                continue
    return None


class DashboardService:
    def __init__(self):
        self.weather_client = WeatherClient()

    def get_summary(
        self,
        db: Session,
        user_id: int | None = None,
        region: str | None = None,
        crop_name: str = "lua",
        force_refresh_weather: bool = False,
        force_refresh_market: bool = False,
        force_refresh_news: bool = False,
    ) -> dict:
        selected_region = self._clean_region(region)
        selected_crop = self._clean_crop(crop_name)
        force_refresh = force_refresh_weather or force_refresh_market or force_refresh_news

        cache_key = f"dashboard:summary:v2:{selected_region}:{selected_crop}:{user_id or 'anon'}"
        if not force_refresh:
            try:
                cached = redis_client.get(cache_key)
                if cached and isinstance(cached, dict):
                    return cached
            except Exception:
                pass

        module_status: list[dict] = []

        if force_refresh_market:
            self._safe_dashboard_call(
                "refresh_prices",
                lambda: price_aggregator_service.refresh_prices(db, crop_name=selected_crop),
                {"status": "failed", "records_fetched": 0, "records_saved": 0},
                module_status,
            )
        if force_refresh_news:
            self._safe_dashboard_call(
                "refresh_news",
                market_news_service.refresh_news,
                {"status": "failed", "records_fetched": 0, "records_saved": 0},
                module_status,
            )

        # 5 lời gọi dưới đây độc lập nhau nhưng trước kia chạy nối đuôi, khiến
        # /api/dashboard/summary mất ~7s trong khi các endpoint khác chỉ vài
        # trăm ms. Chạy song song, MỖI LUỒNG MỘT SESSION RIÊNG vì SQLAlchemy
        # Session không thread-safe — dùng chung sẽ hỏng dữ liệu ngẫu nhiên.
        jobs = {
            "featured_crop": (
                lambda sess: self.get_featured_crop(
                    sess, crop_name=selected_crop, region=selected_region, force_refresh=False
                ),
                lambda: self._fallback_featured_crop(selected_crop, selected_region),
            ),
            "weather_risk": (
                lambda sess: self.get_weather_risk(
                    sess, region=selected_region, crop_name=selected_crop,
                    force_refresh=force_refresh_weather,
                ),
                lambda: self._fallback_weather_risk(selected_region, selected_crop),
            ),
            "price_trend": (
                lambda sess: self.get_price_trend(
                    sess, crop_name=selected_crop, region=selected_region, days=7
                ),
                lambda: self._fallback_price_trend(selected_crop, selected_region),
            ),
            "market_news": (
                lambda sess: self.get_news(
                    sess, limit=6, crop_name=selected_crop, region=None, force_refresh=False
                ),
                lambda: self._fallback_news(),
            ),
            "regional_prices": (
                lambda sess: self.get_regional_prices(sess, crop_name=selected_crop),
                {
                    "regions": [],
                    "source": "realtime_api",
                    "source_name": "Regional price service",
                    "is_mock": False,
                    "error": "Không thể tải giá theo khu vực realtime.",
                },
            ),
        }
        ket_qua = self._run_dashboard_jobs(jobs, module_status)
        featured = ket_qua["featured_crop"]
        weather_risk = ket_qua["weather_risk"]
        trend = ket_qua["price_trend"]
        news = ket_qua["market_news"]
        regional_price_data = ket_qua["regional_prices"]
        regional_prices = regional_price_data.get("regions", [])

        # Reuse featured instead of calling get_featured_crop() again inside get_realtime_market()
        realtime_market = self._safe_dashboard_call(
            "realtime_market",
            lambda: {
                "featured_crop": featured,
                "global_references": price_aggregator_service.latest_global_references(db, limit=6),
                "exchange_rate": price_aggregator_service.exchange_rate(live=False),
                "cache_status": featured.get("cache_status", "from_db"),
                "last_updated": featured.get("last_updated"),
            },
            lambda: self._fallback_realtime_market(featured),
            module_status,
        )
        user = self._get_user(db, user_id)
        active_alerts = self._safe_dashboard_call(
            "active_alerts",
            lambda: alert_service.get_active_alerts(
                db,
                user_id=user_id,
                crop=selected_crop,
                region=selected_region,
            ),
            [],
            module_status,
        )
        if not active_alerts and not self._realtime_only():
            generated_alerts = self._safe_dashboard_call(
                "auto_alerts",
                lambda: alert_service.auto_generate_alerts(
                    db,
                    {"crop_name": selected_crop, "region": selected_region},
                    user,
                ),
                {"alerts": []},
                module_status,
            )
            active_alerts = generated_alerts.get("alerts", [])
        notification_summary = {
            "total": 0,
            "unread": 0,
            "source": "database",
            "source_name": "Notifications DB",
            "confidence": 0.7,
            "updated_at": datetime.now(),
        }
        if user:
            notification_summary = self._safe_dashboard_call(
                "notification_summary",
                lambda: notification_center_service.summary(db, user),
                notification_summary,
                module_status,
            )

        try:
            seasons_query = db.query(Season)
            quality_query = db.query(QualityCheck)
            if user_id:
                seasons_query = seasons_query.filter(Season.UserID == user_id)
                quality_query = quality_query.filter(QualityCheck.UserID == user_id)
            active_seasons = seasons_query.filter(Season.Status.in_(["active", "harvesting"])).count()
            quality_checks = quality_query.count()
            unread_notifications = int(notification_summary.get("unread", 0))
        except SQLAlchemyError:
            db.rollback()
            active_seasons = quality_checks = unread_notifications = 0

        # Derive weather overview from already-computed weather_risk (no extra DB calls)
        weather_overview = {
            "current": weather_risk.get("current", {}),
            "forecast": weather_risk.get("forecast", []),
            "alerts": weather_risk.get("alerts", []),
            "is_mock": weather_risk.get("is_mock", False),
            "is_realtime": weather_risk.get("is_realtime", False),
            "cache_status": weather_risk.get("cache_status", "from_db"),
            "last_updated": weather_risk.get("last_updated"),
        }

        # Compute ai_recommendation from already-fetched featured + weather_risk (no extra service calls)
        ai_recommendation = self._safe_dashboard_call(
            "ai_recommendation",
            lambda: self._compute_ai_recommendation_inline(featured, weather_risk, selected_crop, selected_region),
            lambda: self._fallback_ai_recommendation(selected_crop, selected_region),
            module_status,
        )

        result = {
            "region": selected_region,
            "crop_name": selected_crop,
            "featured_crop": featured,
            "weather": weather_overview,
            "weather_risk": weather_risk,
            "forecast": trend.get("forecast", []),
            "price_trend": trend,
            "regional_prices": regional_prices,
            "news": news.get("news", []),
            "realtime_market": realtime_market,
            "alert_center": active_alerts,
            "alert_count": len(active_alerts),
            "notifications": notification_summary,
            "ai_recommendation": ai_recommendation,
            "active_seasons": active_seasons,
            "quality_checks": quality_checks,
            "unread_notifications": unread_notifications,
            "generated_at": datetime.now(),
            "cache_status": "from_db",
            "module_status": module_status,
            "fallback_used": any(not item.get("ok") for item in module_status),
        }

        try:
            redis_client.set(cache_key, result, expire=180)
        except Exception:
            pass

        return result

    def reset_and_load_dashboard(
        self,
        db: Session,
        user_id: int | None = None,
        region: str | None = None,
        crop_name: str = "lua",
    ) -> dict:
        selected_region = self._clean_region(region)
        selected_crop = self._clean_crop(crop_name)

        self._delete_dashboard_realtime_data(db, selected_region, selected_crop)

        refresh_results: dict[str, dict] = {}
        tasks = {
            "weather": lambda: self._refresh_weather_in_new_session(selected_region),
            "prices": lambda: self._refresh_prices_in_new_session(selected_crop),
            "news": market_news_service.refresh_news,
        }
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(task): name for name, task in tasks.items()}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    refresh_results[name] = future.result()
                except Exception as exc:
                    refresh_results[name] = {"status": "failed", "error": str(exc)}

        db.expire_all()
        summary = self.get_summary(
            db,
            user_id=user_id,
            region=selected_region,
            crop_name=selected_crop,
            force_refresh_weather=False,
            force_refresh_market=False,
            force_refresh_news=False,
        )
        summary["reset_refresh"] = refresh_results
        summary["cache_status"] = "reset_refreshed"
        return summary


    def _run_dashboard_jobs(self, jobs: dict, module_status: list[dict]) -> dict:
        """Chạy các khối dashboard song song, mỗi khối một DB session riêng.

        SQLAlchemy Session không thread-safe nên không dùng chung session của
        request; mỗi luồng tự mở và tự đóng session của mình.
        """
        def chay(ten, fn, fallback):
            sess = SessionLocal()
            try:
                return ten, self._safe_dashboard_call(
                    ten, lambda: fn(sess), fallback, module_status
                )
            finally:
                sess.close()

        out: dict = {}
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futures = [pool.submit(chay, ten, fn, fb) for ten, (fn, fb) in jobs.items()]
            for f in as_completed(futures):
                ten, gia_tri = f.result()
                out[ten] = gia_tri
        return out

    def _crop_with_recent_price(self, db: Session, region: str, exclude: str = "") -> str | None:
        """Cây có giá mới nhất ở vùng này, theo đúng dữ liệu đang có trong DB.

        Trước đây dò từng cây bằng cách gọi pricing_service nhiều lần — mỗi lần
        có thể chạm mạng, khiến /api/dashboard/summary gọi get_current_price
        tới 10 lần. Một truy vấn thẳng vào MarketPrices rẻ hơn hẳn và luôn
        đúng với dữ liệu thật, không cần bảng cây-theo-vùng viết tay.
        """
        try:
            muc_tieu = normalize_text(region or "")
            rows = (
                db.query(CropType.CropName, MarketPrice.Region)
                .join(MarketPrice, MarketPrice.CropID == CropType.CropID)
                .order_by(MarketPrice.PriceDate.desc(), MarketPrice.UpdatedAt.desc())
                .limit(200)
                .all()
            )
            bo_qua = normalize_text(exclude)
            for ten, vung in rows:
                # Phải đúng vùng: cây mới nhất toàn quốc thường không có giá ở
                # vùng người dùng, chọn nó chỉ tốn thêm một lượt gọi rồi vẫn hỏng.
                if normalize_text(vung or "") != muc_tieu:
                    continue
                ung_vien = normalize_text(ten)
                if ung_vien and ung_vien != bo_qua:
                    return ung_vien
        except SQLAlchemyError as exc:
            logger.warning("[dashboard] khong tra duoc cay theo vung: %s", exc)
        return None

    def get_featured_crop(
        self,
        db: Session,
        crop_name: str = "lua",
        region: str | None = None,
        force_refresh: bool = False,
    ) -> dict:
        selected_region = self._clean_region(region)
        selected_crop = self._clean_crop(crop_name)
        if force_refresh:
            price_aggregator_service.refresh_prices(db, crop_name=selected_crop)

        current = pricing_service.get_current_price(db, selected_crop, selected_region)

        # Cây được hỏi không có giá ở vùng này, nhưng vùng có thể đang có giá
        # cây khác. Mặc định crop_name="lua" áp cho mọi vùng khiến nông dân
        # Đắk Lắk (vùng cà phê) thấy card chính trống, dù DB có giá cà phê.
        substituted_for = None
        if current.get("_api_error"):
            ung_vien = self._crop_with_recent_price(db, selected_region, exclude=selected_crop)
            if ung_vien:
                thu = pricing_service.get_current_price(db, ung_vien, selected_region)
                if not thu.get("_api_error"):
                    substituted_for = selected_crop
                    selected_crop, current = ung_vien, thu

        if current.get("_api_error"):
            current.update(
                {
                    "name": selected_crop,
                    "display_name": self._display_crop(selected_crop),
                    "location": selected_region,
                    "price": None,
                    "unit": "VND/kg",
                    "trend": None,
                }
            )
            return current
        current["substituted_for"] = substituted_for
        current_price = float(current["current_price"])
        last_updated = current.get("last_updated") or datetime.now()
        source_name = current.get("source_name") or "pricing_service"
        source_url = current.get("source_url")
        is_mock = bool(current.get("is_mock"))
        cache_status = current.get("cache_status", "from_db")

        history = pricing_service.get_price_history(db, selected_crop, selected_region, 7)
        previous_day = history[-2]["avg_price"] if len(history) >= 2 else current_price
        first_week = history[0]["avg_price"] if history else current_price

        return {
            "name": selected_crop,
            "substituted_for": substituted_for,
            "display_name": self._display_crop(selected_crop),
            "location": selected_region,
            "price": current_price,
            "unit": "VND/kg",
            "change": self._format_pct(self._pct_change(current_price, previous_day)),
            "change_day_pct": self._pct_change(current_price, previous_day),
            "change_week_pct": self._pct_change(current_price, first_week),
            "trend": pricing_service.analyze_price_trend(db, selected_crop, selected_region),
            "last_updated": last_updated,
            "source_name": source_name,
            "source_url": source_url,
            "source": current.get("source", "database"),
            "is_realtime": current.get("is_realtime", False),
            "is_mock": is_mock,
            "cache_status": cache_status,
        }

    def get_price_trend(self, db: Session, crop_name: str = "lua", region: str = "Ha Noi", days: int = 7) -> dict:
        selected_crop = self._clean_crop(crop_name)
        selected_region = self._clean_region(region)

        # Strict spec: only use real cached/DB data from official sources.
        # - No mock
        # - No synthetic/random forecast if not enough real history
        # - If forecast exists, it must be derived deterministically from history
        history = pricing_service.get_price_history(db, selected_crop, selected_region, max(days, 7))
        recent = history[-days:] if history else []

        if not recent:
            return {
                "crop_name": selected_crop,
                "region": selected_region,
                "history": [],
                "forecast": [],
                "estimated": [],
                "trend": None,
                "is_mock": False,
                "source": "database",
                "source_name": "Official price history (PriceHistory DB)",
                "confidence": 0.0,
                "updated_at": datetime.now(),
                "error": "Không thể tải dữ liệu giá realtime/cache cho 7 ngày.",
                "cache_status": "miss",
            }

        if any(item.get("is_mock") for item in recent):
            return {
                "crop_name": selected_crop,
                "region": selected_region,
                "history": recent,
                "forecast": [],
                "estimated": [],
                "trend": None,
                "is_mock": True,
                "source": "database",
                "source_name": "Official price history (PriceHistory DB)",
                "confidence": 0.0,
                "updated_at": datetime.now(),
                "error": "Phát hiện dữ liệu mock trong history. Tối không thể tạo dự báo.",
                "cache_status": "miss",
            }

        trend = pricing_service.analyze_price_trend(db, selected_crop, selected_region)

        # Estimated forecast only if we have enough real points.
        # Requirement: if not enough (6-7 days close) -> only show history.
        have_enough = len(recent) >= 6

        forecast: list[dict] = []
        estimated: list[dict] = []

        if have_enough:
            prices = [float(item.get("avg_price") or 0) for item in recent]

            # Compute deterministic growth rate from last differences.
            diffs = []
            for i in range(1, len(prices)):
                prev = prices[i - 1]
                cur = prices[i]
                if prev != 0:
                    diffs.append((cur - prev) / prev)

            last_diff = diffs[-1] if diffs else 0.0
            avg_diff = sum(diffs[-3:]) / max(len(diffs[-3:]), 1) if diffs else 0.0

            if trend in {"up", "increasing"}:
                growth_rate = (avg_diff + last_diff) / 2
            elif trend in {"down", "decreasing"}:
                growth_rate = (avg_diff + last_diff) / 2
            else:
                growth_rate = avg_diff / 4 if avg_diff else 0.0

            last_price = prices[-1]

            for offset in range(1, days + 1):
                est = float(last_price) * ((1 + growth_rate) ** offset)
                est = round(est, 2)

                conf = "high" if offset <= 3 else "medium"
                item = {
                    "date": (date.today() + timedelta(days=offset)).isoformat(),
                    "estimated_price": est,
                    "predicted_price": est,  # backward compatible for UI fields
                    "forecast_price": est,
                    "min_price": round(est * 0.92, 2),
                    "max_price": round(est * 1.08, 2),
                    "confidence": conf,
                    "trend": "up" if growth_rate >= 0 else "down",
                    "reason_codes": ["price_history_db", "deterministic_estimation"],
                    "source": "estimated_from_history",
                    "source_name": "PriceHistory DB (estimated)",
                    "updated_at": datetime.now(),
                    "is_mock": False,
                    "estimated": True,
                }
                estimated.append(item)

            forecast = estimated

        return {
            "crop_name": selected_crop,
            "region": selected_region,
            "history": recent,
            "forecast": forecast,
            "estimated": estimated,
            "trend": trend,
            "is_mock": False,
            "source": "database",
            "source_name": "Official price history (PriceHistory DB)",
            "confidence": 0.68 if have_enough else 0.42,
            "updated_at": datetime.now(),
            "cache_status": "from_db" if recent else "miss",
            "history_points": len(recent),
            "forecast_status": "estimated" if have_enough else "not_available",
        }


    def get_weather_overview(self, db: Session, region: str = "Ha Noi", force_refresh: bool = False) -> dict:
        selected_region = self._clean_region(region)
        current = weather_service.get_current_weather(db, selected_region, force_refresh=force_refresh)
        forecast = weather_service.get_weather_forecast(db, selected_region, 7)
        alerts = weather_service.generate_alerts(current, forecast)
        return {
            "current": current,
            "forecast": forecast,
            "alerts": alerts,
            "is_mock": bool(current.get("is_mock")) or any(item.get("is_mock") for item in forecast),
            "is_realtime": bool(current.get("is_realtime")),
            "cache_status": current.get("cache_status", "unknown"),
            "last_updated": current.get("last_updated"),
        }

    def get_weather_risk(
        self,
        db: Session,
        region: str = "Ha Noi",
        crop_name: str = "lua",
        growth_stage: str | None = None,
        force_refresh: bool = False,
    ) -> dict:
        current = weather_service.get_current_weather(db, region, force_refresh=force_refresh)
        forecast = weather_service.get_weather_forecast(db, region, 7)
        hourly_bundle = weather_service.get_hourly_forecast(db, region, 168)
        hourly = hourly_bundle.get("forecast", []) if isinstance(hourly_bundle, dict) else hourly_bundle
        if current.get("_api_error") or not forecast:
            return {
                "region": self._clean_region(region),
                "crop_name": self._clean_crop(crop_name),
                "risk_score": 0,
                "risk_level": None,
                "current": current,
                "forecast": forecast if isinstance(forecast, list) else [],
                "hourly_forecast": hourly if isinstance(hourly, list) else [],
                "rain_24h": 0,
                "alerts": [],
                "activity_recommendations": [],
                "source": "realtime_api",
                "source_name": current.get("source_name") or OPEN_METEO_SOURCE_NAME,
                "source_url": current.get("source_url") or OPEN_METEO_FORECAST_URL,
                "is_realtime": False,
                "is_mock": False,
                "cache_status": "miss",
                "fetched_at": current.get("fetched_at"),
                "last_updated": current.get("last_updated"),
                "data_age_minutes": current.get("data_age_minutes"),
                "error": current.get("error_message") or "Weather cache miss.",
            }
        service_risk = weather_service.get_weather_risk(db, region, crop_name)
        if service_risk.get("_api_error"):
            service_risk = {}
        alerts = service_risk.get("alerts") or weather_service.generate_alerts(current, forecast, crop_name=crop_name, growth_stage=growth_stage)
        recommendations = weather_service.build_activity_recommendations(current, forecast, hourly, crop_name, growth_stage)
        risk_score = service_risk.get("risk_score") or self._weather_risk_score(current, forecast, alerts)
        risk_level = service_risk.get("risk_level") or ("high" if risk_score >= 70 else "medium" if risk_score >= 40 else "low")
        rain_24h = round(sum(float(item.get("rainfall") or 0) for item in hourly[:24]), 1)
        return {
            "region": self._clean_region(region),
            "crop_name": self._clean_crop(crop_name),
            "risk_score": risk_score,
            "risk_level": risk_level,
            "current": current,
            "forecast": forecast,
            "hourly_forecast": hourly,
            "rain_24h": rain_24h,
            "alerts": alerts,
            "activity_recommendations": recommendations,
            "ai_recommendation": {
                "provider": "rule_based_ai",
                "summary": "Dữ liệu thời tiết được nạp lại khi mở dashboard, sau đó đọc nhanh từ DB/cache.",
                "risk_explanation": "Risk score được tính từ mưa, UV, gió, độ ẩm và cảnh báo nông vụ hiện có.",
                "action_plan": [item.get("reason") for item in recommendations[:3] if item.get("reason")],
                "data_note": "Dashboard reset sẽ cập nhật dữ liệu API trước khi hiển thị.",
            },
            "source_name": current.get("source_name") or "Weather DB",
            "source_url": current.get("source_url"),
            "is_realtime": current.get("is_realtime", False),
            "is_mock": current.get("is_mock", False),
            "cache_status": current.get("cache_status", "from_db"),
            "fetched_at": current.get("fetched_at"),
            "last_updated": current.get("last_updated"),
            "data_age_minutes": current.get("data_age_minutes"),
        }

    def get_regional_prices(
        self,
        db: Session,
        crop_name: str = "lua",
        regions: list[str] | None = None,
        force_refresh: bool = False,
    ) -> dict:
        selected_crop = self._clean_crop(crop_name)
        if force_refresh:
            price_aggregator_service.refresh_prices(db, crop_name=selected_crop)

        wanted = regions or DEFAULT_REGIONS
        comparison = pricing_service.get_price_comparison(db, selected_crop, wanted)
        regions_data = [
            {
                "region": item.get("region"),
                # `or 0` cu bien gia thieu thanh 0 dong — cung loi voi
                # Number(null)===0 ben frontend. Thieu gia thi de None.
                "price": _gia_hoac_none(item),
                "unit": item.get("unit") or "VND/kg",
                "source": item.get("source"),
                "source_name": item.get("source_name"),
                "source_url": item.get("source_url"),
                "last_updated": item.get("last_updated"),
                "is_mock": bool(item.get("is_mock")),
                "cache_status": item.get("cache_status"),
                "confidence": item.get("confidence"),
            }
            for item in comparison.get("regions", [])
        ]
        return {
            "crop_name": selected_crop,
            "regions": regions_data,
            "cache_status": comparison.get("cache_status", "computed"),
            "source": comparison.get("source"),
            "source_name": comparison.get("source_name"),
            "confidence": comparison.get("confidence"),
        }

    def get_realtime_market(self, db: Session, crop_name: str = "lua", region: str = "Ha Noi", force_refresh: bool = False) -> dict:
        featured = self.get_featured_crop(db, crop_name=crop_name, region=region, force_refresh=force_refresh)
        return {
            "featured_crop": featured,
            "retail_references": [],
            "cache_status": featured.get("cache_status", "from_db"),
            "last_updated": featured.get("last_updated"),
        }

    def get_news(
        self,
        db: Session,
        limit: int = 6,
        crop_name: str | None = None,
        region: str | None = None,
        force_refresh: bool = False,
    ) -> dict:
        if force_refresh:
            market_news_service.refresh_news()
        return market_news_service.get_market_news(db, limit=limit, crop=crop_name, region=region)

    def get_data_health(self, db: Session, region: str = "Ha Noi", crop_name: str = "lua") -> dict:
        weather_count = db.query(WeatherData).filter(
            WeatherData.Region == self._clean_region(region),
            WeatherData.SourceURL.isnot(None),
            WeatherData.FetchedAt.isnot(None),
            WeatherData.IsMock == False,  # noqa: E712
        ).count()
        news_count = db.query(MarketNews).filter(
            MarketNews.SourceURL.isnot(None),
            MarketNews.FetchedAt.isnot(None),
            MarketNews.IsMock == False,  # noqa: E712
        ).count()
        price_count = db.query(MarketPrice).filter(
            MarketPrice.SourceURL.isnot(None),
            MarketPrice.FetchedAt.isnot(None),
            MarketPrice.IsMock == False,  # noqa: E712
        ).count()
        score = min(100, weather_count * 8 + min(news_count, 20) + min(price_count, 20))
        ai_status = "active" if settings.AI_API_KEY or settings.CLAUDE_API_KEY else "not_configured"
        return {
            "score": score,
            "sources": [
                {"name": "Open-Meteo", "status": "active" if weather_count else external_circuit_breaker.status("open_meteo_forecast"), "role": "weather", "source_url": OPEN_METEO_FORECAST_URL},
                {"name": "Gia thi truong nong san Viet Nam", "status": "active" if price_count else external_circuit_breaker.status("thitruongnongsan_price:C\u00e0 ph\u00ea"), "role": "official_price", "source_url": OFFICIAL_PRICE_URL},
                {"name": "Tin tuc thi truong nong san Viet Nam", "status": "active" if news_count else external_circuit_breaker.status("thitruongnongsan_news"), "role": "market_news", "source_url": OFFICIAL_NEWS_URL},
                {"name": "Gia ban le tham khao Viet Nam", "status": "cache" if price_count else "error", "role": "retail_price"},
                {"name": "AI provider", "status": ai_status, "role": "ai"},
                {"name": "Database cache", "status": "active" if (weather_count or news_count or price_count) else "empty", "role": "cache"},
            ],
        }

    def refresh_dashboard(self, db: Session, source: str = "all", region: str = "Ha Noi", crop_name: str = "lua") -> dict:
        selected_region = self._clean_region(region)
        selected_crop = self._clean_crop(crop_name)
        result = {}
        if source in {"weather", "all"}:
            result["weather"] = self._refresh_weather(db, selected_region)
        if source in {"price", "prices", "all"}:
            result["prices"] = price_aggregator_service.refresh_prices(db, crop_name=selected_crop)
        if source in {"news", "all"}:
            result["news"] = market_news_service.refresh_news()
        result["refreshed_at"] = datetime.now()
        return result

    def get_ai_recommendation(self, db: Session, crop_name: str = "lua", region: str = "Ha Noi") -> dict:
        current_price = pricing_service.get_current_price(db, crop_name, region)
        if current_price.get("_api_error"):
            return current_price
        weather = self.get_weather_overview(db, region)
        if weather.get("current", {}).get("_api_error"):
            payload = realtime_error(
                code="DASHBOARD_AI_INPUT_CACHE_MISS",
                message="Dashboard AI recommendation input cache miss.",
                source_name="Dashboard AI recommendation",
                source_url=OPEN_METEO_FORECAST_URL,
            )
            payload.update({"crop_name": crop_name, "region": region})
            return payload
        trend = current_price.get("price_trend", "stable")
        rainy_days = sum(1 for item in weather["forecast"] if float(item.get("rainfall") or 0) >= 5)

        if trend in {"increasing", "up"} and rainy_days <= 2:
            action = "hold"
            title = "Nên giữ hàng"
            confidence = 0.78
            description = "Xu hướng giá đang cải thiện và rủi ro thời tiết ở mức chấp nhận được."
        elif rainy_days >= 4:
            action = "sell_sooner"
            title = "Nên bán sớm hơn"
            confidence = 0.72
            description = "Rủi ro mưa cao, nên giảm thời gian tồn kho để hạn chế hao hụt."
        else:
            action = "sell_in_batches"
            title = "Bán theo nhiều đợt"
            confidence = 0.70
            description = "Tín hiệu thị trường trung tính; chia nhỏ sản lượng giúp giảm rủi ro giá và thời tiết."

        return {
            "crop_name": crop_name,
            "region": region,
            "action": action,
            "title": title,
            "description": description,
            "confidence": confidence,
            "expected_price": round(float(current_price["current_price"]) * 1.02, 2),
            "period": "7 ngày tới",
            "source": "rule_based_ai",
            "is_mock": bool(current_price.get("is_mock")) or weather["is_mock"],
            "last_updated": datetime.now(),
        }

    def _safe_dashboard_call(self, name: str, factory, fallback, statuses: list[dict] | None = None):
        try:
            value = factory()
            if statuses is not None:
                statuses.append({"module": name, "ok": True, "fallback_used": False})
            return value
        except Exception as exc:
            logger.warning("[dashboard] module=%s failed error=%s", name, exc)
            value = fallback() if callable(fallback) else fallback
            if isinstance(value, dict):
                value = {
                    **value,
                    "fallback_used": True,
                    "timeout": "timeout" in str(exc).lower(),
                    "error": str(exc),
                    "source": value.get("source", "realtime_api"),
                    "source_name": value.get("source_name", f"{name} unavailable"),
                    "is_mock": value.get("is_mock", False),
                    "cache_status": value.get("cache_status", "miss"),
                }
            if statuses is not None:
                statuses.append({
                    "module": name,
                    "ok": False,
                    "fallback_used": True,
                    "timeout": "timeout" in str(exc).lower(),
                    "error": str(exc),
                })
            return value

    @staticmethod
    def _fallback_featured_crop(crop_name: str, region: str) -> dict:
        return {
            "name": crop_name,
            "display_name": crop_name.title(),
            "location": region,
            "price": None,
            "unit": "VND/kg",
            "change": None,
            "change_day_pct": None,
            "change_week_pct": None,
            "trend": None,
            "last_updated": datetime.now(),
            "source": "realtime_api",
            "source_name": "Dashboard featured crop",
            "is_mock": False,
            "cache_status": "miss",
            "confidence": 0.0,
            "error": "Không thể tải giá realtime.",
        }

    @staticmethod
    def _fallback_weather_risk(region: str, crop_name: str) -> dict:
        current = {
            "region": region,
            "temperature": None,
            "rainfall": None,
            "humidity": None,
            "source": "realtime_api",
            "source_name": "Dashboard weather",
            "is_mock": False,
            "cache_status": "miss",
            "last_updated": datetime.now(),
        }
        return {
            "region": region,
            "crop_name": crop_name,
            "risk_score": 0,
            "risk_level": None,
            "current": current,
            "forecast": [],
            "hourly_forecast": [],
            "rain_24h": 0,
            "alerts": [],
            "activity_recommendations": [],
            "source": "realtime_api",
            "source_name": "Dashboard weather",
            "is_mock": False,
            "cache_status": "miss",
            "last_updated": datetime.now(),
            "error": "Không thể tải dữ liệu thời tiết realtime.",
        }

    @staticmethod
    def _fallback_weather_overview(weather_risk: dict) -> dict:
        current = weather_risk.get("current", {})
        return {
            "current": current,
            "forecast": weather_risk.get("forecast", []),
            "alerts": weather_risk.get("alerts", []),
            "is_mock": False,
            "is_realtime": False,
            "cache_status": current.get("cache_status", "miss"),
            "last_updated": current.get("last_updated") or datetime.now(),
            "error": current.get("error") or "Không thể tải dữ liệu thời tiết realtime.",
        }

    @staticmethod
    def _fallback_price_trend(crop_name: str, region: str) -> dict:
        return {
            "crop_name": crop_name,
            "region": region,
            "history": [],
            "forecast": [],
            "trend": None,
            "is_mock": False,
            "source": "realtime_api",
            "source_name": "Dashboard price trend",
            "confidence": 0.0,
            "error": "Không thể tải giá realtime.",
            "updated_at": datetime.now(),
        }

    @staticmethod
    def _fallback_news() -> dict:
        return {
            "news": [],
            "source": "realtime_api",
            "source_name": "Dashboard market news",
            "is_mock": False,
            "cache_status": "miss",
            "confidence": 0.0,
            "error": "Không thể tải tin tức thị trường realtime.",
        }

    @staticmethod
    def _fallback_realtime_market(featured: dict) -> dict:
        return {
            "featured_crop": featured,
            "global_references": [],
            "exchange_rate": {},
            "cache_status": featured.get("cache_status", "miss"),
            "last_updated": featured.get("last_updated") or datetime.now(),
            "source": "realtime_api",
            "source_name": "Dashboard realtime market",
            "is_mock": False,
            "error": "Không thể tải dữ liệu thị trường realtime.",
        }

    @staticmethod
    def _compute_ai_recommendation_inline(featured: dict, weather_risk: dict, crop_name: str, region: str) -> dict:
        current_price = float(featured.get("price") or 0)
        trend = featured.get("trend") or "stable"
        rainy_days = sum(1 for item in weather_risk.get("forecast", []) if float(item.get("rainfall") or 0) >= 5)

        if trend in {"increasing", "up"} and rainy_days <= 2:
            action, title, confidence = "hold", "Nên giữ hàng", 0.78
            description = "Xu hướng giá đang cải thiện và rủi ro thời tiết ở mức chấp nhận được."
        elif rainy_days >= 4:
            action, title, confidence = "sell_sooner", "Nên bán sớm hơn", 0.72
            description = "Rủi ro mưa cao, nên giảm thời gian tồn kho để hạn chế hao hụt."
        else:
            action, title, confidence = "sell_in_batches", "Bán theo nhiều đợt", 0.70
            description = "Tín hiệu thị trường trung tính; chia nhỏ sản lượng giúp giảm rủi ro giá và thời tiết."

        return {
            "crop_name": crop_name,
            "region": region,
            "action": action,
            "title": title,
            "description": description,
            "confidence": confidence,
            "expected_price": round(current_price * 1.02, 2) if current_price else None,
            "period": "7 ngày tới",
            "source": "rule_based_ai",
            "is_mock": bool(featured.get("is_mock")) or bool(weather_risk.get("is_mock")),
            "last_updated": datetime.now(),
        }

    @staticmethod
    def _fallback_ai_recommendation(crop_name: str, region: str) -> dict:
        return {
            "crop_name": crop_name,
            "region": region,
            "action": "review",
            "title": "Không thể tải gợi ý AI",
            "description": "Không thể tạo khuyến nghị realtime. Vui lòng thử lại sau.",
            "confidence": 0.0,
            "expected_price": None,
            "period": "hôm nay",
            "source": "realtime_api",
            "source_name": "Dashboard AI",
            "is_mock": False,
            "error": "Không thể tải gợi ý AI realtime.",
            "last_updated": datetime.now(),
        }

    @staticmethod
    def _realtime_only() -> bool:
        from app.core.config import settings

        return bool(settings.USE_REALTIME_ONLY) and not bool(settings.ALLOW_MOCK_DATA or settings.ALLOW_SAMPLE_DATA)

    def _delete_dashboard_realtime_data(self, db: Session, region: str, crop_name: str) -> None:
        try:
            crop = ensure_crop(db, crop_name)
            today = date.today()
            db.query(MarketNews).delete(synchronize_session=False)
            db.query(MarketPrice).filter(
                MarketPrice.CropID == crop.CropID,
                or_(MarketPrice.SourceURL.is_not(None), MarketPrice.Region == "Global Futures"),
            ).delete(synchronize_session=False)
            db.query(WeatherData).filter(
                WeatherData.Region == region,
                WeatherData.RecordDate >= today,
                WeatherData.RecordDate <= today + timedelta(days=7),
            ).delete(synchronize_session=False)
            db.query(WeatherObservation).filter(WeatherObservation.Region == region).delete(synchronize_session=False)
            db.commit()
            redis_client.delete("market_news:latest")
            redis_client.delete("market_news:latest:agriculture")
            for limit in (4, 6, 20):
                redis_client.delete(f"market_news:latest:agriculture:{limit}")
            try:
                for key in redis_client.scan_iter(f"dashboard:summary:{region}:{crop_name}:*"):
                    redis_client.delete(key)
            except Exception:
                pass
        except Exception:
            db.rollback()

    def _refresh_weather_in_new_session(self, region: str) -> dict:
        db = SessionLocal()
        try:
            return self._refresh_weather(db, region)
        finally:
            db.close()

    def _refresh_prices_in_new_session(self, crop_name: str) -> dict:
        db = SessionLocal()
        try:
            return price_aggregator_service.refresh_prices(db, crop_name=crop_name)
        finally:
            db.close()

    def _refresh_weather(self, db: Session, region: str) -> dict:
        today = date.today()
        deleted_weather = (
            db.query(WeatherData)
            .filter(WeatherData.Region == region, WeatherData.RecordDate >= today, WeatherData.RecordDate <= today + timedelta(days=7))
            .delete(synchronize_session=False)
        )
        deleted_observations = db.query(WeatherObservation).filter(WeatherObservation.Region == region).delete(synchronize_session=False)
        current = self.weather_client.get_current(region)
        forecast = self.weather_client.get_forecast(region, days=7)

        observation = WeatherObservation(
            Region=region,
            ObservedAt=current.get("source_updated_at") or datetime.now(),
            Temperature=current.get("temperature"),
            Humidity=current.get("humidity"),
            Rainfall=current.get("rainfall"),
            WindSpeed=current.get("wind_speed"),
            UVIndex=current.get("uv_index"),
            Pressure=current.get("pressure"),
            WeatherCode=current.get("weather_code"),
            WeatherDesc=current.get("condition"),
            SourceName=current.get("source_name") or "Open-Meteo",
            SourceURL=current.get("source_url") or OPEN_METEO_FORECAST_URL,
            SourceUpdatedAt=current.get("source_updated_at"),
            FetchedAt=datetime.now(),
            IsRealtime=True,
            IsMock=False,
        )
        db.add(observation)

        for item in forecast:
            record_date = date.fromisoformat(str(item["date"])[:10])
            db.add(
                WeatherData(
                    Region=region,
                    RecordDate=record_date,
                    TempMin=item.get("temp_min"),
                    TempMax=item.get("temp_max"),
                    Humidity=item.get("humidity"),
                    Rainfall=item.get("rainfall"),
                    WeatherDesc=item.get("condition"),
                    Latitude=current.get("latitude"),
                    Longitude=current.get("longitude"),
                    WindSpeed=item.get("wind_speed"),
                    UVIndex=item.get("uv_index"),
                    WeatherCode=item.get("weather_code"),
                    SourceName=item.get("source_name") or "Open-Meteo",
                    SourceURL=item.get("source_url") or OPEN_METEO_FORECAST_URL,
                    SourceUpdatedAt=item.get("last_updated") or datetime.now(),
                    FetchedAt=datetime.now(),
                    IsRealtime=True,
                    IsMock=False,
                )
            )
        db.commit()
        return {
            "cache_status": "refreshed",
            "saved_daily_rows": len(forecast),
            "saved_observations": 1,
            "deleted": {"weather_data": deleted_weather, "observations": deleted_observations},
        }

    def _latest_market_price_for_crop(self, db: Session, crop_name: str, region: str | None = None) -> MarketPrice | None:
        try:
            crop = ensure_crop(db, crop_name)
            query = db.query(MarketPrice).filter(MarketPrice.CropID == crop.CropID)
            if region:
                query = query.filter(MarketPrice.Region == region)
            return query.order_by(desc(MarketPrice.PriceDate), desc(MarketPrice.UpdatedAt)).first()
        except SQLAlchemyError:
            db.rollback()
            return None

    def _current_weather_from_db(self, db: Session, region: str) -> dict | None:
        row = (
            db.query(WeatherData)
            .filter(WeatherData.Region == region, WeatherData.RecordDate <= date.today())
            .order_by(desc(WeatherData.RecordDate), desc(WeatherData.CreatedAt))
            .first()
        )
        if not row:
            return None
        temp = row.temperature
        updated = row.SourceUpdatedAt or row.CreatedAt or datetime.now()
        return {
            "region": row.Region,
            "temperature": float(temp) if temp is not None else None,
            "temp_min": float(row.TempMin) if row.TempMin is not None else None,
            "temp_max": float(row.TempMax) if row.TempMax is not None else None,
            "rainfall": float(row.Rainfall) if row.Rainfall is not None else 0,
            "humidity": float(row.Humidity) if row.Humidity is not None else None,
            "condition": row.WeatherDesc,
            "wind_speed": float(row.WindSpeed) if row.WindSpeed is not None else None,
            "uv_index": float(row.UVIndex) if row.UVIndex is not None else None,
            "pressure": float(row.Pressure) if row.Pressure is not None else None,
            "weather_code": row.WeatherCode,
            "source_name": row.SourceName or "Open-Meteo",
            "source_url": "https://open-meteo.com",
            "is_realtime": False,
            "is_mock": False,
            "last_updated": updated,
            "cache_status": "from_db",
        }

    def _weather_forecast_from_db(self, db: Session, region: str, days: int) -> list[dict]:
        rows = (
            db.query(WeatherData)
            .filter(
                WeatherData.Region == region,
                WeatherData.RecordDate >= date.today(),
                WeatherData.RecordDate <= date.today() + timedelta(days=days),
            )
            .order_by(WeatherData.RecordDate)
            .all()
        )
        result = []
        for row in rows[:days]:
            temp = row.temperature
            result.append(
                {
                    "date": row.RecordDate.isoformat(),
                    "temperature": float(temp) if temp is not None else None,
                    "temp_min": float(row.TempMin) if row.TempMin is not None else None,
                    "temp_max": float(row.TempMax) if row.TempMax is not None else None,
                    "humidity": float(row.Humidity) if row.Humidity is not None else None,
                    "rainfall": float(row.Rainfall) if row.Rainfall is not None else 0,
                    "condition": row.WeatherDesc,
                    "wind_speed": float(row.WindSpeed) if row.WindSpeed is not None else None,
                    "uv_index": float(row.UVIndex) if row.UVIndex is not None else None,
                    "source_name": row.SourceName or "Open-Meteo",
                    "is_mock": False,
                    "cache_status": "from_db",
                }
            )
        return result

    @staticmethod
    def _weather_risk_score(current: dict, forecast: list[dict], alerts: list[dict]) -> int:
        score = 0
        temp = float(current.get("temperature") or 0)
        humidity = float(current.get("humidity") or 0)
        wind = float(current.get("wind_speed") or 0)
        uv = float(current.get("uv_index") or 0)
        rain_total = sum(float(item.get("rainfall") or 0) for item in forecast[:3])
        if temp >= 35:
            score += 25
        if humidity >= 88:
            score += 15
        if wind >= 25:
            score += 15
        if uv >= 8:
            score += 10
        if rain_total >= 40:
            score += 25
        score += min(20, len(alerts) * 5)
        return min(100, int(score))

    @staticmethod
    def _clean_region(region: str | None) -> str:
        return (region or "Ha Noi").strip() or "Ha Noi"

    @staticmethod
    def _clean_crop(crop_name: str | None) -> str:
        return (crop_name or "lua").strip().lower() or "lua"

    @staticmethod
    def _display_crop(crop_name: str) -> str:
        labels = {"lua": "Lúa", "gao": "Gạo", "ca phe": "Cà phê", "ho tieu": "Hồ tiêu"}
        return labels.get(crop_name, crop_name.title())

    @staticmethod
    def _get_user(db: Session, user_id: int | None) -> User | None:
        if not user_id:
            return None
        try:
            return db.query(User).filter(User.UserID == user_id).first()
        except Exception:
            return None

    @staticmethod
    def _pct_change(current: float, previous: float | None) -> float:
        if not previous:
            return 0.0
        return round(((float(current) - float(previous)) / float(previous)) * 100, 1)

    @staticmethod
    def _format_pct(value: float) -> str:
        return f"{value:+.1f}%"


dashboard_service = DashboardService()
