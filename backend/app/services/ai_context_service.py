import logging
from concurrent.futures import (ThreadPoolExecutor, TimeoutError,
                                as_completed)

from sqlalchemy.orm import Session

from app.services.agri_data_aggregator_service import agri_data_aggregator_service
from app.services.data_source_service import data_source_service
from app.services.ai_intent_service import normalize_intent
from app.services.pricing_service import pricing_service

logger = logging.getLogger(__name__)


class AIContextService:

    # Ngan sach cho toan bo viec dung context.
    NGAN_SACH_GIAY = 3.5

    def _chay_trong_ngan_sach(self, viec: dict) -> dict:
        """Chay cac nguon song song, cat theo ngan sach.

        Nguon nao khong kip thi giu gia tri mac dinh — co cache thi tra loi
        bang cache, khong co thi noi that. Tuyet doi khong de mot nguon cham
        chan ca cau tra loi cho nong dan.
        """
        if not viec:
            return {}

        ket_qua = {ten: mac_dinh for ten, (_, mac_dinh) in viec.items()}
        with ThreadPoolExecutor(max_workers=len(viec)) as pool:
            futures = {pool.submit(self._safe, ham, ten): ten
                       for ten, (ham, _) in viec.items()}
            try:
                for f in as_completed(futures, timeout=self.NGAN_SACH_GIAY):
                    try:
                        ket_qua[futures[f]] = f.result()
                    except Exception:
                        pass
            except TimeoutError:
                cham = [t for f, t in futures.items() if not f.done()]
                logger.warning(
                    "[ai-context] het ngan sach %.1fs, bo qua nguon cham: %s",
                    self.NGAN_SACH_GIAY, cham,
                )
            for f in futures:
                f.cancel()
        return ket_qua


    def build_ai_context(
        self,
        db: Session,
        *,
        user_id: int | None = None,
        region: str | None = None,
        crop: str | None = None,
        intent: str | None = None,
    ) -> dict:
        selected_region = (region or "Ha Noi").strip() or "Ha Noi"
        selected_crop = (crop or "lua").strip().lower() or "lua"
        selected_intent = normalize_intent(intent)

        needs_all = selected_intent == "full_farm_analysis"
        needs_weather = selected_intent in {"weather_analysis", "alert_analysis"} or needs_all
        needs_pricing = selected_intent == "price_analysis" or needs_all
        needs_market = selected_intent == "price_analysis" or needs_all
        needs_alerts = selected_intent == "alert_analysis" or needs_all
        needs_quality = selected_intent == "quality_analysis" or needs_all
        needs_harvest = selected_intent == "harvest_analysis" or needs_all
        needs_settings = needs_all

        # 5 nguon duoi day doc lap nhau. Truoc kia goi noi duoi nen /api/chat
        # mat 8.2s ngay ca khi crawler nen da tat: moi nguon cham timeout
        # 3.18s va cong don. Chay song song kem ngan sach — nguon nao khong
        # kip thi dung mac dinh, khong chan cau tra loi (TOD0 §4).
        viec = {}
        if needs_weather:
            viec["weather"] = (
                lambda: agri_data_aggregator_service.get_weather_bundle(
                    db, region=selected_region, crop=selected_crop), {})
        if needs_pricing:
            viec["pricing"] = (
                lambda: agri_data_aggregator_service.get_pricing_bundle(
                    db, crop=selected_crop, region=selected_region), {})
            viec["market_analysis"] = (
                lambda: pricing_service.analyze_market(
                    db, crop_name=selected_crop, region=selected_region,
                    quantity=1000, quality_grade="grade_2"), {})
        if needs_market:
            viec["market"] = (
                lambda: agri_data_aggregator_service.get_market_bundle(
                    db, crop=selected_crop, region=selected_region), {})
        if needs_alerts:
            viec["alerts"] = (
                lambda: agri_data_aggregator_service.get_alert_notification_bundle(
                    db, user_id=user_id, crop=selected_crop,
                    region=selected_region), {})

        thu = self._chay_trong_ngan_sach(viec)
        weather_bundle = thu.get("weather", {})
        pricing_bundle = thu.get("pricing", {})
        market_bundle = thu.get("market", {})
        market_analysis = thu.get("market_analysis", {})
        alert_bundle = thu.get("alerts", {})

        quality_history = agri_data_aggregator_service.get_quality_history(db, user_id) if needs_quality else []
        harvest_status = agri_data_aggregator_service.get_harvest_status(db, user_id) if needs_harvest else {}
        settings = agri_data_aggregator_service.get_user_settings(db, user_id) if needs_settings else {}
        include_weather_details = selected_intent == "weather_analysis" or needs_all

        context = {
            "intent": selected_intent,
            "region": selected_region,
            "crop_name": selected_crop,
            "crop": selected_crop,
            "weather": weather_bundle.get("current", {}) if include_weather_details else {},
            "weather_risk": weather_bundle.get("risk", {}),
            "weather_forecast": weather_bundle.get("forecast", []) if include_weather_details else [],
            "farming_recommendation": weather_bundle.get("recommendation", {}) if include_weather_details else {},
            "pricing": pricing_bundle.get("current", {}),
            "price_history": pricing_bundle.get("history", []),
            "price_forecast": pricing_bundle.get("forecast", {}),
            "price_recommendation": pricing_bundle.get("recommendation", {}),
            "market": {
                "news": market_bundle.get("news", []),
                "trends": market_bundle.get("trends", {}),
                "opportunities": market_bundle.get("opportunities", []),
                "risks": market_bundle.get("risks", []),
            },
            "market_analysis": market_analysis,
            "pricing_analysis": market_analysis,
            "quality_history": quality_history,
            "harvest_status": harvest_status,
            "alerts": alert_bundle.get("alerts", []),
            "notifications": alert_bundle.get("notifications", {}),
            "settings": settings,
        }
        context["data_sources"] = data_source_service.collect_data_sources(context)
        tools_used = []
        if needs_weather:
            tools_used.append("weather_service")
        if needs_pricing:
            tools_used.append("pricing_service")
        if needs_market:
            tools_used.append("market_news_service")
        if needs_alerts:
            tools_used.extend(["alert_service", "notification_center_service"])
        if needs_quality:
            tools_used.append("quality_service")
        if needs_harvest:
            tools_used.append("harvest_service")
        if needs_settings:
            tools_used.append("settings_service")
        context["tools_used"] = tools_used
        return context

    @staticmethod
    def _safe(factory, key: str) -> dict:
        try:
            return factory()
        except Exception as exc:
            return {
                "error": str(exc),
                "source": "realtime_api",
                "source_name": f"{key} realtime context",
                "is_mock": False,
                "fallback_used": False,
                "timeout": "timeout" in str(exc).lower(),
                "confidence": 0.0,
            }


ai_context_service = AIContextService()
