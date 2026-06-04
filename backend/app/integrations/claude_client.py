import asyncio
import logging
import os

from anthropic import Anthropic, AsyncAnthropic
from dotenv import load_dotenv

from app.core.config import settings

logger = logging.getLogger(__name__)

load_dotenv()


class ClaudeClient:
    def __init__(self):
        api_key = settings.CLAUDE_API_KEY or os.getenv("ANTHROPIC_API_KEY") or (
            settings.AI_API_KEY if settings.AI_PROVIDER.lower() == "claude" else ""
        )
        self.model = settings.AI_MODEL_NAME or "claude-3-haiku-20240307"
        if not api_key:
            logger.warning("Claude API key is not set. Claude AI is disabled.")
            self.client = None
            self.sync_client = None
            return

        self.client = AsyncAnthropic(api_key=api_key, timeout=settings.AI_TIMEOUT_SECONDS)
        self.sync_client = Anthropic(api_key=api_key, timeout=settings.AI_TIMEOUT_SECONDS)

    async def get_farming_advice(self, question: str, context_data: str = "") -> str:
        if not self.client:
            raise RuntimeError("Không thể kết nối trợ lý AI. Vui lòng thử lại sau.")

        prompt = (
            "Ban la mot chuyen gia nong nghiep AI.\n\n"
            f"Du lieu boi canh: {context_data}\n\n"
            f"Cau hoi cua nong dan: {question}\n\n"
            "Hay dua ra loi khuyen ngan gon, de hieu va thuc te."
        )

        try:
            response = await asyncio.wait_for(
                self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=settings.AI_TIMEOUT_SECONDS,
            )
            return response.content[0].text
        except asyncio.TimeoutError:
            logger.warning("[Claude] farming advice timed out after %.1fs", settings.AI_TIMEOUT_SECONDS)
            raise RuntimeError("Không thể kết nối trợ lý AI. Vui lòng thử lại sau.")
        except Exception as exc:
            logger.error("Claude API error: %s", exc)
            raise RuntimeError("Không thể kết nối trợ lý AI. Vui lòng thử lại sau.") from exc

    def complete(self, messages: list[dict], system_prompt: str = "", max_tokens: int = 1024) -> dict:
        if not self.sync_client:
            return {
                "answer": "[Test] Câu trả lời giả lập từ Claude.",
                "provider": "claude",
                "model": self.model,
                "token_usage": None,
                "is_mock": True,
                "error": None,
            }

        try:
            response = self.sync_client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt or "",
                messages=messages,
            )
            return {
                "answer": response.content[0].text if response.content else "",
                "provider": "claude",
                "model": self.model,
                "token_usage": {
                    "input_tokens": getattr(response.usage, "input_tokens", None),
                    "output_tokens": getattr(response.usage, "output_tokens", None),
                },
                "is_mock": False,
                "error": None,
            }
        except Exception as exc:
            message = str(exc)
            logger.warning("[Claude] complete failed: %s", message)
            return self._error_completion("Không thể kết nối trợ lý AI. Vui lòng thử lại sau.")

    def _error_completion(self, reason: str) -> dict:
        timeout = "timeout" in reason.lower() or "timed out" in reason.lower()
        return {
            "answer": reason,
            "provider": "claude",
            "model": self.model if hasattr(self, "model") else "claude",
            "token_usage": None,
            "is_mock": False,
            "error": reason,
            "timeout": timeout,
            "status": "failed",
        }


ai_client = ClaudeClient()
