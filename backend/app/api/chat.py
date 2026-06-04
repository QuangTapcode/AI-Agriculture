from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session
from app.integrations.gemini_client import GeminiClient
from app.core.database import get_db
from app.api.auth import get_optional_current_user, get_current_user
from app.models.user import User
from app.services.ai_intent_service import (
    GENERAL_CAPABILITY_REPLY,
    GREETING_REPLY,
    classify_user_intent,
    db_topic_for_intent,
    extract_crop_from_message,
    extract_region_from_message,
    is_capability_question,
)

router = APIRouter(prefix="/api/chat", tags=["AI Chatbot"])

gemini_client = GeminiClient()


def _build_local_fallback_answer(question: str, topic: str = "general", region: str | None = None, crop: str | None = None) -> str:
    region_text = region or _detect_region(question)
    crop_text = crop or extract_crop_from_message(question)

    if topic in {"price", "price_query"}:
        crop_label = crop_text or "nông sản này"
        return (
            f"Hiện AI bên ngoài đang tạm không khả dụng. "
            f"Bạn đang hỏi về giá {crop_label} tại {region_text}. "
            "Vui lòng thử lại sau ít phút hoặc cung cấp thêm khu vực/cây trồng để hệ thống hỗ trợ tốt hơn."
        )
    if topic == "weather":
        return (
            f"Hiện AI bên ngoài đang tạm không khả dụng. "
            f"Bạn đang hỏi thời tiết tại {region_text}. Vui lòng thử lại sau ít phút."
        )
    if topic == "cultivation":
        crop_label = crop_text or "cây trồng"
        return (
            f"Hiện AI bên ngoài đang tạm không khả dụng. "
            f"Bạn đang hỏi về canh tác {crop_label}. Vui lòng thử lại sau hoặc mô tả rõ hơn giai đoạn sinh trưởng."
        )
    if topic == "pest":
        crop_label = crop_text or "cây trồng"
        return (
            f"Hiện AI bên ngoài đang tạm không khả dụng. "
            f"Bạn đang hỏi về sâu bệnh trên {crop_label}. Vui lòng cung cấp thêm triệu chứng để hỗ trợ tốt hơn khi hệ thống sẵn sàng."
        )
    return "Hiện AI bên ngoài đang tạm không khả dụng. Vui lòng thử lại sau ít phút."


def _save_conversation(db: Session, user_id: int | None, question: str, answer: str, topic: str = "general") -> None:
    from app.models.conversation import AIConversation

    row = AIConversation(
        UserID=user_id,
        UserMessage=question,
        AIResponse=answer,
        Provider="gemini",
        Topic=db_topic_for_intent(topic),
    )
    try:
        db.add(row)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise RuntimeError(f"Failed to save conversation: {exc}") from exc


class ChatRequest(BaseModel):
    question: str = ""
    message: str = ""   # alias cho question (backward compat)
    context_data: str = ""
    user_id: int | None = None

    @model_validator(mode="after")
    def resolve_question(self):
        if not self.question and self.message:
            self.question = self.message
        if not self.question:
            raise ValueError("Vui lòng cung cấp trường 'question' hoặc 'message'")
        return self


class ChatResponse(BaseModel):
    answer: str


class PriceQARequest(BaseModel):
    question: str     # Câu hỏi định giá, ví dụ: "Giá sầu riêng Đắk Lắk hôm nay?"


class PriceQAResponse(BaseModel):
    answer: str
    tavily_answer: str = ""
    sources: list = []
    db_prices: list = []

# Từ khoá kích hoạt RAG từng loại
_PRICE_KEYWORDS       = ["giá", "bao nhiêu", "thị trường", "mua", "bán", "đồng", "tiền", "xu hướng giá"]
_CROP_KEYWORDS        = ["trồng", "chăm sóc", "thu hoạch", "sinh trưởng", "phát triển", "ra hoa", "đậu trái", "bón phân", "gieo", "ươm", "canh tác", "mùa vụ"]
_PEST_KEYWORDS        = ["sâu", "bệnh", "nấm", "vi khuẩn", "virus", "héo", "vàng lá", "thối", "rệp", "nhện", "côn trùng", "thuốc trừ", "thuốc bảo vệ", "phòng trừ"]
_WEATHER_KEYWORDS     = ["thời tiết", "bão", "lũ", "lụt", "mưa", "hạn hán", "nhiệt độ", "độ ẩm", "gió", "dự báo", "áp thấp", "nắng nóng", "rét đậm", "sương muối", "ngập", "khô hạn", "lũ quét", "bão số"]
_SALINITY_KEYWORDS    = ["độ mặn", "xâm nhập mặn", "đất mặn", "nước mặn", "nhiễm mặn", "mặn hóa", "mặn xâm"]
_ACIDITY_KEYWORDS     = ["phèn", "đất phèn", "đất chua", "ph đất", "cải tạo đất", "vôi nông nghiệp", "bón vôi", "đất nhiễm phèn", "axit đất"]


def _question_contains(question: str, keywords: list[str]) -> bool:
    q = question.lower()
    return any(k in q for k in keywords)


def _detect_topic(question: str) -> str:
    """Phát hiện chủ đề chính của câu hỏi."""
    q = question.lower()
    if any(k in q for k in _WEATHER_KEYWORDS):
        return "weather"
    if any(k in q for k in _SALINITY_KEYWORDS):
        return "soil_salinity"
    if any(k in q for k in _ACIDITY_KEYWORDS):
        return "soil_acidity"
    if any(k in q for k in _PEST_KEYWORDS):
        return "pest"
    if any(k in q for k in _CROP_KEYWORDS):
        return "cultivation"
    if any(k in q for k in _PRICE_KEYWORDS):
        return "price"
    return "general"


_SALINITY_KNOWLEDGE = """## Kiến thức xử lý đất mặn (Saline Soil):
- Đất mặn: ECe > 4 dS/m, phổ biến ĐBSCL khi nước biển xâm nhập tháng 1–4
- Ngưỡng an toàn: Lúa ECe < 2 dS/m | Sầu riêng/Chôm chôm < 1 dS/m | Dừa < 6 dS/m
- Nhận biết: Lá cây cháy mép, đất có váng muối trắng, cây chậm phát triển
- Xử lý cấp bách: Đắp bờ ngăn nước mặn | Tưới rửa mặn bằng nước ngọt 3–4 lần liên tiếp
- Cải tạo: Bón thạch cao (CaSO4) 500–1000 kg/ha | Trồng cây phân xanh cải tạo đất
- Giống chịu mặn: Lúa OM9915, GKG9, Đài Thơm 8 | Ớt, cà tím, mè chịu mặn tương đối
- Thời điểm nguy hiểm: tháng 2–4 mặn xâm nhập sâu nhất tại ĐBSCL"""

_ACIDITY_KNOWLEDGE = """## Kiến thức xử lý đất phèn (Acid Sulfate Soil):
- Đất phèn: pH < 4.5, có pyrite (FeS2) và jarosite vàng, phổ biến tứ giác Long Xuyên, Đồng Tháp
- Nhận biết: đất vàng xám/xám đen | nước ruộng màu đỏ cam | lá cây vàng từ ngọn xuống
- Không cày sâu khi đất phèn tiềm tàng | Xả phèn trước khi trồng 2–3 tuần
- Bón vôi: CaCO3 (vôi nông nghiệp) 1–2 tấn/ha | Dolomite nếu thiếu Mg | Trộn đều tầng canh tác
- pH mục tiêu: 5.5–6.5 cho lúa và rau màu | > 6.0 cho cây ăn trái
- Phân bón phù hợp: Lân nung chảy (thermophosphate) thay super lân | Ưu tiên NPK cao P và K
- Luân canh: Lúa → cải thiện hơn hoa màu liên tục | Cây tràm giúp ổn định đất phèn"""


_WEATHER_COND_VI = {
    "clear": "trời trong", "mostly_clear": "ít mây", "partly_cloudy": "mây rải rác",
    "cloudy": "nhiều mây", "rainy": "có mưa", "heavy_rain": "mưa lớn",
    "thunderstorm": "dông sấm sét", "foggy": "sương mù", "drizzle": "mưa phùn",
    "rain_showers": "mưa rào", "sunny": "nắng đẹp",
}


def _build_weather_context(db: Session, region: str) -> str:
    try:
        from app.services.weather_service import weather_service
        current = weather_service.get_current_weather(db, region)
        cond = _WEATHER_COND_VI.get(str(current.get("condition", "")), str(current.get("condition", "chưa rõ")))
        lines = [f"## Thời tiết tại {current.get('region', region)} (live):"]
        temp = current.get("temperature")
        if temp is not None:
            lines.append(f"- Nhiệt độ: {temp}°C (thấp nhất {current.get('temp_min', 'N/A')}°C / cao nhất {current.get('temp_max', 'N/A')}°C)")
        if current.get("humidity") is not None:
            lines.append(f"- Độ ẩm: {current['humidity']}%")
        rain = current.get("rainfall") or 0
        lines.append(f"- Lượng mưa: {float(rain):.1f} mm/ngày")
        if current.get("wind_speed"):
            lines.append(f"- Gió: {float(current['wind_speed']):.0f} km/h")
        lines.append(f"- Điều kiện: {cond}")
        warnings = current.get("warnings") or []
        if warnings:
            lines.append("\n## Cảnh báo thời tiết:")
            for w in warnings:
                lines.append(f"- ⚠️ {w}")
        forecast = weather_service.get_forecast(db, region, days=3)
        if forecast:
            lines.append(f"\n## Dự báo 3 ngày tới tại {region}:")
            for f in forecast[:3]:
                fc = _WEATHER_COND_VI.get(str(f.get("condition", "")), str(f.get("condition", "")))
                fwarns = f.get("warnings") or []
                ws = f" | ⚠️ {fwarns[0]}" if fwarns else ""
                lines.append(f"- {f.get('date', 'N/A')}: {fc} | {f.get('temp_min', '?')}–{f.get('temp_max', '?')}°C | mưa {float(f.get('rainfall', 0)):.0f}mm{ws}")
        return "\n".join(lines)
    except Exception:
        return f"## Lưu ý: Không lấy được dữ liệu thời tiết tại {region}."

# Bảng mapping từ khoá vùng → tên vùng chính xác trong DB
_REGION_KEYWORDS: dict[str, str] = {
    "đà nẵng": "Đà Nẵng", "da nang": "Đà Nẵng",
    "hà nội": "Hà Nội", "ha noi": "Hà Nội", "hà nôi": "Hà Nội",
    "hồ chí minh": "TP.HCM", "ho chi minh": "TP.HCM",
    "tp.hcm": "TP.HCM", "tphcm": "TP.HCM", "hcm": "TP.HCM", "sài gòn": "TP.HCM",
    "cần thơ": "Cần Thơ", "can tho": "Cần Thơ",
    "gia lai": "Gia Lai",
    "đắk lắk": "Đắk Lắk", "dak lak": "Đắk Lắk", "đắk lak": "Đắk Lắk",
    "đắk nông": "Đắk Nông", "dak nong": "Đắk Nông",
    "bình phước": "Bình Phước", "binh phuoc": "Bình Phước",
    "tiền giang": "Tiền Giang", "tien giang": "Tiền Giang",
    "đồng nai": "Đồng Nai", "dong nai": "Đồng Nai",
    "lâm đồng": "Lâm Đồng", "lam dong": "Lâm Đồng",
    "đà lạt": "Đà Lạt", "da lat": "Đà Lạt",
    "an giang": "An Giang",
    "bắc giang": "Bắc Giang", "bac giang": "Bắc Giang",
    "bến tre": "Bến Tre", "ben tre": "Bến Tre",
    "bình định": "Bình Định", "binh dinh": "Bình Định",
    "bình dương": "Bình Dương", "binh duong": "Bình Dương",
    "bình thuận": "Bình Thuận", "binh thuan": "Bình Thuận",
    "đồng tháp": "Đồng Tháp", "dong thap": "Đồng Tháp",
    "hà giang": "Hà Giang", "ha giang": "Hà Giang",
    "hải dương": "Hải Dương", "hai duong": "Hải Dương",
    "hậu giang": "Hậu Giang", "hau giang": "Hậu Giang",
    "hưng yên": "Hưng Yên", "hung yen": "Hưng Yên",
    "khánh hòa": "Khánh Hòa", "khanh hoa": "Khánh Hòa",
    "kiên giang": "Kiên Giang", "kien giang": "Kiên Giang",
    "kon tum": "Kon Tum",
    "long an": "Long An",
    "nghệ an": "Nghệ An", "nghe an": "Nghệ An",
    "quảng ngãi": "Quảng Ngãi", "quang ngai": "Quảng Ngãi",
    "sóc trăng": "Sóc Trăng", "soc trang": "Sóc Trăng",
    "sơn la": "Sơn La", "son la": "Sơn La",
    "tây ninh": "Tây Ninh", "tay ninh": "Tây Ninh",
    "vĩnh long": "Vĩnh Long", "vinh long": "Vĩnh Long",
}
DEFAULT_PRICE_REGION = "Đà Nẵng"

def _detect_region(question: str) -> str:
    q = question.lower()
    for key, region in _REGION_KEYWORDS.items():
        if key in q:
            return region
    return DEFAULT_PRICE_REGION


def _detect_crop(question: str) -> str:
    return extract_crop_from_message(question) or "lua"


@router.post("", response_model=ChatResponse)
async def ask_farming_advice(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    context_parts = []
    if request.context_data:
        context_parts.append(request.context_data)

    q = request.question
    intent = classify_user_intent(q)
    if intent == "greeting":
        _save_conversation(db, current_user.UserID if current_user else None, q, GREETING_REPLY, intent)
        return ChatResponse(answer=GREETING_REPLY)
    if intent == "general_question" and is_capability_question(q):
        _save_conversation(db, current_user.UserID if current_user else None, q, GENERAL_CAPABILITY_REPLY, intent)
        return ChatResponse(answer=GENERAL_CAPABILITY_REPLY)

    # Legacy /api/chat now reuses the same context builder used by /api/ai-chat.
    try:
        from app.services.ai_context_service import ai_context_service
        from app.services.claude_service import claude_service

        try:
            context = ai_context_service.build_ai_context(
                db,
                user_id=current_user.UserID if current_user else request.user_id,
                region=extract_region_from_message(q) or _detect_region(q),
                crop=extract_crop_from_message(q) or _detect_crop(q),
                intent=intent,
            )
        except Exception:
            context = {
                "intent": intent,
                "region": extract_region_from_message(q) or _detect_region(q),
                "crop_name": extract_crop_from_message(q) or _detect_crop(q),
            }

        if request.context_data:
            context["legacy_context_data"] = request.context_data
        result = await claude_service.answer_question(
            db,
            question=q,
            user_id=current_user.UserID if current_user else request.user_id,
            crop_name=context.get("crop_name"),
            region=context.get("region"),
            extra_context=context,
        )
        answer = result.get("answer") or result.get("error")
        if not answer:
            answer = _build_local_fallback_answer(
                q,
                topic=intent,
                region=context.get("region"),
                crop=context.get("crop_name"),
            )
        _save_conversation(db, current_user.UserID if current_user else None, q, answer, intent)
        return ChatResponse(answer=answer)
    except Exception:
        answer = _build_local_fallback_answer(
            q,
            topic=intent,
            region=extract_region_from_message(q) or _detect_region(q),
            crop=extract_crop_from_message(q) or _detect_crop(q),
        )
        try:
            _save_conversation(db, current_user.UserID if current_user else None, q, answer, intent)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return ChatResponse(answer=answer)

    # RAG 1: Bổ sung giá thị trường từ DB nếu câu hỏi liên quan đến giá
    if _question_contains(q, _PRICE_KEYWORDS):
        try:
            from sqlalchemy import text
            query = text("""
                SELECT TOP 20 c.CropName, m.Region, m.PricePerKg, m.SourceName, m.PriceDate
                FROM MarketPrices m
                JOIN CropTypes c ON m.CropID = c.CropID
                ORDER BY m.PriceDate DESC
            """)
            rows = db.execute(query).fetchall()
            if rows:
                lines = ["## Giá thị trường từ hệ thống (cập nhật gần nhất):"]
                for r in rows:
                    lines.append(
                        f"- {r[0]} tại {r[1]}: **{float(r[2]):,.0f} VNĐ/kg** "
                        f"(nguồn: {r[3]}, ngày {r[4]})"
                    )
                context_parts.append("\n".join(lines))
        except Exception as e:
            print(f"[Chat RAG-price] Lỗi: {e}")

    # RAG 2: Bổ sung thông tin chu kỳ sinh trưởng từ DB nếu hỏi về cây trồng
    if _question_contains(q, _CROP_KEYWORDS + _PEST_KEYWORDS):
        try:
            from sqlalchemy import text
            crop_query = text("""
                SELECT TOP 10 CropName, GrowthDurationDays, HarvestSeason,
                       TypicalPriceMin, TypicalPriceMax
                FROM CropTypes
                ORDER BY CropName
            """)
            crops = db.execute(crop_query).fetchall()
            if crops:
                lines = ["## Thông tin cây trồng trong hệ thống:"]
                for c in crops:
                    price_range = ""
                    if c[3] and c[4]:
                        price_range = f", giá điển hình: {float(c[3]):,.0f}–{float(c[4]):,.0f} VNĐ/kg"
                    days = f", chu kỳ: {c[1]} ngày" if c[1] else ""
                    season = f", mùa vụ: {c[2]}" if c[2] else ""
                    lines.append(f"- {c[0]}{days}{season}{price_range}")
                context_parts.append("\n".join(lines))
        except Exception as e:
            print(f"[Chat RAG-crop] Lỗi: {e}")

    # RAG 3: Bổ sung lịch sử giá 7 ngày gần nhất để phân tích xu hướng
    if _question_contains(q, _PRICE_KEYWORDS):
        try:
            from sqlalchemy import text
            trend_query = text("""
                SELECT TOP 30 c.CropName, ph.Region, ph.AvgPrice, ph.MinPrice,
                       ph.MaxPrice, ph.RecordDate
                FROM PriceHistory ph
                JOIN CropTypes c ON ph.CropID = c.CropID
                WHERE ph.RecordDate >= DATEADD(day, -7, GETDATE())
                ORDER BY ph.RecordDate DESC
            """)
            hist = db.execute(trend_query).fetchall()
            if hist:
                lines = ["## Lịch sử giá 7 ngày gần nhất:"]
                for h in hist:
                    lines.append(
                        f"- {h[0]} tại {h[1]} ngày {h[5]}: "
                        f"TB {float(h[2]):,.0f} | Min {float(h[3]):,.0f} | Max {float(h[4]):,.0f} VNĐ/kg"
                    )
                context_parts.append("\n".join(lines))
        except Exception as e:
            print(f"[Chat RAG-trend] Lỗi: {e}")

    combined_context = "\n\n".join(context_parts)

    try:
        answer = await gemini_client.get_farming_advice(
            question=q,
            context_data=combined_context
        )
        _save_conversation(db, current_user.UserID if current_user else None, q, answer)
        return ChatResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi kết nối AI: {str(e)}")


@router.post("/price-qa", response_model=PriceQAResponse)
async def price_qa(
    request: PriceQARequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    from datetime import date as _date, timedelta
    from app.models.crop import Crop as _Crop
    from app.models.price import MarketPrice as _MP, PriceHistory as _PH

    q = request.question
    region = _detect_region(q)
    crop = _detect_crop(q)
    try:
        from app.services.ai_context_service import ai_context_service
        from app.services.claude_service import claude_service
        from app.services.pricing_service import pricing_service

        current = pricing_service.get_current_price(db, crop, region, include_weather=False)
        if current.get("_api_error"):
            answer = current.get("error_message") or "Chưa có dữ liệu giá thật trong cache cho câu hỏi này."
            _save_conversation(db, current_user.UserID if current_user else None, q, answer, "price_query")
            return PriceQAResponse(answer=answer, tavily_answer="", sources=[], db_prices=[])
        history = pricing_service.get_price_history(db, crop, region, days=7)
        try:
            context = ai_context_service.build_ai_context(
                db,
                user_id=current_user.UserID if current_user else None,
                region=region,
                crop=crop,
                intent="price_query",
            )
        except Exception:
            context = {"intent": "price_query", "region": region, "crop_name": crop}
        result = await claude_service.answer_question(
            db,
            question=q,
            user_id=current_user.UserID if current_user else None,
            crop_name=crop,
            region=region,
            extra_context=context,
        )
        answer = result.get("answer") or result.get("error")
        if not answer:
            answer = _build_local_fallback_answer(q, topic="price_query", region=region, crop=crop)
        _save_conversation(db, current_user.UserID if current_user else None, q, answer, "price_query")
        return PriceQAResponse(
            answer=answer,
            tavily_answer="",
            sources=context.get("data_sources", []),
            db_prices=[
                {
                    "crop_name": current.get("crop_name"),
                    "region": current.get("region"),
                    "price": current.get("current_price"),
                    "unit": "VND/kg",
                    "source": current.get("source"),
                    "source_name": current.get("source_name"),
                    "date": str(current.get("price_date") or current.get("last_updated")),
                    "history": history,
                }
            ],
        )
    except Exception:
        pass
    _seven_ago = _date.today() - timedelta(days=7)

    def _mp_row(mp, name):
        return {
            "crop_name": name, "region": mp.Region,
            "price": float(mp.PricePerKg),
            "source": mp.SourceName or "",
            "date": str(mp.PriceDate),
        }

    # ── Bước 1: Giá mới nhất theo vùng ────────────────────────────────────
    db_prices: list[dict] = []
    try:
        rows = (
            db.query(_Crop.CropName, _MP)
            .join(_MP, _Crop.CropID == _MP.CropID)
            .filter(_MP.Region == region)
            .order_by(_MP.PriceDate.desc())
            .limit(15).all()
        )
        if not rows:
            rows = (
                db.query(_Crop.CropName, _MP)
                .join(_MP, _Crop.CropID == _MP.CropID)
                .order_by(_MP.PriceDate.desc())
                .limit(15).all()
            )
        db_prices = [_mp_row(mp, name) for name, mp in rows]
    except Exception:
        pass

    # ── Bước 2: Lịch sử 7 ngày theo vùng ─────────────────────────────────
    price_history: list = []
    try:
        hist = (
            db.query(_Crop.CropName, _PH)
            .join(_PH, _Crop.CropID == _PH.CropID)
            .filter(_PH.Region == region, _PH.RecordDate >= _seven_ago)
            .order_by(_PH.RecordDate.desc())
            .limit(50).all()
        )
        if not hist:
            hist = (
                db.query(_Crop.CropName, _PH)
                .join(_PH, _Crop.CropID == _PH.CropID)
                .filter(_PH.RecordDate >= _seven_ago)
                .order_by(_PH.RecordDate.desc())
                .limit(50).all()
            )
        price_history = [(name, ph) for name, ph in hist]
    except Exception:
        pass

    # ── Bước 3 extra: Luôn lấy top giá toàn quốc làm tham chiếu ──────────
    national_rows: list = []
    try:
        national_rows = (
            db.query(_Crop.CropName, _MP)
            .join(_MP, _Crop.CropID == _MP.CropID)
            .order_by(_MP.PriceDate.desc())
            .limit(30).all()
        )
    except Exception:
        pass

    # ── Xây context cho AI: vùng cụ thể + toàn quốc tham chiếu ───────────
    ctx_parts: list[str] = []

    if db_prices:
        lines = [f"## Giá tại {region} (mới nhất):"]
        for p in db_prices:
            lines.append(f"- {p['crop_name']} ({p['region']}): {p['price']:,.0f} VNĐ/kg — {p['date']}")
        ctx_parts.append("\n".join(lines))

    if price_history:
        lines = [f"## Lịch sử giá 7 ngày tại {region}:"]
        for name, ph in price_history:
            lines.append(
                f"- {name} ({ph.Region}) ngày {ph.RecordDate}: "
                f"TB {float(ph.AvgPrice):,.0f} | Min {float(ph.MinPrice or 0):,.0f} | Max {float(ph.MaxPrice or 0):,.0f} VNĐ/kg"
            )
        ctx_parts.append("\n".join(lines))

    if national_rows:
        lines = ["## Giá toàn quốc (tham chiếu khi vùng trên thiếu dữ liệu):"]
        for name, mp in national_rows:
            lines.append(f"- {name} tại {mp.Region}: {float(mp.PricePerKg):,.0f} VNĐ/kg — {mp.PriceDate}")
        ctx_parts.append("\n".join(lines))

    db_context = "\n\n".join(ctx_parts)

    # ── Bước 3: Tavily Search ──────────────────────────────────────────────
    tavily_answer = ""
    sources: list = []
    full_answer = ""
    try:
        from app.integrations.tavily_client import ask_price_qa
        import asyncio
        from app.core.config import settings
        result = await asyncio.wait_for(
            asyncio.to_thread(ask_price_qa, f"{q} tại {region}", db_context),
            timeout=settings.AI_TIMEOUT_SECONDS,
        )
        tavily_answer = result.get("tavily_answer", "")
        sources = result.get("sources", [])
        full_answer = result.get("answer", "")
    except Exception:
        pass

    # ── Bước 4: Gemini với prompt ngắn gọn về giá ─────────────────────────
    if not tavily_answer:
        try:
            full_answer = await gemini_client.get_price_answer(q, region, db_context)
        except Exception:
            pass

    # ── Bước 5: Fallback thuần DB nếu AI fail ─────────────────────────────
    _is_ai_fail = (
        not full_answer
        or full_answer.startswith("Xin lỗi")
        or full_answer.startswith("Lỗi AI")
        or "đang bận" in full_answer
    )
    if _is_ai_fail:
        if db_prices:
            lines = [f"**Giá nông sản tại {region}** *(AI tạm bận — dữ liệu thô từ hệ thống)*\n"]
            for p in db_prices:
                lines.append(f"- **{p['crop_name']}**: {p['price']:,.0f} VNĐ/kg — {p['date']}")
            full_answer = "\n".join(lines)
        else:
            full_answer = _build_local_fallback_answer(q, topic="price_query", region=region, crop=crop)

    _save_conversation(db, current_user.UserID if current_user else None, q, full_answer, "price_query")

    return PriceQAResponse(
        answer=full_answer,
        tavily_answer=tavily_answer,
        sources=sources,
        db_prices=db_prices,
    )


class AskResponse(BaseModel):
    answer: str
    topic: str = "general"
    region: str = ""
    sources: list = []


@router.post("/ask", response_model=AskResponse)
async def ask_agri(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    """Endpoint thống nhất: tự phát hiện chủ đề (giá, thời tiết, đất phèn/mặn, sâu bệnh, canh tác)."""
    from datetime import date as _date, timedelta
    from app.models.crop import Crop as _Crop
    from app.models.price import MarketPrice as _MP, PriceHistory as _PH

    q = request.question
    intent = classify_user_intent(q)
    region = extract_region_from_message(q) or _detect_region(q)
    if intent == "greeting":
        _save_conversation(db, current_user.UserID if current_user else None, q, GREETING_REPLY, intent)
        return AskResponse(answer=GREETING_REPLY, topic=intent, region=region, sources=[])
    if intent == "general_question" and is_capability_question(q):
        _save_conversation(db, current_user.UserID if current_user else None, q, GENERAL_CAPABILITY_REPLY, intent)
        return AskResponse(answer=GENERAL_CAPABILITY_REPLY, topic=intent, region=region, sources=[])
    fallback_topic = _detect_topic(q)
    topic = intent if intent != "general_question" else fallback_topic
    try:
        from app.services.ai_context_service import ai_context_service
        from app.services.claude_service import claude_service

        try:
            context = ai_context_service.build_ai_context(
                db,
                user_id=current_user.UserID if current_user else request.user_id,
                region=region,
                crop=extract_crop_from_message(q) or _detect_crop(q),
                intent=topic,
            )
        except Exception:
            context = {
                "intent": topic,
                "region": region,
                "crop_name": extract_crop_from_message(q) or _detect_crop(q),
            }
        result = await claude_service.answer_question(
            db,
            question=q,
            user_id=current_user.UserID if current_user else request.user_id,
            crop_name=context.get("crop_name"),
            region=context.get("region"),
            extra_context=context,
        )
        answer = result.get("answer", "")
        _save_conversation(db, current_user.UserID if current_user else None, q, answer, topic)
        return AskResponse(
            answer=answer,
            topic=topic,
            region=region,
            sources=context.get("data_sources", []),
        )
    except Exception:
        topic = fallback_topic
    _seven_ago = _date.today() - timedelta(days=7)
    ctx_parts: list[str] = []
    sources: list = []

    # ── Context theo chủ đề ──────────────────────────────────────────────────
    if topic == "weather":
        ctx_parts.append(_build_weather_context(db, region))

    elif topic == "soil_salinity":
        ctx_parts.append(_SALINITY_KNOWLEDGE)

    elif topic == "soil_acidity":
        ctx_parts.append(_ACIDITY_KNOWLEDGE)

    elif topic == "price":
        try:
            rows = (
                db.query(_Crop.CropName, _MP)
                .join(_MP, _Crop.CropID == _MP.CropID)
                .filter(_MP.Region == region)
                .order_by(_MP.PriceDate.desc())
                .limit(15).all()
            )
            if not rows:
                rows = (
                    db.query(_Crop.CropName, _MP)
                    .join(_MP, _Crop.CropID == _MP.CropID)
                    .order_by(_MP.PriceDate.desc())
                    .limit(15).all()
                )
            if rows:
                lines = [f"## Giá tại {region}:"]
                for name, mp in rows:
                    lines.append(f"- {name} ({mp.Region}): {float(mp.PricePerKg):,.0f} VNĐ/kg — {mp.PriceDate}")
                ctx_parts.append("\n".join(lines))
            hist = (
                db.query(_Crop.CropName, _PH)
                .join(_PH, _Crop.CropID == _PH.CropID)
                .filter(_PH.RecordDate >= _seven_ago)
                .order_by(_PH.RecordDate.desc())
                .limit(30).all()
            )
            if hist:
                lines = ["## Lịch sử giá 7 ngày:"]
                for name, ph in hist:
                    lines.append(f"- {name} ({ph.Region}) ngày {ph.RecordDate}: TB {float(ph.AvgPrice):,.0f} VNĐ/kg")
                ctx_parts.append("\n".join(lines))
        except Exception:
            pass

    # Canh tác, sâu bệnh, general: bổ sung thông tin cây trồng từ DB
    if topic in ("cultivation", "pest", "general"):
        try:
            crops = (
                db.query(_Crop)
                .order_by(_Crop.CropName)
                .limit(15).all()
            )
            if crops:
                lines = ["## Thông tin cây trồng:"]
                for c in crops:
                    days = f", chu kỳ {c.GrowthDurationDays} ngày" if c.GrowthDurationDays else ""
                    season = f", mùa vụ: {c.HarvestSeason}" if c.HarvestSeason else ""
                    price_range = (
                        f", giá: {float(c.TypicalPriceMin):,.0f}–{float(c.TypicalPriceMax):,.0f} VNĐ/kg"
                        if c.TypicalPriceMin and c.TypicalPriceMax else ""
                    )
                    lines.append(f"- {c.CropName}{days}{season}{price_range}")
                ctx_parts.append("\n".join(lines))
        except Exception:
            pass

    # ── Tavily cho thời tiết, đất, sâu bệnh (thông tin web thực tế) ─────────
    if topic in ("weather", "soil_salinity", "soil_acidity", "pest"):
        try:
            import asyncio
            from app.core.config import settings
            from app.integrations.tavily_client import ask_agri_qa
            result = await asyncio.wait_for(
                asyncio.to_thread(ask_agri_qa, q, "\n\n".join(ctx_parts)),
                timeout=settings.AI_TIMEOUT_SECONDS,
            )
            if result.get("tavily_answer"):
                ctx_parts.append(f"## Thông tin từ web:\n{result['tavily_answer']}")
            sources = result.get("sources", [])
        except Exception:
            pass

    context = "\n\n".join(ctx_parts)

    # ── Gọi AI với system prompt theo chủ đề ────────────────────────────────
    try:
        answer = await gemini_client.get_agri_answer(q, topic, region, context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi AI: {str(e)}")

    _save_conversation(db, current_user.UserID if current_user else None, q, answer, topic)
    return AskResponse(answer=answer, topic=topic, region=region, sources=sources)


@router.get("/history")
def get_chat_history(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.conversation import AIConversation

    base_query = db.query(AIConversation).filter(AIConversation.UserID == current_user.UserID)
    total = base_query.count()
    rows = (
        base_query
        .order_by(AIConversation.CreatedAt.desc())
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "history": [
            {
                "id": r.ConvID,
                "user_message": r.UserMessage,
                "ai_response": r.AIResponse,
                "topic": r.Topic,
                "created_at": r.CreatedAt.isoformat() if r.CreatedAt else None,
            }
            for r in rows
        ],
    }


@router.delete("/history/{conv_id}", status_code=200)
def delete_chat_message(
    conv_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xóa một tin nhắn khỏi lịch sử chat."""
    from app.models.conversation import AIConversation
    row = (
        db.query(AIConversation)
        .filter(AIConversation.ConvID == conv_id, AIConversation.UserID == current_user.UserID)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy tin nhắn")
    db.delete(row)
    db.commit()
    return {"deleted": conv_id}


@router.delete("/history", status_code=200)
def clear_chat_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xóa toàn bộ lịch sử chat của người dùng."""
    from app.models.conversation import AIConversation
    count = (
        db.query(AIConversation)
        .filter(AIConversation.UserID == current_user.UserID)
        .delete()
    )
    db.commit()
    return {"deleted_count": count}
