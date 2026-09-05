"""
TDD: thiếu API key thì nói thẳng, không bịa câu trả lời AI.

gemini_client trả chuỗi giả khi chưa cấu hình key:
    "[Chế độ Test] Đây là câu trả lời giả lập từ AI cho câu hỏi: '...'"

Nó đi thẳng vào trường `answer` như một câu trả lời bình thường — không cờ
is_mock, không error code. Frontend render y hệt câu thật. Đây đúng là thứ
TOD0 §1 cấm: dữ liệu bịa lọt ra API công khai.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

DAU_HIEU_BIA = ("giả lập", "chế độ test", "[test]")


def _khong_bia(text: str) -> bool:
    low = (text or "").lower()
    return not any(m in low for m in DAU_HIEU_BIA)


def test_chat_khong_tra_cau_bia_khi_thieu_key():
    """Không có key => phải báo lỗi rõ, không đưa câu giả cho nông dân."""
    r = client.post("/api/chat", json={"question": "Cách trồng cà chua?"})
    assert r.status_code == 200
    body = r.json()

    answer = body.get("answer") or ""
    assert _khong_bia(answer), f"Vẫn trả câu bịa: {answer[:120]!r}"


def test_chat_bao_ro_ly_do_khi_ai_khong_kha_dung():
    """Người dùng phải biết vì sao không có câu trả lời."""
    r = client.post("/api/chat", json={"question": "Cách trồng cà chua?"})
    body = r.json()

    if body.get("answer"):
        return  # AI that dang chay, khong ap dung

    err = body.get("error") or {}
    assert err.get("code"), f"Không có mã lỗi để frontend xử lý: {body}"
    assert body.get("is_mock") is False
