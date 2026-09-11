from fastapi.testclient import TestClient

from app.api.ai_chat import AIChatMessageRequest, _build_gemini_prompt
from app.main import app
from app.services.ai_context_service import AIContextService
from app.services.ai_intent_service import classify_user_intent


client = TestClient(app)


def test_classify_greeting_does_not_match_price():
    assert classify_user_intent("chào bạn") == "greeting"
    assert classify_user_intent("bạn ơi") == "greeting"


def test_classify_analysis_intents():
    assert classify_user_intent("phân tích giá cà chua ở Hà Nội hôm nay") == "price_analysis"
    assert classify_user_intent("hôm nay có nên tưới lúa không?") == "weather_analysis"
    assert classify_user_intent("mùa vụ của tôi khi nào thu hoạch?") == "harvest_analysis"
    assert classify_user_intent("có cảnh báo gì không") == "alert_analysis"
    assert classify_user_intent("phân tích tình hình nông trại") == "full_farm_analysis"


def test_cultivation_question_is_not_misrouted_to_harvest_analysis():
    assert classify_user_intent("Kỹ thuật trồng cà phê vụ mới") == "cultivation_advice"
    assert classify_user_intent("Cà phê Robusta cần chuẩn bị đất như thế nào?") == "cultivation_advice"


def test_cultivation_prompt_excludes_unrelated_national_season_calendar():
    request = AIChatMessageRequest(message="Kỹ thuật trồng cà phê vụ mới")
    _, prompt = _build_gemini_prompt(request, {
        "intent": "cultivation_advice",
        "crop_name": "cà phê",
        "region": None,
        "rag": {"status": "ready", "sources": []},
    })

    assert "LỊCH MÙA VỤ HIỆN TẠI" not in prompt
    assert "Các bước thực hiện" in prompt
    assert "phân tích thu hoạch" not in prompt.lower()
    assert "cultivation_advice" not in prompt
    assert "tối đa 6 gạch đầu dòng và 140 từ" in prompt


def test_model_prompt_keeps_rag_evidence_but_omits_long_source_urls():
    request = AIChatMessageRequest(message="Cách chăm sóc cà phê?")
    _, prompt = _build_gemini_prompt(request, {
        "intent": "cultivation_advice",
        "crop_name": "cà phê",
        "region": "Đắk Lắk",
        "rag": {"status": "ready", "sources": [{
            "citation": "TL1",
            "name": "Hướng dẫn cà phê.pdf",
            "source_name": "VAAS",
            "source_url": "https://vaas.vn/a-very-long-encoded-document-url.pdf",
            "page": 4,
            "excerpt": "Giữ ẩm đất và kiểm tra thoát nước.",
            "score": 0.81,
        }]},
    })

    assert "Giữ ẩm đất và kiểm tra thoát nước" in prompt
    assert "[TL1]" in prompt
    assert "Hướng dẫn cà phê.pdf" in prompt
    assert "a-very-long-encoded-document-url" not in prompt
    assert '"score"' not in prompt
    assert "không áp dụng số liệu hoặc quy trình của nguồn đó" in _build_gemini_prompt(request, {
        "intent": "cultivation_advice",
        "crop_name": "cà phê",
        "region": "Đắk Lắk",
        "rag": {"status": "ready", "sources": []},
    })[0]


def test_context_general_question_does_not_load_default_agri_data(monkeypatch):
    calls: list[str] = []
    import app.services.ai_context_service as context_module

    monkeypatch.setattr(
        context_module.agri_data_aggregator_service,
        "get_weather_bundle",
        lambda *args, **kwargs: calls.append("weather") or {},
    )
    monkeypatch.setattr(
        context_module.agri_data_aggregator_service,
        "get_pricing_bundle",
        lambda *args, **kwargs: calls.append("pricing") or {},
    )
    monkeypatch.setattr(
        context_module.agri_data_aggregator_service,
        "get_market_bundle",
        lambda *args, **kwargs: calls.append("market") or {},
    )
    monkeypatch.setattr(
        context_module.agri_data_aggregator_service,
        "get_alert_notification_bundle",
        lambda *args, **kwargs: calls.append("alerts") or {},
    )

    context = AIContextService().build_ai_context(
        None,
        region="Hà Nội",
        crop="cà chua",
        intent="general_question",
    )

    assert calls == []
    assert context["intent"] == "general_question"
    assert context["pricing"] == {}
    assert context["weather"] == {}
    assert context["market"] == {"news": [], "trends": {}, "opportunities": [], "risks": []}


def test_context_price_analysis_only_loads_price_and_market(monkeypatch):
    calls: list[str] = []
    import app.services.ai_context_service as context_module

    monkeypatch.setattr(
        context_module.agri_data_aggregator_service,
        "get_weather_bundle",
        lambda *args, **kwargs: calls.append("weather") or {},
    )
    monkeypatch.setattr(
        context_module.agri_data_aggregator_service,
        "get_pricing_bundle",
        lambda *args, **kwargs: calls.append("pricing") or {"current": {"current_price": 10000}},
    )
    monkeypatch.setattr(
        context_module.agri_data_aggregator_service,
        "get_market_bundle",
        lambda *args, **kwargs: calls.append("market") or {"trends": {"trend": "stable"}},
    )
    monkeypatch.setattr(
        context_module.agri_data_aggregator_service,
        "get_alert_notification_bundle",
        lambda *args, **kwargs: calls.append("alerts") or {},
    )

    context = AIContextService().build_ai_context(
        None,
        region="Hà Nội",
        crop="cà chua",
        intent="price_analysis",
    )

    assert calls == ["pricing", "market"]
    assert context["pricing"]["current_price"] == 10000
    assert context["weather"] == {}
    assert context["alerts"] == []


def test_ai_chat_greeting_returns_local_reply_without_market_analysis():
    response = client.post("/api/ai-chat/message", json={"message": "chào bạn"})

    assert response.status_code == 200
    payload = response.json()
    reply = payload["reply"].lower()
    assert payload["data"]["intent"] == "greeting"
    assert "chào bạn" in reply
    assert "giá cà chua" not in reply
    assert "thời tiết hà nội" not in reply


def test_broad_cultivation_question_requests_region_variety_and_planting_stage():
    response = client.post("/api/ai-chat/message", json={
        "message": "Kỹ thuật trồng cà phê vụ mới",
    })

    assert response.status_code == 200
    payload = response.json()
    reply = payload["reply"].lower()
    assert payload["data"]["intent"] == "cultivation_advice"
    assert payload["data"]["model"] == "intent-router-v1"
    assert "khu vực" in reply
    assert "robusta" in reply and "arabica" in reply
    assert "trồng mới" in reply and "tái canh" in reply


def test_cultivation_without_matching_document_does_not_invent_numbers_or_citations(monkeypatch):
    monkeypatch.setattr(
        "app.api.ai_chat.rag_service.retrieve",
        lambda *args, **kwargs: {"status": "no_match", "sources": []},
    )
    response = client.post("/api/ai-chat/message", json={
        "message": "Tôi ở Đắk Lắk, trồng mới cà phê vối Robusta. Cần chuẩn bị đất như thế nào?",
    })

    assert response.status_code == 200
    payload = response.json()
    reply = payload["reply"].lower()
    assert payload["data"]["model"] == "rag-safety-router-v1"
    assert "chưa có nguồn" in reply
    assert "phân tích đất" in reply
    assert "[tl" not in reply
    assert "kg" not in reply and "tấn/ha" not in reply
