"""
TDD: trợ lý AI dùng provider theo cấu hình và trả lời dựa trên dữ liệu thật.

_call_claude gọi thẳng ai_client.client.messages.create(...) — API riêng của
Anthropic — nên khi AI_PROVIDER=ollama vẫn không dùng được model local.

Cần một nhánh gọi qua seam chung get_ai_client().complete(), và prompt phải
mang theo số liệu thật từ DB: model 7B không biết giá cà phê hôm nay, nó chỉ
diễn giải được số liệu mình đưa vào.
"""
import pytest

from app.api.ai_chat import _call_local_ai
from app.api.ai_chat import AIChatMessageRequest


class _ClientGia:
    """Client giả ghi lại prompt nhận được."""
    def __init__(self, answer="Giá cà phê Đắk Lắk hôm nay 96.433 đ/kg."):
        self.answer = answer
        self.nhan = {}
        self.model = "qwen2.5:7b-instruct-q4_K_M"

    def complete(self, messages, system_prompt="", max_tokens=1024):
        self.nhan = {"messages": messages, "system": system_prompt}
        return {"answer": self.answer, "provider": "ollama", "model": self.model,
                "token_usage": None, "is_mock": False, "error": None}


@pytest.mark.asyncio
async def test_dung_provider_theo_cau_hinh(monkeypatch):
    fake = _ClientGia()
    monkeypatch.setattr("app.api.ai_chat.get_ai_client", lambda: fake)

    req = AIChatMessageRequest(message="Giá cà phê hôm nay?")
    reply, model = await _call_local_ai(req, {})

    assert reply == fake.answer
    assert "qwen" in model.lower()


@pytest.mark.asyncio
async def test_prompt_mang_theo_so_lieu_that(monkeypatch):
    fake = _ClientGia()
    monkeypatch.setattr("app.api.ai_chat.get_ai_client", lambda: fake)

    req = AIChatMessageRequest(message="Giá cà phê hôm nay?")
    await _call_local_ai(req, {"prices": [{"crop": "Cà phê", "region": "Đắk Lắk",
                                           "price": 96433}]})

    het_prompt = str(fake.nhan)
    assert "96433" in het_prompt or "96.433" in het_prompt, (
        "Số liệu thật không được đưa vào prompt — model sẽ đoán bừa"
    )


@pytest.mark.asyncio
async def test_ai_loi_thi_bao_that(monkeypatch):
    class Hong(_ClientGia):
        def complete(self, *a, **kw):
            return {"answer": "Không thể kết nối trợ lý AI.", "provider": "ollama",
                    "model": self.model, "token_usage": None, "is_mock": False,
                    "error": "connection refused"}
    monkeypatch.setattr("app.api.ai_chat.get_ai_client", lambda: Hong())

    req = AIChatMessageRequest(message="Giá cà phê hôm nay?")
    with pytest.raises(RuntimeError):
        await _call_local_ai(req, {})


@pytest.mark.asyncio
async def test_endpoint_uu_tien_provider_local(monkeypatch):
    """AI_PROVIDER=ollama => dùng model local, không gọi Gemini/Claude."""
    goi = []

    async def gemini_khong_duoc_goi(*a, **kw):
        goi.append("gemini")
        raise RuntimeError("khong duoc goi Gemini khi cau hinh local")

    async def local(*a, **kw):
        goi.append("local")
        return "Trả lời từ model local.", "qwen2.5:7b-instruct-q4_K_M"

    monkeypatch.setattr("app.core.config.settings.AI_PROVIDER", "ollama")
    monkeypatch.setattr("app.api.ai_chat._call_gemini", gemini_khong_duoc_goi)
    monkeypatch.setattr("app.api.ai_chat._call_local_ai", local)

    from app.api.ai_chat import _chon_provider
    fn, ten = _chon_provider()
    reply, _ = await fn(AIChatMessageRequest(message="Xin chào"), {})

    assert ten == "ollama"
    assert goi == ["local"], f"Gọi sai thứ tự: {goi}"


def test_api_chat_dung_provider_local(monkeypatch):
    """/api/chat (router chat.py) cũng phải qua seam chung, không cứng Gemini."""
    from fastapi.testclient import TestClient
    from app.main import app

    class FakeLocal:
        model = "qwen2.5:3b-instruct-q4_K_M"
        async def get_farming_advice(self, question, context_data=""):
            return "Cà chua cần đất tơi xốp, thoát nước tốt."
        def complete(self, messages, system_prompt="", max_tokens=1024):
            return {"answer": "Cà chua cần đất tơi xốp, thoát nước tốt.",
                    "provider": "ollama", "model": self.model,
                    "token_usage": None, "is_mock": False, "error": None}

    monkeypatch.setattr("app.api.chat.get_ai_client", lambda: FakeLocal(), raising=False)

    r = TestClient(app).post("/api/chat", json={"question": "Trồng cà chua thế nào?"})
    assert r.status_code == 200
    answer = r.json().get("answer", "")
    assert "tơi xốp" in answer, f"Không dùng model local: {answer[:100]!r}"
