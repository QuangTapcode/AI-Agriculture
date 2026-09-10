"""Opt-in smoke test with real local Ollama; no user data is read or changed."""
import os
import time

import pytest

from app.api.ai_chat import AIChatMessageRequest, _call_local_ai
from app.core.config import settings
from app.services.rag_service import RagService


@pytest.mark.skipif(os.getenv("RUN_OLLAMA_RAG_TEST") != "1", reason="Requires local Ollama models")
@pytest.mark.asyncio
async def test_real_embedding_retrieval_and_generation(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "RAG_STORAGE_PATH", str(tmp_path / "live-rag"))
    monkeypatch.setattr(settings, "RAG_ENABLED", True)
    service = RagService()
    started = time.monotonic()
    service.ingest(999999, "kiem-thu-rag.txt", (
        "Tài liệu kiểm thử hệ thống, không phải hướng dẫn canh tác. "
        "Ruộng lúa thử nghiệm có mã LO-LUA-7429. Người phụ trách kiểm tra thoát nước là anh Minh."
    ).encode())
    rag = service.retrieve("Ruộng lúa thử nghiệm có mã gì và ai phụ trách kiểm tra thoát nước?", 999999)
    assert rag["status"] == "ready", rag
    assert "LO-LUA-7429" in rag["sources"][0]["excerpt"]
    reply, model = await _call_local_ai(AIChatMessageRequest(
        message="Theo tài liệu, ruộng lúa thử nghiệm có mã gì và ai phụ trách kiểm tra thoát nước? Trả lời trong một câu và dẫn nguồn."
    ), {"rag": rag, "intent": "general_question", "crop_name": "lúa"})
    assert "LO-LUA-7429" in reply and "Minh" in reply, reply
    assert "TL1" in reply, reply
    assert "</think>" not in reply and len(reply) < 700, reply
    print(f"\nModel: {model}; elapsed: {time.monotonic() - started:.1f}s; reply: {reply}")
