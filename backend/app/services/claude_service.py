import asyncio
import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.integrations.claude_client import ai_client
from app.models.conversation import AIConversation
from app.services.ai_intent_service import (
    ANALYSIS_INTENTS,
    GENERAL_CAPABILITY_REPLY,
    GREETING_REPLY,
    classify_user_intent,
    db_topic_for_intent,
    is_capability_question,
)
from app.services.pricing_service import pricing_service
from app.services.weather_service import weather_service


class ClaudeService:
    async def answer_question(
        self,
        db: Session,
        *,
        question: str,
        user_id: int | None = None,
        crop_name: str | None = None,
        region: str | None = None,
        session_id: str | None = None,
        extra_context: dict | None = None,
    ) -> dict:
        intent = classify_user_intent(question)
        if intent == "greeting" or (intent == "general_question" and is_capability_question(question)):
            answer = GREETING_REPLY if intent == "greeting" else GENERAL_CAPABILITY_REPLY
            context = {"intent": intent}
            return {
                "answer": answer,
                "provider": "local",
                "model": "intent-router-v1",
                "token_usage": None,
                "context": context,
                "is_mock": False,
                "error": None,
                "timeout": False,
                "created_at": datetime.now(),
            }

        if extra_context:
            built_context = {}
        elif intent in ANALYSIS_INTENTS:
            from app.services.ai_context_service import ai_context_service

            built_context = ai_context_service.build_ai_context(
                db,
                user_id=user_id,
                crop=crop_name,
                region=region,
                intent=intent,
            )
        else:
            built_context = {"intent": intent, "region": region, "crop_name": crop_name}
        context = dict(extra_context or {})
        for key, value in built_context.items():
            context.setdefault(key, value)
        if extra_context:
            context.update({key: value for key, value in extra_context.items() if key not in {"weather_error", "pricing_error"}})
            context["tools_used"] = extra_context.get("tools_used", [])
        system_prompt = (
            "Bạn là Trợ lý AI nông nghiệp của hệ thống NongNghiepAI. "
            "Trả lời đúng trọng tâm câu hỏi, ngắn gọn, thực tế cho nông dân. "
            "Chỉ dùng dữ liệu trong context; không bịa số liệu giá, thời tiết, sản lượng, rủi ro hoặc ngày thu hoạch. "
            "Nếu thiếu dữ liệu, hãy nói rõ “Hiện chưa có đủ dữ liệu để phân tích chính xác”. "
            "Không hiển thị metadata nội bộ như Database, API, AI Generated, timestamp, engine."
        )
        user_prompt = f"Context JSON:\n{json.dumps(context, ensure_ascii=False, default=str)}\n\nQuestion: {question}"
        try:
            completion = await asyncio.to_thread(
                ai_client.complete,
                [{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
            )
        except Exception as exc:
            completion = {
                "answer": "",
                "provider": "claude",
                "model": "claude",
                "token_usage": None,
                "is_mock": False,
                "error": "Không thể kết nối trợ lý AI. Vui lòng thử lại sau.",
                "timeout": "timeout" in str(exc).lower(),
            }

        return {
            "answer": completion["answer"],
            "provider": completion["provider"],
            "model": completion["model"],
            "token_usage": completion.get("token_usage"),
            "context": context,
            "is_mock": completion.get("is_mock", False),
            "error": completion.get("error"),
            "timeout": completion.get("timeout", False),
            "created_at": datetime.now(),
        }

    def get_market_insights(self, crop_name: str, region: str) -> str:
        return f"Hãy gọi /api/ai/chat với crop_name={crop_name}, region={region} để lấy insight có context."

    def get_selling_recommendations(self, data: dict) -> str:
        return "Dùng /api/market/suggest và /api/ai/chat để lấy khuyến nghị có dữ liệu giá/thời tiết."

    def _build_context(self, db: Session, crop_name: str | None, region: str | None, user_id: int | None) -> dict:
        region = region or "Ha Noi"
        context: dict = {"region": region}
        if crop_name:
            context["crop_name"] = crop_name
            context["pricing"] = pricing_service.get_current_price(db, crop_name, region)
            context["price_history"] = pricing_service.get_price_history(db, crop_name, region, 14)
        context["weather"] = weather_service.get_current_weather(db, region)
        context["weather_forecast"] = weather_service.get_forecast(db, region, 7)
        if user_id:
            context["recent_quality_records"] = self._recent_quality_records(db, user_id)
            context["harvest_schedules"] = self._active_harvest_schedules(db, user_id)
        return context

    @staticmethod
    def _recent_quality_records(db: Session, user_id: int) -> list[dict]:
        try:
            from app.models.quality import QualityRecord

            rows = db.query(QualityRecord).filter(QualityRecord.UserID == user_id).order_by(QualityRecord.CheckDate.desc()).limit(5).all()
            return [
                {
                    "quality_grade": row.AIGrade,
                    "confidence": row.ConfidenceScore,
                    "checked_at": row.CheckDate,
                    "issues": row.DetectedIssues,
                }
                for row in rows
            ]
        except Exception:
            return []

    @staticmethod
    def _active_harvest_schedules(db: Session, user_id: int) -> list[dict]:
        try:
            from app.models.harvest import HarvestSchedule

            rows = db.query(HarvestSchedule).filter(HarvestSchedule.UserID == user_id).order_by(HarvestSchedule.CreatedAt.desc()).limit(5).all()
            return [
                {
                    "crop_id": row.CropID,
                    "region": row.Region,
                    "planting_date": row.PlantingDate,
                    "expected_harvest_date": row.ExpectedHarvestDate,
                    "status": row.Status,
                }
                for row in rows
            ]
        except Exception:
            return []

    @staticmethod
    def _fallback_answer(question: str, context: dict, error: str) -> str:
        parts = [
            "Hiện chưa có đủ dữ liệu để phân tích chính xác.",
        ]
        pricing = context.get("pricing")
        if pricing:
            price_value = pricing.get("current_price") or pricing.get("market_price")
            price_text = f"{float(price_value):,.0f} VND/kg" if price_value is not None else "chưa có số liệu giá"
            parts.append(
                f"Giá hiện tại {pricing.get('crop_name')} tại {pricing.get('region')} là "
                f"{price_text}."
            )
        weather = context.get("weather")
        if weather:
            parts.append(
                f"Thời tiết {weather.get('region')}: {weather.get('temperature')}C, "
                f"mưa {weather.get('rainfall')}mm."
            )
        if not pricing and not weather:
            parts.append("Bạn vui lòng cung cấp thêm cây trồng, khu vực hoặc mùa vụ cần xem.")
        return "\n".join(parts)

    @staticmethod
    def _save_conversation(
        db: Session,
        user_id: int | None,
        session_id: str | None,
        question: str,
        completion: dict,
        context: dict,
        crop_name: str | None,
    ) -> None:
        try:
            related_crop_id = None
            if crop_name:
                from app.models.crop import Crop

                crop = db.query(Crop).filter(Crop.CropName == crop_name).first()
                related_crop_id = crop.CropID if crop else None
            row = AIConversation(
                UserID=user_id,
                SessionID=session_id,
                UserMessage=question,
                AIResponse=completion["answer"],
                Topic=db_topic_for_intent(context.get("intent")),
                RelatedCropID=related_crop_id,
                ContextSnapshot=json.dumps(context, ensure_ascii=False, default=str),
                Provider=completion.get("provider"),
                ModelName=completion.get("model"),
                TokenUsage=json.dumps(completion.get("token_usage"), ensure_ascii=False),
            )
            db.add(row)
            db.commit()
        except Exception:
            db.rollback()


claude_service = ClaudeService()
