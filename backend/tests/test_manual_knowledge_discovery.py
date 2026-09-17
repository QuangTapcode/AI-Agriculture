from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import get_current_user
from app.core.database import Base, get_db
from app.main import app
from app.services.knowledge_discovery_service import knowledge_discovery_service


def test_manual_knowledge_discovery_endpoint_extracts_topic_and_starts_now(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    user = SimpleNamespace(UserID=1001, Region=None)
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    captured = {}

    def enqueue(*args, **kwargs):
        captured.update(kwargs)
        return {"job_id": 12, "status": "queued", "keywords": ["nho ngón tay", "Đà Nẵng"]}

    monkeypatch.setattr(knowledge_discovery_service, "enqueue", enqueue)
    try:
        response = TestClient(app).post("/api/ai-chat/knowledge-discovery", json={
            "question": "Kỹ thuật trồng nho ngón tay tại Đà Nẵng",
        })
    finally:
        app.dependency_overrides = original
        db.close()
        engine.dispose()

    assert response.status_code == 200
    assert captured == {
        "question": "Kỹ thuật trồng nho ngón tay tại Đà Nẵng",
        "user_id": 1001,
        "intent": "cultivation_advice",
        "crop": "nho",
        "region": "Đà Nẵng",
        "force": True,
    }
