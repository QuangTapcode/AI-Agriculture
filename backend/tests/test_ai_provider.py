"""
TDD: chọn nhà cung cấp AI qua cấu hình, không hardcode.

ai_chat.py gọi thẳng ai_client.client.messages.create(...) — API riêng của
Anthropic — nên không thể đổi sang Ollama mà không sửa tầng gọi. Cần một
seam chung: get_ai_client() trả về client theo settings.AI_PROVIDER, mọi
client đều có complete().
"""
import pytest

from app.integrations.ai_provider import get_ai_client


def test_chon_ollama_khi_cau_hinh_local(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.AI_PROVIDER", "ollama")
    client = get_ai_client()
    assert client.__class__.__name__ == "OllamaClient"


def test_chon_claude_khi_cau_hinh_claude(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.AI_PROVIDER", "claude")
    client = get_ai_client()
    assert client.__class__.__name__ == "ClaudeClient"


def test_provider_la_nao_cung_co_complete(monkeypatch):
    """Tầng gọi chỉ dùng complete() — mọi provider phải có."""
    for provider in ("ollama", "claude"):
        monkeypatch.setattr("app.core.config.settings.AI_PROVIDER", provider)
        client = get_ai_client()
        assert callable(getattr(client, "complete", None)), f"{provider} thiếu complete()"


def test_provider_la_khong_biet_thi_dung_local(monkeypatch):
    """Mặc định an toàn: chạy local, không lặng lẽ gọi dịch vụ tính phí."""
    monkeypatch.setattr("app.core.config.settings.AI_PROVIDER", "khong-ton-tai")
    assert get_ai_client().__class__.__name__ == "OllamaClient"
