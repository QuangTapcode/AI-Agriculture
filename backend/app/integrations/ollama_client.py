"""
Trợ lý AI chạy local qua Ollama — không cần API key trả phí.

Vì sao local: dữ liệu nông dân (vùng trồng, sản lượng, giá bán) không rời
khỏi máy chủ; chạy được cả khi mất mạng; và không tốn chi phí theo token.

Giao diện khớp ClaudeClient để tầng gọi không phải sửa gì khi đổi provider
qua settings.AI_PROVIDER.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

LOI_KHONG_KET_NOI = "Không thể kết nối trợ lý AI. Vui lòng thử lại sau."


class OllamaClient:
    """Gọi Ollama qua HTTP API cục bộ (mặc định http://localhost:11434)."""

    def __init__(self, base_url: str | None = None, model: str | None = None,
                 transport: httpx.BaseTransport | None = None):
        self.base_url = (base_url or getattr(settings, "AI_BASE_URL", "")
                         or "http://localhost:11434").rstrip("/")
        self.model = model or settings.AI_MODEL_NAME or "qwen2.5:7b-instruct-q4_K_M"
        # transport tiêm vào để test không cần Ollama chạy thật
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=settings.AI_TIMEOUT_SECONDS,
            transport=self._transport,
        )

    async def get_farming_advice(self, question: str, context_data: str = "") -> str:
        prompt = (
            f"Dữ liệu hệ thống:\n{context_data}\n\n" if context_data else ""
        ) + f"Câu hỏi của nông dân: {question}"

        try:
            async with self._client() as c:
                r = await c.post("/api/chat", json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                })
                r.raise_for_status()
                return (r.json().get("message") or {}).get("content", "")
        except Exception as exc:
            logger.error("[Ollama] loi khi hoi: %s", exc)
            raise RuntimeError(LOI_KHONG_KET_NOI) from exc

    def complete(self, messages: list[dict], system_prompt: str = "",
                 max_tokens: int = 1024) -> dict:
        """Bản đồng bộ, khớp shape ClaudeClient.complete()."""
        payload = {
            "model": self.model,
            "messages": ([{"role": "system", "content": system_prompt}] if system_prompt else [])
                        + list(messages),
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        try:
            with httpx.Client(base_url=self.base_url,
                              timeout=settings.AI_TIMEOUT_SECONDS,
                              transport=self._transport) as c:
                r = c.post("/api/chat", json=payload)
                r.raise_for_status()
                data = r.json()
            return {
                "answer": (data.get("message") or {}).get("content", ""),
                "provider": "ollama",
                "model": data.get("model") or self.model,
                "token_usage": {
                    "input_tokens": data.get("prompt_eval_count"),
                    "output_tokens": data.get("eval_count"),
                },
                "is_mock": False,
                "error": None,
            }
        except Exception as exc:
            logger.warning("[Ollama] complete that bai: %s", exc)
            return self._error_completion(LOI_KHONG_KET_NOI)

    def _error_completion(self, reason: str) -> dict:
        """Lỗi là lỗi — is_mock=False, tránh lẫn với dữ liệu giả (TOD0 §1)."""
        return {
            "answer": reason,
            "provider": "ollama",
            "model": self.model,
            "token_usage": None,
            "is_mock": False,
            "error": reason,
            "timeout": "timeout" in reason.lower(),
            "status": "failed",
        }


ollama_client = OllamaClient()
