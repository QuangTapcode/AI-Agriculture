import logging
from datetime import date, datetime, timedelta

from sqlalchemy import desc, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.alert import AlertNotification, PriceAlert
from app.models.crop import Crop
from app.models.notification import Notification, NotificationDelivery
from app.models.price import MarketPrice, PriceHistory
from app.models.user import User
from app.models.weather import WeatherAlert
from app.core.real_data import cache_status_for
from app.repositories.common import normalize_text
from app.repositories.alert_repository import (
    create_alert,
    deactivate_alert,
    get_alert_by_id,
    get_alert_crop_name,
    get_alert_receiver,
    get_alerts,
)
from app.repositories.common import ensure_user, to_api_alert_condition
from app.schemas.alert_schema import AlertCreateRequest
from app.schemas.notification_schema import NotificationCreate
from app.services.location_service import location_service
from app.services.notification_center_service import notification_center_service
from app.services.notification_service import notification_service
from app.services.pricing_service import pricing_service
from app.services.weather_service import weather_service

logger = logging.getLogger(__name__)

ALERT_COOLDOWN = timedelta(minutes=30)
WEATHER_CONDITIONS = {
    "rainfall": {"label": "Mưa lớn 24h tới", "unit": "mm", "epsilon": 0.5},
    "temperature": {"label": "Nhiệt độ vượt ngưỡng", "unit": "°C", "epsilon": 0.5},
    "wind": {"label": "Gió mạnh", "unit": "km/h", "epsilon": 1.0},
    "humidity": {"label": "Độ ẩm cao", "unit": "%", "epsilon": 1.0},
    "air_quality": {"label": "Chỉ số UV cao", "unit": "UV", "epsilon": 0.5},
}


# Nhãn mức rủi ro và lời khuyên tương ứng, dùng cho cảnh báo gửi nông dân.
def region_display(region: str | None) -> str:
    """Tên vùng dạng hiển thị, có dấu tiếng Việt.

    Bên trong hệ thống dùng dạng không dấu để so khớp, nhưng chuỗi đưa ra
    màn hình phải có dấu — nếu không cảnh báo hiện "tại Dak Lak" trong khi
    mọi chỗ khác là "Đắk Lắk". Dùng lại bảng alias của pricing_service để
    không sinh ra nguồn sự thật thứ hai.
    """
    from app.services.pricing_service import REGION_DISPLAY_ALIASES

    raw = " ".join((region or "").strip().split())
    if not raw:
        return raw
    return REGION_DISPLAY_ALIASES.get(normalize_text(raw), raw)


_RISK_LABEL_VI = {
    "low": "Rủi ro thấp",
    "medium": "Cảnh báo",
    "high": "Rủi ro cao",
}

_RISK_MESSAGE_VI = {
    "low": "Thời tiết thuận lợi. Có thể tưới, phun thuốc và thu hoạch theo lịch thường.",
    "medium": "Thời tiết có biến động. Nên xem kỹ dự báo trước khi tưới, phun thuốc hoặc thu hoạch.",
    "high": "Thời tiết bất lợi. Hoãn phun thuốc và thu hoạch, kiểm tra thoát nước cho vườn.",
}


class AlertService:
    def create_price_alert(self, db: Session, request: AlertCreateRequest, user: User | None = None) -> dict:
        region = location_service.resolve_region(db, request.region_key or request.region)
        crop_name = request.crop_name
        if not crop_name and request.crop_id:
            crop = db.query(Crop).filter(Crop.CropID == request.crop_id).first()
            crop_name = crop.CropName if crop else None

        alert = create_alert(
            db,
            crop_id=request.crop_id,
            crop_name=crop_name,
            user_id=user.UserID if user else request.user_id,
            region=region,
            target_price=request.target_price,
            condition=request.condition,
            notification_channel=request.notification_channel,
            receiver=request.receiver,
            is_active=True,
        )
        current = self._current_price_for_alert(db, alert, get_alert_crop_name(db, alert))
        confirmation = self._send_registration_confirmation(db, alert, current)
        response = self._to_response(db, alert, "Tạo cảnh báo giá thành công.")
        response["confirmation_delivery"] = confirmation
        if confirmation and confirmation.get("status") in {"sent", "stored"}:
            response["message"] = f"Đã đăng ký cảnh báo và gửi email xác nhận tới {confirmation.get('receiver') or 'người nhận'}."
        elif confirmation and confirmation.get("status") in {"failed", "error", "missing_token"}:
            response["message"] = "Đã đăng ký cảnh báo, nhưng chưa thể gửi xác nhận realtime qua kênh thông báo."
        return response

    def list_price_alerts(self, db: Session, user: User | None = None) -> list[dict]:
        price_alerts = [
            self._to_response(
                db,
                alert,
                "Cảnh báo đang hoạt động." if alert.is_active else "Cảnh báo đã tắt.",
            )
            for alert in get_alerts(db, user_id=user.UserID if user else None)
        ]
        return price_alerts + self.list_weather_alerts(db, user)

    def get_active_alerts(
        self,
        db: Session,
        user_id: int | None = None,
        crop: str | None = None,
        region: str | None = None,
    ) -> list[dict]:
        user = db.query(User).filter(User.UserID == user_id).first() if user_id else None
        alerts = self.list_price_alerts(db, user)
        normalized_crop = (crop or "").strip().lower()
        normalized_region = (region or "").strip().lower()
        filtered = []
        for alert in alerts:
            if normalized_crop and normalized_crop not in str(alert.get("crop_name") or alert.get("crop") or "").lower():
                continue
            if normalized_region and normalized_region not in str(alert.get("region") or "").lower():
                continue
            filtered.append(
                {
                    **alert,
                    "related_alert_id": alert.get("alert_id"),
                    "severity": alert.get("severity") or "medium",
                    "priority": alert.get("priority") or "medium",
                    "suggested_action": alert.get("recommended_action") or alert.get("recommendation"),
                    "action_required": (alert.get("severity") or "medium") in {"high", "urgent"},
                    "source": alert.get("source") or "database",
                    "source_name": alert.get("source_name") or "Alert rules DB",
                    "confidence": alert.get("confidence", 0.7),
                }
            )
        return filtered

    def evaluate_alert_rules(self, db: Session, context: dict, user: User | None = None) -> list[dict]:
        triggered = self.check_and_trigger_alerts(db, user)
        triggered.extend(self.check_and_trigger_weather_alerts(db, user))
        return triggered

    def auto_generate_alerts(self, db: Session, context: dict, user: User | None = None) -> dict:
        region = context.get("region") or (user.Region if user and user.Region else "Ha Noi")
        crop_name = context.get("crop_name") or context.get("crop") or "lua"
        weather_risk = weather_service.get_weather_risk(db, region, crop_name)
        risk_level = weather_risk.get("risk_level", "low")
        alerts = [
            {
                "alert_type": "weather",
                # Nội dung gửi thẳng tới nông dân nên phải là tiếng Việt ngay
                # từ nguồn. Trước đây sinh tiếng Anh rồi trông chờ frontend
                # dịch, kết quả ra câu lai "Thời tiết risk high in Dak Lak".
                "title": f"{_RISK_LABEL_VI.get(risk_level, 'Rủi ro')} thời tiết tại {region_display(region)}",
                "message": _RISK_MESSAGE_VI.get(risk_level, _RISK_MESSAGE_VI["low"]),
                "severity": risk_level,
                "priority": "high" if risk_level == "high" else "medium",
                "suggested_action": "; ".join(weather_risk.get("reasons", [])[:2]),
                "action_required": risk_level == "high",
                "crop_name": crop_name,
                "region": region,
                "source": "ai_generated" if not weather_risk.get("is_mock") else "mock",
                "source_name": "Alert auto-generation rules",
                "confidence": weather_risk.get("confidence", 0.0),
            }
        ]
        return {
            "alerts": alerts,
            "total": len(alerts),
            "source": alerts[0]["source"],
            "source_name": "Alert auto-generation rules",
            "confidence": alerts[0]["confidence"],
            "is_mock": weather_risk.get("is_mock", False),
        }

    def send_alert(self, db: Session, alert_id: int, channels: list[str], user: User | None = None) -> dict:
        alert = self.get_price_alert(db, alert_id)
        if alert is None:
            return {"alert_id": alert_id, "sent": 0, "failed": 0, "deliveries": [], "source": "database"}
        deliveries = []
        for channel in channels or ["app"]:
            result = notification_service.send(
                channel=channel,
                receiver=alert.get("receiver") or (user.Email if user and channel == "email" else None),
                subject=alert.get("title") or f"Alert {alert_id}",
                message=alert.get("message") or "AgriAI alert",
            ) if channel != "app" else {"channel": "app", "status": "stored", "message_id": None, "error": None}
            deliveries.append(result)
        return {
            "alert_id": alert_id,
            "deliveries": deliveries,
            "sent": sum(1 for item in deliveries if item.get("status") in {"sent", "stored"}),
            "failed": sum(1 for item in deliveries if item.get("status") in {"failed", "error"}),
            "source": "database",
            "source_name": "Alert send dispatcher",
            "confidence": 0.7,
        }

    def create_notification_from_alert(self, db: Session, alert: dict, user: User) -> dict:
        return notification_center_service.create_notification(
            db,
            NotificationCreate(
                user_id=user.UserID,
                type=alert.get("alert_type") or "alert",
                title=alert.get("title") or "AgriAI alert",
                message=alert.get("message") or alert.get("suggested_action") or "Alert requires review.",
                priority=alert.get("priority") or alert.get("severity") or "medium",
                channel="app",
                related_entity_type="alert",
                related_entity_id=alert.get("alert_id") or alert.get("related_alert_id"),
            ),
        )

    def get_price_alert(self, db: Session, alert_id: int) -> dict | None:
        alert = get_alert_by_id(db, alert_id)
        if not alert:
            return None
        status_msg = "Cảnh báo đang hoạt động." if alert.is_active else "Cảnh báo đã tắt."
        return self._to_response(db, alert, status_msg)

    def deactivate_price_alert(self, db: Session, alert_id: int) -> dict | None:
        alert = deactivate_alert(db, alert_id)
        if not alert:
            return None
        return {"alert_id": alert.id, "message": "Đã tắt cảnh báo giá."}

    def get_options(self, db: Session, user: User | None = None) -> dict:
        crops = [
            {
                "crop_id": crop.CropID,
                "crop_name": crop.CropName,
                "category": crop.Category,
                "typical_price_min": crop.TypicalPriceMin,
                "typical_price_max": crop.TypicalPriceMax,
            }
            for crop in db.query(Crop).order_by(Crop.CropName).all()
        ]
        if not crops:
            crops = [
                {"crop_id": None, "crop_name": name, "category": "fallback", "typical_price_min": None, "typical_price_max": None}
                for name in sorted(pricing_service.crop_base_prices.keys())
            ]

        channels = [
            {"value": "app", "label": "Trong ứng dụng"},
            {"value": "email", "label": "Email"},
            {"value": "zalo", "label": "Zalo"},
            {"value": "sms", "label": "SMS"},
        ]
        rule_types = [
            {"value": "above", "label": "Giá trên ngưỡng", "unit": "VND/kg"},
            {"value": "below", "label": "Giá dưới ngưỡng", "unit": "VND/kg"},
            {"value": "percent_change", "label": "Biến động phần trăm", "unit": "%"},
            {"value": "weather_rain", "label": "Mưa lớn 24h tới", "unit": "mm"},
            {"value": "weather_heat", "label": "Nhiệt độ vượt ngưỡng", "unit": "°C"},
            {"value": "air_quality", "label": "PM2.5/PM10 cao", "unit": "AQI"},
        ]
        return {
            "crops": crops,
            "regions": location_service.list_locations(db),
            "rule_types": rule_types,
            "channels": channels,
            "default_region": user.Region if user and user.Region else "Hà Nội",
        }

    def get_suggestions(
        self,
        db: Session,
        *,
        crop_name: str | None = None,
        crop_id: int | None = None,
        region: str | None = None,
        region_key: str | None = None,
    ) -> dict:
        crop = db.query(Crop).filter(Crop.CropID == crop_id).first() if crop_id else None
        resolved_crop = crop.CropName if crop else (crop_name or "Nông sản")
        resolved_region = location_service.resolve_region(db, region_key or region)
        current = pricing_service.get_current_price(db, resolved_crop, resolved_region, include_weather=False)
        if current.get("_api_error"):
            return {
                **current,
                "alerts": [],
                "suggestions": [],
                "recommended_action": None,
            }
        price = float(current["current_price"])
        history_rows = self._recent_history(db, crop.CropID if crop else None, resolved_crop, resolved_region)
        avg_7d = sum(history_rows) / len(history_rows) if history_rows else price
        change_pct = ((price - avg_7d) / avg_7d * 100) if avg_7d else 0
        return {
            "crop_name": resolved_crop,
            "region": resolved_region,
            "current_price": price,
            "avg_7d": round(avg_7d, 2),
            "change_pct": round(change_pct, 2),
            "suggestions": [
                {
                    "rule_type": "above",
                    "label": "Báo khi giá tăng mạnh",
                    "target_price": round(price * 1.08, 0),
                    "reason": "Cao hơn giá hiện tại khoảng 8%, phù hợp theo dõi cơ hội bán.",
                },
                {
                    "rule_type": "below",
                    "label": "Báo khi giá giảm",
                    "target_price": round(price * 0.92, 0),
                    "reason": "Thấp hơn giá hiện tại khoảng 8%, hữu ích để phòng rủi ro.",
                },
                {
                    "rule_type": "percent_change",
                    "label": "Báo biến động 24h",
                    "threshold_percent": 5,
                    "reason": f"Giá hiện lệch {round(change_pct, 1)}% so với trung bình gần đây.",
                },
            ],
        }

    def check_and_trigger_alerts(self, db: Session, user: User | None = None) -> list[dict]:
        try:
            query = db.query(PriceAlert).filter(PriceAlert.IsActive == True)
            if user:
                query = query.filter(PriceAlert.UserID == user.UserID)
            alerts = query.all()
        except Exception as exc:
            logger.warning("Cannot load active price alerts: %s", exc)
            return []

        triggered = []
        for alert in alerts:
            result = self._evaluate_alert(db, alert)
            if result:
                triggered.append(result)
        return triggered

    def get_trigger_history(self, db: Session, user: User | None = None, limit: int = 50) -> dict:
        query = db.query(AlertNotification, PriceAlert).join(
            PriceAlert,
            AlertNotification.AlertID == PriceAlert.AlertID,
        )
        if user:
            query = query.filter(PriceAlert.UserID == user.UserID)
        rows = query.order_by(desc(AlertNotification.SentAt)).limit(limit).all()
        events = []
        for event, alert in rows:
            crop_name = get_alert_crop_name(db, alert)
            region = location_service.display_name(alert.Region)
            message = event.Message or ""
            if self._looks_mojibake(message) or self._looks_incomplete_history(message):
                message = self._history_message(crop_name, region, event.CurrentPrice, alert.TargetPrice)
            events.append(
                {
                    "event_id": event.NotificationID,
                    "alert_id": event.AlertID,
                    "crop_name": crop_name,
                    "region": region,
                    "condition": to_api_alert_condition(alert.AlertType),
                    "target_price": float(alert.TargetPrice),
                    "current_price": float(event.CurrentPrice or 0),
                    "message": message,
                    "channel": (event.Channel or event.NotifyMethod or alert.NotifyMethod or "app").lower(),
                    "receiver": event.Receiver,
                    "status": event.Status or event.SendStatus,
                    "provider_message_id": event.ProviderMessageID,
                    "error_message": self._delivery_error_message(event.ErrorMessage),
                    "triggered_at": event.SentAt,
                }
            )

        weather_query = db.query(Notification, WeatherAlert).join(
            WeatherAlert,
            Notification.RelatedEntityID == WeatherAlert.AlertID,
        ).filter(
            Notification.RelatedEntityType == "weather_alert",
            Notification.IsDeleted == False,
        )
        if user:
            weather_query = weather_query.filter(Notification.UserID == user.UserID)
        weather_rows = weather_query.order_by(desc(Notification.CreatedAt)).limit(limit).all()
        for notification, alert in weather_rows:
            delivery = self._preferred_delivery(db, notification.NotificationID)
            events.append(
                {
                    "event_id": f"weather-{notification.NotificationID}",
                    "alert_id": alert.AlertID,
                    "alert_kind": "weather",
                    "crop_name": "Thời tiết",
                    "region": location_service.display_name(alert.Region),
                    "condition": alert.AlertType,
                    "weather_condition": alert.AlertType,
                    "target_price": float(alert.TriggerValue or 0),
                    "current_price": float(alert.LastValue or 0),
                    "trigger_unit": alert.TriggerUnit or self._weather_condition_meta(alert.AlertType)["unit"],
                    "message": notification.Message,
                    "channel": (delivery.Channel if delivery else notification.Channel or alert.NotifyMethod or "app").lower(),
                    "receiver": delivery.Receiver if delivery else alert.Receiver,
                    "status": (delivery.Status if delivery else "stored"),
                    "provider_message_id": delivery.ProviderMessageID if delivery else None,
                    "error_message": self._delivery_error_message(delivery.ErrorMessage if delivery else None),
                    "triggered_at": notification.CreatedAt,
                }
            )

        events.sort(key=lambda item: item.get("triggered_at") or datetime.min, reverse=True)
        return {"events": events[:limit], "total": len(events)}

    def create_weather_alert(self, db: Session, payload: dict, user: User | None = None) -> dict:
        region = location_service.resolve_region(db, payload.get("region_key") or payload.get("region"))
        condition = payload.get("condition") or "rainfall"
        threshold = float(payload.get("threshold") or 0)
        meta = self._weather_condition_meta(condition)
        channel = (payload.get("notification_channel") or "email").lower()
        receiver = (payload.get("receiver") or "").strip()
        owner = user or ensure_user(db, receiver=receiver, region=region)
        if not receiver:
            receiver = self._default_receiver(owner, channel)
        current = weather_service.get_current_weather(db, region)
        current_value = self._weather_value(current, condition)
        title = payload.get("title") or f"Cảnh báo {meta['label'].lower()} tại {region}"
        message = payload.get("message") or f"Theo dõi {meta['label'].lower()} với ngưỡng {threshold:g} {meta['unit']}."
        row = WeatherAlert(
            UserID=owner.UserID,
            Region=region,
            AlertType=condition,
            Severity=payload.get("severity") or "medium",
            Title=title,
            Message=message,
            Recommendation=payload.get("recommendation") or "Theo dõi dự báo và điều chỉnh lịch nông vụ.",
            TriggerValue=threshold,
            TriggerUnit=payload.get("unit") or meta["unit"],
            Source="manual_subscription",
            DedupKey=f"manual:{owner.UserID}:{location_service.region_key(region)}:{condition}:{threshold:g}",
            NotifyMethod=self._db_channel(channel),
            Receiver=receiver,
            LastValue=current_value,
            IsActive=True,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        confirmation = self._send_weather_registration_confirmation(db, row, current, current_value)
        response = self._weather_to_response(row, "Đã tạo cảnh báo thời tiết.")
        response["confirmation_delivery"] = confirmation
        if confirmation and confirmation.get("status") == "sent":
            response["message"] = f"Đã tạo cảnh báo thời tiết và gửi email xác nhận tới {confirmation.get('receiver') or receiver}."
        elif confirmation and confirmation.get("status") in {"failed", "error", "missing_token"}:
            response["message"] = "Đã tạo cảnh báo thời tiết, nhưng chưa thể gửi xác nhận realtime qua kênh thông báo."
        return response

    def list_weather_alerts(self, db: Session, user: User | None = None) -> list[dict]:
        query = db.query(WeatherAlert).filter(
            WeatherAlert.Source == "manual_subscription",
            WeatherAlert.IsActive == True,
        )
        if user:
            query = query.filter(WeatherAlert.UserID == user.UserID)
        return [
            self._weather_to_response(alert, "Cảnh báo thời tiết đang hoạt động.")
            for alert in query.order_by(desc(WeatherAlert.CreatedAt)).all()
        ]

    def deactivate_weather_alert(self, db: Session, alert_id: int) -> dict | None:
        alert = db.query(WeatherAlert).filter(WeatherAlert.AlertID == alert_id).first()
        if not alert:
            return None
        alert.IsActive = False
        db.add(alert)
        db.commit()
        return {
            "alert_id": alert.AlertID,
            "message": "Đã tắt cảnh báo thời tiết.",
        }

    def check_and_trigger_weather_alerts(self, db: Session, user: User | None = None) -> list[dict]:
        query = db.query(WeatherAlert).filter(
            WeatherAlert.Source == "manual_subscription",
            WeatherAlert.IsActive == True,
        )
        if user:
            query = query.filter(WeatherAlert.UserID == user.UserID)
        triggered = []
        for alert in query.all():
            result = self._evaluate_weather_alert(db, alert)
            if result:
                triggered.append(result)
        return triggered

    def _send_alert_notification(
        self,
        db: Session,
        alert: PriceAlert,
        crop_name: str,
        current_price: float,
        target_price: float,
        condition: str,
        message: str,
        *,
        source: dict | None = None,
        previous_price: float | None = None,
    ) -> dict:
        return self._create_notification_records(
            db,
            alert,
            crop_name,
            current_price,
            target_price,
            condition,
            message,
            source=source,
            previous_price=previous_price,
        )

    def _evaluate_alert(self, db: Session, alert: PriceAlert) -> dict | None:
        if isinstance(alert.LastTriggered, datetime) and datetime.now() - alert.LastTriggered < ALERT_COOLDOWN:
            return None

        crop_name = get_alert_crop_name(db, alert)
        current = self._current_price_for_alert(db, alert, crop_name)
        if current is None:
            return None

        current_price = float(current["current_price"])
        target_price = float(alert.TargetPrice)
        condition = to_api_alert_condition(alert.AlertType)
        matched = current_price >= target_price if condition == "above" else current_price <= target_price
        last_price = self._last_recorded_price(db, alert.AlertID)
        price_changed = last_price is None or abs(current_price - last_price) >= 1
        if not matched:
            return None

        direction = "vượt" if condition == "above" else "xuống dưới"
        if price_changed and last_price is not None:
            diff = current_price - last_price
            diff_text = "tăng" if diff > 0 else "giảm"
            message = (
                f"Giá {crop_name} tại {alert.Region} đã {diff_text} từ {last_price:,.0f} "
                f"lên {current_price:,.0f} VND/kg. Ngưỡng theo dõi: {target_price:,.0f} VND/kg."
            )
        else:
            message = (
                f"{crop_name} tại {alert.Region} hiện {current_price:,.0f} VND/kg, "
                f"đã {direction} ngưỡng {target_price:,.0f} VND/kg."
            )
        delivery = self._send_alert_notification(
            db,
            alert,
            crop_name,
            current_price,
            target_price,
            condition,
            message,
            source=current,
            previous_price=last_price,
        )
        triggered_at = datetime.now()
        try:
            alert.LastTriggered = triggered_at
            db.add(alert)
            db.commit()
        except SQLAlchemyError:
            db.rollback()

        return {
            "alert_id": alert.AlertID,
            "crop_name": crop_name,
            "region": alert.Region,
            "target_price": target_price,
            "current_price": current_price,
            "condition": condition,
            "triggered": True,
            "price_changed": price_changed,
            "previous_price": last_price,
            "triggered_at": triggered_at,
            "source": current,
            "delivery": delivery,
        }

    def _current_price_for_alert(self, db: Session, alert: PriceAlert, crop_name: str) -> dict | None:
        latest = (
            db.query(MarketPrice)
            .filter(MarketPrice.CropID == alert.CropID, MarketPrice.Region == alert.Region)
            .order_by(desc(MarketPrice.PriceDate), desc(MarketPrice.UpdatedAt))
            .first()
        )
        if latest is None:
            lookup_key = location_service.region_key(alert.Region)
            candidates = (
                db.query(MarketPrice)
                .filter(MarketPrice.CropID == alert.CropID)
                .order_by(desc(MarketPrice.PriceDate), desc(MarketPrice.UpdatedAt))
                .limit(100)
                .all()
            )
            latest = next(
                (row for row in candidates if location_service.region_key(row.Region) == lookup_key),
                None,
            )
        if latest:
            # Giá quá hạn không phải căn cứ để báo "vừa vượt ngưỡng". Nguồn
            # chính thống cập nhật hàng ngày; STALE_TTL_MINUTES["official_price"]
            # là 24 giờ. Bắn cảnh báo bán hàng dựa trên số đo hai tuần trước là
            # sai lệch tốn tiền thật của nông dân.
            # FetchedAt/ObservedAt có thể NULL với hàng cũ, nhưng PriceDate và
            # UpdatedAt là NOT NULL — luôn có mốc để lùi về, nên chốt chặn này
            # không bao giờ tắt câm cảnh báo chỉ vì thiếu một cột.
            moc = (latest.FetchedAt or latest.ObservedAt or latest.UpdatedAt
                   or latest.PriceDate)
            if isinstance(moc, date) and not isinstance(moc, datetime):
                moc = datetime.combine(moc, datetime.min.time())
            tuoi = cache_status_for(moc, "official_price")
            if tuoi == "miss":
                logger.info(
                    "[Alert] Bỏ qua cảnh báo %s/%s: giá gần nhất đã quá hạn (%s)",
                    crop_name, alert.Region, latest.FetchedAt or latest.UpdatedAt,
                )
                return None
            return {
                "current_price": float(latest.PricePerKg),
                "unit": "VND/kg",
                "source": "database",
                "source_name": latest.SourceName or "MarketPrices DB",
                "source_url": latest.SourceURL,
                "observed_at": latest.PriceDate,
                "last_updated": latest.UpdatedAt,
                "cache_status": "cached",
            }
        return None

    def _create_notification_records(
        self,
        db: Session,
        alert: PriceAlert,
        crop_name: str,
        current_price: float,
        target_price: float,
        condition: str,
        message: str,
        *,
        source: dict | None = None,
        previous_price: float | None = None,
    ) -> dict:
        channel = (alert.NotifyMethod or "app").lower()
        receiver = get_alert_receiver(db, alert)
        subject, plain, html = self._build_price_change_email(
            alert=alert,
            crop_name=crop_name,
            current_price=current_price,
            target_price=target_price,
            condition=condition,
            source=source,
            previous_price=previous_price,
        )
        inbox = notification_center_service.create_notification(
            db,
            NotificationCreate(
                user_id=alert.UserID,
                type="price",
                title=f"Cảnh báo giá {crop_name}",
                message=message,
                priority="high",
                channel="app",
                related_entity_type="price_alert",
                related_entity_id=alert.AlertID,
            ),
        )
        send_result = {"channel": channel, "receiver": receiver, "status": "stored", "message_id": None, "error": None}
        if channel != "app":
            if receiver:
                send_result = notification_service.send(channel, receiver, subject, plain, html)
            else:
                send_result = {
                    "channel": channel,
                    "receiver": receiver,
                    "status": "failed",
                    "message_id": None,
                    "error": "Receiver is missing",
                }
            delivery = NotificationDelivery(
                NotificationID=inbox["notification_id"],
                Channel=channel,
                Receiver=receiver,
                Status=send_result.get("status") or "pending",
                ProviderMessageID=send_result.get("message_id"),
                ErrorMessage=send_result.get("error"),
            )
            db.add(delivery)

        alert_event = AlertNotification(
            AlertID=alert.AlertID,
            CurrentPrice=current_price,
            Message=message,
            NotifyMethod=alert.NotifyMethod,
            SendStatus=self._legacy_send_status(send_result.get("status")),
            Channel=channel,
            Receiver=receiver,
            Status=send_result.get("status") or "stored",
            ProviderMessageID=send_result.get("message_id"),
            ErrorMessage=send_result.get("error"),
        )
        db.add(alert_event)
        db.commit()
        return send_result

    def _send_registration_confirmation(self, db: Session, alert: PriceAlert, current: dict | None) -> dict | None:
        crop_name = get_alert_crop_name(db, alert)
        current_price = float(current["current_price"]) if current else 0
        target_price = float(alert.TargetPrice)
        condition = to_api_alert_condition(alert.AlertType)
        channel = (alert.NotifyMethod or "email").lower()
        receiver = get_alert_receiver(db, alert)
        subject, plain, html = self._build_registration_email(
            alert=alert,
            crop_name=crop_name,
            current_price=current_price,
            target_price=target_price,
            condition=condition,
            source=current,
        )
        message = (
            f"Đã đăng ký cảnh báo giá {crop_name} tại {alert.Region}. "
            f"Giá hiện tại {current_price:,.0f} VND/kg, ngưỡng {target_price:,.0f} VND/kg."
        )
        inbox = notification_center_service.create_notification(
            db,
            NotificationCreate(
                user_id=alert.UserID,
                type="price",
                title=f"Đã đăng ký cảnh báo giá {crop_name}",
                message=message,
                priority="medium",
                channel="app",
                related_entity_type="price_alert",
                related_entity_id=alert.AlertID,
            ),
        )

        send_result = {"channel": channel, "receiver": receiver, "status": "stored", "message_id": None, "error": None}
        if channel != "app":
            if receiver:
                send_result = notification_service.send(channel, receiver, subject, plain, html)
            else:
                send_result = {
                    "channel": channel,
                    "receiver": receiver,
                    "status": "failed",
                    "message_id": None,
                    "error": "Receiver is missing",
                }
            db.add(
                NotificationDelivery(
                    NotificationID=inbox["notification_id"],
                    Channel=channel,
                    Receiver=receiver,
                    Status=send_result.get("status") or "pending",
                    ProviderMessageID=send_result.get("message_id"),
                    ErrorMessage=send_result.get("error"),
                )
            )

        db.add(
            AlertNotification(
                AlertID=alert.AlertID,
                CurrentPrice=current_price,
                Message=message,
                NotifyMethod=alert.NotifyMethod,
                SendStatus=self._legacy_send_status(send_result.get("status")),
                Channel=channel,
                Receiver=receiver,
                Status=send_result.get("status") or "stored",
                ProviderMessageID=send_result.get("message_id"),
                ErrorMessage=send_result.get("error"),
            )
        )
        db.commit()
        return send_result

    def _last_recorded_price(self, db: Session, alert_id: int) -> float | None:
        row = (
            db.query(AlertNotification)
            .filter(AlertNotification.AlertID == alert_id, AlertNotification.CurrentPrice.isnot(None))
            .order_by(desc(AlertNotification.SentAt), desc(AlertNotification.NotificationID))
            .first()
        )
        return float(row.CurrentPrice) if row and row.CurrentPrice is not None else None

    def _build_registration_email(
        self,
        *,
        alert: PriceAlert,
        crop_name: str,
        current_price: float,
        target_price: float,
        condition: str,
        source: dict | None,
    ) -> tuple[str, str, str]:
        condition_text = "giá cao hơn hoặc bằng" if condition == "above" else "giá thấp hơn hoặc bằng"
        source_name = (source or {}).get("source_name") or (source or {}).get("source") or "backend"
        cache_status = (source or {}).get("cache_status") or "unknown"
        last_updated = (source or {}).get("last_updated") or (source or {}).get("observed_at") or "chưa rõ"
        subject = f"[AgriAI] Xác nhận đăng ký cảnh báo giá {crop_name}"
        plain = (
            "Bạn đã đăng ký cảnh báo giá trên AgriAI.\n"
            f"Nông sản: {crop_name}\n"
            f"Khu vực: {alert.Region}\n"
            f"Giá hiện tại: {current_price:,.0f} VND/kg\n"
            f"Điều kiện: {condition_text} {target_price:,.0f} VND/kg\n"
            f"Kênh nhận: {alert.NotifyMethod}\n"
            f"Nguồn dữ liệu: {source_name} ({cache_status})\n"
            f"Cập nhật lúc: {last_updated}\n"
            "Khi backend kiểm tra thấy giá thay đổi, hệ thống sẽ gửi email cập nhật tiếp."
        )
        html = (
            "<html><body>"
            "<h2>Đã đăng ký cảnh báo giá</h2>"
            "<p>AgriAI đã lưu cấu hình cảnh báo của bạn.</p>"
            "<table cellpadding='6' cellspacing='0' border='1' style='border-collapse:collapse'>"
            f"<tr><td><strong>Nông sản</strong></td><td>{crop_name}</td></tr>"
            f"<tr><td><strong>Khu vực</strong></td><td>{alert.Region}</td></tr>"
            f"<tr><td><strong>Giá hiện tại</strong></td><td>{current_price:,.0f} VND/kg</td></tr>"
            f"<tr><td><strong>Điều kiện</strong></td><td>{condition_text} {target_price:,.0f} VND/kg</td></tr>"
            f"<tr><td><strong>Kênh nhận</strong></td><td>{alert.NotifyMethod}</td></tr>"
            f"<tr><td><strong>Nguồn dữ liệu</strong></td><td>{source_name} ({cache_status})</td></tr>"
            f"<tr><td><strong>Cập nhật lúc</strong></td><td>{last_updated}</td></tr>"
            "</table>"
            "<p>Khi giá thay đổi, AgriAI sẽ gửi email cập nhật tiếp.</p>"
            "</body></html>"
        )
        return subject, plain, html

    def _build_price_change_email(
        self,
        *,
        alert: PriceAlert,
        crop_name: str,
        current_price: float,
        target_price: float,
        condition: str,
        source: dict | None,
        previous_price: float | None,
    ) -> tuple[str, str, str]:
        source_name = (source or {}).get("source_name") or (source or {}).get("source") or "backend"
        cache_status = (source or {}).get("cache_status") or "unknown"
        last_updated = (source or {}).get("last_updated") or (source or {}).get("observed_at") or "chưa rõ"
        diff_line = "Chưa có giá trước đó trong hệ thống."
        if previous_price is not None:
            diff = current_price - previous_price
            direction = "tăng" if diff > 0 else "giảm"
            diff_line = f"Giá đã {direction} {abs(diff):,.0f} VND/kg so với lần ghi nhận gần nhất."
        condition_text = "giá cao hơn hoặc bằng" if condition == "above" else "giá thấp hơn hoặc bằng"
        subject = f"[AgriAI] Giá {crop_name} tại {alert.Region} đã thay đổi"
        previous_line = f"Giá trước: {previous_price:,.0f} VND/kg\n" if previous_price is not None else ""
        plain = (
            f"{diff_line}\n"
            f"Nông sản: {crop_name}\n"
            f"Khu vực: {alert.Region}\n"
            f"{previous_line}"
            f"Giá mới: {current_price:,.0f} VND/kg\n"
            f"Ngưỡng theo dõi: {condition_text} {target_price:,.0f} VND/kg\n"
            f"Nguồn dữ liệu: {source_name} ({cache_status})\n"
            f"Cập nhật lúc: {last_updated}\n"
        )
        html_previous = (
            f"<tr><td><strong>Giá trước</strong></td><td>{previous_price:,.0f} VND/kg</td></tr>"
            if previous_price is not None
            else ""
        )
        html = (
            "<html><body>"
            "<h2>Giá nông sản đã thay đổi</h2>"
            f"<p>{diff_line}</p>"
            "<table cellpadding='6' cellspacing='0' border='1' style='border-collapse:collapse'>"
            f"<tr><td><strong>Nông sản</strong></td><td>{crop_name}</td></tr>"
            f"<tr><td><strong>Khu vực</strong></td><td>{alert.Region}</td></tr>"
            f"{html_previous}"
            f"<tr><td><strong>Giá mới</strong></td><td>{current_price:,.0f} VND/kg</td></tr>"
            f"<tr><td><strong>Ngưỡng theo dõi</strong></td><td>{condition_text} {target_price:,.0f} VND/kg</td></tr>"
            f"<tr><td><strong>Nguồn dữ liệu</strong></td><td>{source_name} ({cache_status})</td></tr>"
            f"<tr><td><strong>Cập nhật lúc</strong></td><td>{last_updated}</td></tr>"
            "</table>"
            "</body></html>"
        )
        return subject, plain, html

    def _evaluate_weather_alert(self, db: Session, alert: WeatherAlert) -> dict | None:
        if alert.LastTriggered and datetime.now() - alert.LastTriggered < ALERT_COOLDOWN:
            return None

        condition = alert.AlertType or "rainfall"
        meta = self._weather_condition_meta(condition)
        region = location_service.display_name(alert.Region)
        current = weather_service.get_current_weather(db, region, force_refresh=True)
        current_value = self._weather_value(current, condition)
        if current_value is None:
            return None

        last_value = alert.LastValue
        changed = last_value is None or abs(current_value - float(last_value)) >= meta["epsilon"]
        if not changed:
            return None

        threshold = float(alert.TriggerValue or 0)
        threshold_matched = current_value >= threshold if threshold > 0 else changed
        message = self._weather_change_message(alert, current_value, last_value, threshold_matched)
        delivery = self._create_weather_notification_records(
            db,
            alert,
            current,
            current_value,
            message,
            priority="high" if threshold_matched else "medium",
            previous_value=last_value,
            update_last_triggered=True,
        )
        return {
            "alert_id": alert.AlertID,
            "alert_kind": "weather",
            "region": location_service.display_name(alert.Region),
            "condition": condition,
            "weather_condition": condition,
            "target_value": threshold,
            "current_value": current_value,
            "previous_value": last_value,
            "unit": meta["unit"],
            "triggered": True,
            "threshold_matched": threshold_matched,
            "triggered_at": datetime.now(),
            "delivery": delivery,
        }

    def _send_weather_registration_confirmation(
        self,
        db: Session,
        alert: WeatherAlert,
        current: dict,
        current_value: float | None,
    ) -> dict:
        meta = self._weather_condition_meta(alert.AlertType)
        message = (
            f"Đã đăng ký cảnh báo {meta['label'].lower()} tại {location_service.display_name(alert.Region)}. "
            f"Giá trị hiện tại {float(current_value or 0):,.1f} {meta['unit']}, "
            f"ngưỡng {float(alert.TriggerValue or 0):,.1f} {meta['unit']}."
        )
        return self._create_weather_notification_records(
            db,
            alert,
            current,
            current_value,
            message,
            priority="medium",
            previous_value=None,
            update_last_triggered=False,
            registration=True,
        )

    def _create_weather_notification_records(
        self,
        db: Session,
        alert: WeatherAlert,
        current: dict,
        current_value: float | None,
        message: str,
        *,
        priority: str,
        previous_value: float | None,
        update_last_triggered: bool,
        registration: bool = False,
    ) -> dict:
        channel = (alert.NotifyMethod or "app").lower()
        receiver = alert.Receiver or ""
        if registration:
            subject, plain, html = self._build_weather_registration_email(alert, current, current_value)
            title = f"Đã đăng ký cảnh báo thời tiết {location_service.display_name(alert.Region)}"
        else:
            subject, plain, html = self._build_weather_change_email(alert, current, current_value, previous_value)
            title = f"Cảnh báo thời tiết {location_service.display_name(alert.Region)}"

        inbox = notification_center_service.create_notification(
            db,
            NotificationCreate(
                user_id=alert.UserID,
                type="weather",
                title=title,
                message=message,
                priority=priority,
                channel="app",
                related_entity_type="weather_alert",
                related_entity_id=alert.AlertID,
            ),
        )
        send_result = {"channel": channel, "receiver": receiver, "status": "stored", "message_id": None, "error": None}
        if channel != "app":
            if receiver:
                send_result = notification_service.send(channel, receiver, subject, plain, html)
            else:
                send_result = {
                    "channel": channel,
                    "receiver": receiver,
                    "status": "failed",
                    "message_id": None,
                    "error": "Receiver is missing",
                }
            db.add(
                NotificationDelivery(
                    NotificationID=inbox["notification_id"],
                    Channel=channel,
                    Receiver=receiver,
                    Status=send_result.get("status") or "pending",
                    ProviderMessageID=send_result.get("message_id"),
                    ErrorMessage=send_result.get("error"),
                )
            )

        alert.LastValue = current_value
        if update_last_triggered:
            alert.LastTriggered = datetime.now()
        db.add(alert)
        db.commit()
        return send_result

    def _build_weather_registration_email(
        self,
        alert: WeatherAlert,
        current: dict,
        current_value: float | None,
    ) -> tuple[str, str, str]:
        meta = self._weather_condition_meta(alert.AlertType)
        region = location_service.display_name(alert.Region)
        threshold = float(alert.TriggerValue or 0)
        current_text = f"{float(current_value or 0):,.1f} {meta['unit']}"
        subject = f"[AgriAI] Xác nhận đăng ký cảnh báo thời tiết {region}"
        plain = (
            "Bạn đã đăng ký cảnh báo thời tiết trên AgriAI.\n"
            f"Khu vực: {region}\n"
            f"Loại cảnh báo: {meta['label']}\n"
            f"Giá trị hiện tại: {current_text}\n"
            f"Ngưỡng theo dõi: {threshold:,.1f} {meta['unit']}\n"
            f"Kênh nhận: {alert.NotifyMethod}\n"
            f"Nguồn dữ liệu: {current.get('source_name') or current.get('source') or 'Open-Meteo'}\n"
            f"Cập nhật lúc: {current.get('recorded_at') or current.get('last_updated') or 'chưa rõ'}\n"
            "Khi thời tiết thay đổi, AgriAI sẽ gửi email cập nhật tiếp."
        )
        html = (
            "<html><body>"
            "<h2>Đã đăng ký cảnh báo thời tiết</h2>"
            "<p>AgriAI đã lưu cấu hình cảnh báo của bạn.</p>"
            "<table cellpadding='6' cellspacing='0' border='1' style='border-collapse:collapse'>"
            f"<tr><td><strong>Khu vực</strong></td><td>{region}</td></tr>"
            f"<tr><td><strong>Loại cảnh báo</strong></td><td>{meta['label']}</td></tr>"
            f"<tr><td><strong>Giá trị hiện tại</strong></td><td>{current_text}</td></tr>"
            f"<tr><td><strong>Ngưỡng theo dõi</strong></td><td>{threshold:,.1f} {meta['unit']}</td></tr>"
            f"<tr><td><strong>Nhiệt độ</strong></td><td>{current.get('temperature') or 0}°C</td></tr>"
            f"<tr><td><strong>Lượng mưa</strong></td><td>{current.get('rainfall') or 0} mm</td></tr>"
            f"<tr><td><strong>Độ ẩm</strong></td><td>{current.get('humidity') or 0}%</td></tr>"
            f"<tr><td><strong>Gió</strong></td><td>{current.get('wind_speed') or 0} km/h</td></tr>"
            f"<tr><td><strong>Nguồn dữ liệu</strong></td><td>{current.get('source_name') or current.get('source') or 'Open-Meteo'}</td></tr>"
            "</table>"
            "<p>Khi thời tiết thay đổi, AgriAI sẽ gửi email cập nhật tiếp.</p>"
            "</body></html>"
        )
        return subject, plain, html

    def _build_weather_change_email(
        self,
        alert: WeatherAlert,
        current: dict,
        current_value: float | None,
        previous_value: float | None,
    ) -> tuple[str, str, str]:
        meta = self._weather_condition_meta(alert.AlertType)
        region = location_service.display_name(alert.Region)
        threshold = float(alert.TriggerValue or 0)
        current_value = float(current_value or 0)
        previous_line = ""
        if previous_value is not None:
            diff = current_value - float(previous_value)
            direction = "tăng" if diff > 0 else "giảm"
            previous_line = f"Giá trị trước: {float(previous_value):,.1f} {meta['unit']} ({direction} {abs(diff):,.1f})\n"
        subject = f"[AgriAI] Thời tiết {region} đã thay đổi"
        plain = (
            f"Cảnh báo: {meta['label']}\n"
            f"Khu vực: {region}\n"
            f"{previous_line}"
            f"Giá trị mới: {current_value:,.1f} {meta['unit']}\n"
            f"Ngưỡng theo dõi: {threshold:,.1f} {meta['unit']}\n"
            f"Nhiệt độ: {current.get('temperature') or 0}°C\n"
            f"Lượng mưa: {current.get('rainfall') or 0} mm\n"
            f"Độ ẩm: {current.get('humidity') or 0}%\n"
            f"Gió: {current.get('wind_speed') or 0} km/h\n"
            f"Cập nhật lúc: {current.get('recorded_at') or current.get('last_updated') or 'chưa rõ'}\n"
        )
        html_previous = (
            f"<tr><td><strong>Giá trị trước</strong></td><td>{float(previous_value):,.1f} {meta['unit']}</td></tr>"
            if previous_value is not None
            else ""
        )
        html = (
            "<html><body>"
            "<h2>Thời tiết đã thay đổi</h2>"
            "<table cellpadding='6' cellspacing='0' border='1' style='border-collapse:collapse'>"
            f"<tr><td><strong>Khu vực</strong></td><td>{region}</td></tr>"
            f"<tr><td><strong>Cảnh báo</strong></td><td>{meta['label']}</td></tr>"
            f"{html_previous}"
            f"<tr><td><strong>Giá trị mới</strong></td><td>{current_value:,.1f} {meta['unit']}</td></tr>"
            f"<tr><td><strong>Ngưỡng theo dõi</strong></td><td>{threshold:,.1f} {meta['unit']}</td></tr>"
            f"<tr><td><strong>Nhiệt độ</strong></td><td>{current.get('temperature') or 0}°C</td></tr>"
            f"<tr><td><strong>Lượng mưa</strong></td><td>{current.get('rainfall') or 0} mm</td></tr>"
            f"<tr><td><strong>Độ ẩm</strong></td><td>{current.get('humidity') or 0}%</td></tr>"
            f"<tr><td><strong>Gió</strong></td><td>{current.get('wind_speed') or 0} km/h</td></tr>"
            f"<tr><td><strong>Nguồn dữ liệu</strong></td><td>{current.get('source_name') or current.get('source') or 'Open-Meteo'}</td></tr>"
            "</table>"
            "</body></html>"
        )
        return subject, plain, html

    def _weather_change_message(
        self,
        alert: WeatherAlert,
        current_value: float,
        previous_value: float | None,
        threshold_matched: bool,
    ) -> str:
        meta = self._weather_condition_meta(alert.AlertType)
        region = location_service.display_name(alert.Region)
        threshold = float(alert.TriggerValue or 0)
        if previous_value is None:
            change_text = "đã được ghi nhận"
        else:
            diff = current_value - float(previous_value)
            change_text = f"đã {'tăng' if diff > 0 else 'giảm'} {abs(diff):,.1f} {meta['unit']}"
        threshold_text = " và đã vượt ngưỡng" if threshold_matched else ""
        return (
            f"{meta['label']} tại {region} {change_text}, hiện {current_value:,.1f} {meta['unit']}"
            f"{threshold_text}. Ngưỡng theo dõi: {threshold:,.1f} {meta['unit']}."
        )

    @staticmethod
    def _weather_condition_meta(condition: str | None) -> dict:
        return WEATHER_CONDITIONS.get(condition or "rainfall", WEATHER_CONDITIONS["rainfall"])

    @staticmethod
    def _weather_value(current: dict, condition: str | None) -> float | None:
        condition = condition or "rainfall"
        if condition == "rainfall":
            return float(current.get("rainfall") or 0)
        if condition == "temperature":
            return float(current.get("temperature") or current.get("temp_max") or 0)
        if condition == "wind":
            return float(current.get("wind_speed") or 0)
        if condition == "humidity":
            return float(current.get("humidity") or 0)
        if condition == "air_quality":
            return float(current.get("uv_index") or 0)
        return float(current.get("rainfall") or 0)

    @staticmethod
    def _db_channel(channel: str | None) -> str:
        return {
            "email": "Email",
            "zalo": "Zalo",
            "sms": "SMS",
            "app": "App",
        }.get((channel or "email").lower(), "Email")

    @staticmethod
    def _default_receiver(user: User | None, channel: str) -> str:
        if not user:
            return ""
        if channel == "sms":
            return user.PhoneNumber or ""
        if channel == "zalo":
            return user.ZaloID or ""
        if channel == "email":
            return user.Email or ""
        return ""

    @staticmethod
    def _preferred_delivery(db: Session, notification_id: int) -> NotificationDelivery | None:
        deliveries = (
            db.query(NotificationDelivery)
            .filter(NotificationDelivery.NotificationID == notification_id)
            .order_by(desc(NotificationDelivery.SentAt), desc(NotificationDelivery.DeliveryID))
            .all()
        )
        return next((delivery for delivery in deliveries if delivery.Channel != "app"), None) or (deliveries[0] if deliveries else None)

    @staticmethod
    def _weather_to_response(alert: WeatherAlert, message: str) -> dict:
        meta = AlertService._weather_condition_meta(alert.AlertType)
        return {
            "alert_id": alert.AlertID,
            "alert_kind": "weather",
            "crop_id": None,
            "crop_name": "Thời tiết",
            "region": location_service.display_name(alert.Region),
            "region_key": location_service.region_key(alert.Region),
            "target_price": float(alert.TriggerValue or 0),
            "condition": alert.AlertType,
            "weather_condition": alert.AlertType,
            "rule_type": "weather_threshold",
            "threshold_percent": None,
            "trigger_unit": alert.TriggerUnit or meta["unit"],
            "severity": alert.Severity,
            "notification_channel": (alert.NotifyMethod or "Email").lower(),
            "receiver": alert.Receiver or "",
            "is_active": bool(alert.IsActive),
            "message": message,
            "created_at": alert.CreatedAt,
            "last_triggered_at": alert.LastTriggered,
            "related_alert_id": alert.AlertID,
            "priority": "high" if alert.Severity == "high" else "medium",
            "suggested_action": alert.Recommendation,
            "action_required": alert.Severity == "high",
            "source": "database",
            "source_name": "WeatherAlert DB",
            "fetched_at": datetime.now(),
            "updated_at": getattr(alert, "UpdatedAt", None) or alert.CreatedAt,
            "confidence": 0.7,
        }

    def _recent_history(self, db: Session, crop_id: int | None, crop_name: str, region: str) -> list[float]:
        if crop_id:
            rows = (
                db.query(PriceHistory)
                .filter(PriceHistory.CropID == crop_id, PriceHistory.Region == region)
                .order_by(desc(PriceHistory.RecordDate))
                .limit(7)
                .all()
            )
            if rows:
                return [float(row.AvgPrice) for row in rows]
        history = pricing_service.get_price_history(db, crop_name, region, days=7)
        return [float(row["avg_price"]) for row in history if row.get("avg_price")]

    @staticmethod
    def _legacy_send_status(status: str | None) -> str:
        if status in {"sent", "stored"}:
            return "Sent"
        if status in {"failed", "error"}:
            return "Failed"
        return "Pending"

    @staticmethod
    def _looks_mojibake(value: str | None) -> bool:
        if not value:
            return False
        bad_question_mark = chr(63)
        markers = (
            "\ufffd",
            "\u00d0",
            "\u00c4",
            "\u00c6",
            "\u00e1\u00ba",
            "\u00e1\u00bb",
            f"Hà N{bad_question_mark}i",
            f"ngư{bad_question_mark}ng",
            f"hi{bad_question_mark}n",
            f"c{bad_question_mark}nh",
        )
        return any(marker in value for marker in markers)

    @staticmethod
    def _looks_incomplete_history(value: str | None) -> bool:
        if not value:
            return True
        return value.startswith("Đã đăng ký cảnh báo") and "Giá hiện tại" not in value

    @staticmethod
    def _history_message(crop_name: str, region: str, current_price: float | None, target_price: float | None) -> str:
        return (
            f"Đã đăng ký cảnh báo giá {crop_name} tại {region}. "
            f"Giá hiện tại {float(current_price or 0):,.0f} VND/kg, "
            f"ngưỡng {float(target_price or 0):,.0f} VND/kg."
        )

    @staticmethod
    def _delivery_error_message(error: str | None) -> str | None:
        if not error:
            return None
        if error == "SMTP is not configured":
            return "SMTP chưa cấu hình nên chưa gửi Gmail thật."
        return error

    @staticmethod
    def _to_response(db: Session, alert: PriceAlert, message: str) -> dict:
        return {
            "alert_id": alert.AlertID,
            "alert_kind": "price",
            "crop_id": alert.CropID,
            "crop_name": get_alert_crop_name(db, alert),
            "region": location_service.display_name(alert.Region),
            "region_key": location_service.region_key(alert.Region),
            "target_price": float(alert.TargetPrice),
            "condition": to_api_alert_condition(alert.AlertType),
            "weather_condition": None,
            "rule_type": "price_threshold",
            "threshold_percent": None,
            "trigger_unit": None,
            "severity": None,
            "notification_channel": (alert.NotifyMethod or "Email").lower(),
            "receiver": get_alert_receiver(db, alert),
            "is_active": bool(alert.IsActive),
            "message": message,
            "created_at": alert.CreatedAt,
            "last_triggered_at": alert.LastTriggered,
            "related_alert_id": alert.AlertID,
            "priority": "medium",
            "suggested_action": "Theo doi gia va tao ke hoach ban theo nhieu dot.",
            "action_required": False,
            "source": "database",
            "source_name": "PriceAlert DB",
            "fetched_at": datetime.now(),
            "updated_at": getattr(alert, "UpdatedAt", None) or alert.CreatedAt,
            "confidence": 0.7,
        }


alert_service = AlertService()
