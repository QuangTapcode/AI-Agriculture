import json
from datetime import datetime, timezone

import pytest

from app.api import ai_chat


@pytest.mark.asyncio
async def test_stream_completes_with_datetime_metadata(monkeypatch):
    created_at = datetime(2026, 9, 16, 2, 30, tzinfo=timezone.utc)

    async def answer(*args):
        return {"success": True, "data": {
            "reply": "Thông tin có nguồn", "created_at": created_at,
            "rag": {"sources": [{"updated_at": created_at}]},
        }}

    monkeypatch.setattr(ai_chat, "ai_chat_message", answer)
    response = await ai_chat.ai_chat_message_stream(
        ai_chat.AIChatMessageRequest(message="Kỹ thuật trồng nho"),
        db=None, current_user=None,
    )
    events = [json.loads(chunk) async for chunk in response.body_iterator]
    assert [event["type"] for event in events] == ["status", "complete"]
    data = events[-1]["payload"]["data"]
    assert data["reply"] == "Thông tin có nguồn"
    assert data["created_at"] == created_at.isoformat()
    assert data["rag"]["sources"][0]["updated_at"] == created_at.isoformat()
