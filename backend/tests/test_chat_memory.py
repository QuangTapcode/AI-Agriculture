"""
TDD: chatbot phải nhớ các lượt trước trong cùng cuộc hội thoại.

Hiện lịch sử ĐƯỢC LƯU (_save_conversation) và ĐƯỢC ĐỌC RA để hiển thị, nhưng
không bao giờ đưa lại vào prompt. Mỗi câu hỏi là một lượt độc lập.

Hệ quả thật: hỏi "Giá cà phê Đắk Lắk?" rồi hỏi tiếp "Còn Gia Lai thì sao?"
-> model không biết "còn... thì sao" đang nói về cà phê. Đó là hỏi-đáp một
lượt, không phải chatbot.
"""
import json

import httpx
import pytest

from app.integrations.ollama_client import OllamaClient


def _bat_prompt():
    """Transport ghi lại messages gửi cho model."""
    nhan = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nhan["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"content": "ok"}})

    return httpx.MockTransport(handler), nhan


@pytest.mark.asyncio
async def test_gui_kem_luot_truoc_cho_model():
    """Có lịch sử => phải nằm trong messages, đúng thứ tự, đúng vai."""
    transport, nhan = _bat_prompt()
    client = OllamaClient(transport=transport)

    lich_su = [
        {"role": "user", "content": "Giá cà phê Đắk Lắk?"},
        {"role": "assistant", "content": "Cà phê Đắk Lắk hôm nay 96.433 đ/kg."},
    ]
    await client.get_farming_advice("Còn Gia Lai thì sao?", lich_su=lich_su)

    msgs = nhan["body"]["messages"]
    vai = [m["role"] for m in msgs]
    assert vai == ["system", "user", "assistant", "user"], (
        f"Thứ tự/vai sai: {vai}"
    )
    assert "96.433" in msgs[2]["content"], "Câu trả lời trước bị mất"
    assert "Còn Gia Lai" in msgs[-1]["content"], "Câu hỏi mới phải ở cuối"


@pytest.mark.asyncio
async def test_khong_co_lich_su_van_chay_binh_thuong():
    """Lượt đầu tiên không có gì để nhớ — không được vỡ."""
    transport, nhan = _bat_prompt()
    client = OllamaClient(transport=transport)

    await client.get_farming_advice("Trồng cà chua thế nào?")

    vai = [m["role"] for m in nhan["body"]["messages"]]
    assert vai == ["system", "user"]


@pytest.mark.asyncio
async def test_cat_bot_lich_su_qua_dai():
    """Nhồi cả trăm lượt sẽ tràn context 4096 token của model 3B.

    Giữ vài lượt gần nhất là đủ để hiểu đại từ ("còn ... thì sao").
    """
    transport, nhan = _bat_prompt()
    client = OllamaClient(transport=transport)

    dai = []
    for i in range(50):
        dai.append({"role": "user", "content": f"cau hoi {i}"})
        dai.append({"role": "assistant", "content": f"tra loi {i}"})

    await client.get_farming_advice("Câu mới nhất", lich_su=dai)

    msgs = nhan["body"]["messages"]
    assert len(msgs) <= 13, f"Gửi {len(msgs)} tin nhắn — sẽ tràn context"
    # Lượt gần nhất phải được giữ, lượt cũ nhất bị cắt
    noi_dung = " ".join(m["content"] for m in msgs)
    assert "tra loi 49" in noi_dung, "Mất lượt gần nhất"
    assert "cau hoi 0" not in noi_dung, "Vẫn giữ lượt quá cũ"


# ── Nối lịch sử thật từ DB vào endpoint ──────────────────────────────────

def test_endpoint_dua_lich_su_cua_dung_nguoi_dung(monkeypatch):
    """/api/chat phải lấy lượt trước của CHÍNH người dùng đó rồi gửi kèm."""
    from fastapi.testclient import TestClient

    from app.main import app

    nhan = {}

    class FakeAI:
        model = "qwen2.5:3b-instruct-q4_K_M"

        async def get_farming_advice(self, question, context_data="", lich_su=None):
            nhan["lich_su"] = lich_su
            return "Gia Lai hôm nay 95.000 đ/kg."

    monkeypatch.setattr("app.api.chat.get_ai_client", lambda: FakeAI(), raising=False)
    monkeypatch.setattr(
        "app.api.chat._lay_lich_su",
        lambda db, user_id, limit=6: [
            {"role": "user", "content": "Giá cà phê Đắk Lắk?"},
            {"role": "assistant", "content": "96.433 đ/kg."},
        ],
        raising=False,
    )

    r = TestClient(app).post("/api/chat", json={"question": "Còn Gia Lai thì sao?"})

    assert r.status_code == 200
    assert nhan.get("lich_su"), "Endpoint không truyền lịch sử cho model"
    assert "96.433" in str(nhan["lich_su"]), "Lượt trước bị mất"


# ── Trí nhớ không được biến thành nguồn bịa số ───────────────────────────

def test_quy_tac_cam_suy_so_lieu_tu_luot_truoc():
    """Lượt trả lời trước KHÔNG phải nguồn dữ liệu cho câu hỏi mới.

    Hồi quy quan sát được khi thêm trí nhớ: cho model biết
    "Cà phê Đắk Lắk 96.433 đ/kg" rồi hỏi "Còn Gia Lai thì sao?" -> nó bịa
    "Gia Lai 96.525 đ/kg". Con số đó chưa ai cung cấp; nó bắt chước định
    dạng câu trước rồi tự chế số.

    Với nông dân, một con số bịa nguy hiểm hơn hẳn câu "tôi chưa có dữ liệu".
    """
    from app.integrations.ai_grounding import SYSTEM_RULES

    rules = SYSTEM_RULES.lower()
    assert "lượt trước" in rules or "câu trả lời trước" in rules, (
        "SYSTEM_RULES chưa nói rõ: lượt trước không phải nguồn số liệu"
    )
    assert "suy" in rules or "ngoại suy" in rules or "áp dụng" in rules, (
        "Chưa cấm suy số của vùng/cây này sang vùng/cây khác"
    )
