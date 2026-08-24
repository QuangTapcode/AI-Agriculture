"""
Chọn nhà cung cấp AI theo cấu hình, để tầng gọi không phụ thuộc hãng nào.

Trước đây ai_chat.py gọi thẳng ai_client.client.messages.create(...) — API
riêng của Anthropic — nên muốn đổi sang model chạy local phải sửa cả tầng
gọi. Ở đây mọi client đều phơi ra `complete()` với cùng shape kết quả.
"""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_ai_client():
    """Client theo settings.AI_PROVIDER.

    Mặc định là Ollama (chạy local): provider lạ không nên lặng lẽ rơi về
    một dịch vụ tính phí theo token.
    """
    provider = (settings.AI_PROVIDER or "").strip().lower()

    if provider == "claude":
        from app.integrations.claude_client import ClaudeClient
        return ClaudeClient()

    if provider not in ("ollama", ""):
        logger.warning("[AI] provider %r khong nhan ra — dung Ollama (local)", provider)

    from app.integrations.ollama_client import OllamaClient
    return OllamaClient()
