from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.admin import require_admin
from app.api.auth import get_current_user
from app.core.database import Base, get_db
from app.main import app
from app.models.knowledge import KnowledgeSourceCandidate


def test_admin_can_review_a_pending_source_candidate():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    admin = SimpleNamespace(UserID=1, Role="admin", Region=None)
    candidate = KnowledgeSourceCandidate(
        Name="Hướng dẫn trồng nho",
        URL="https://example.gov.vn/nho",
        URLHash="review-test-url-hash",
        Domain="example.gov.vn",
        Status="pending",
    )
    db.add(candidate)
    db.commit()
    candidate_id = candidate.CandidateID
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[require_admin] = lambda: admin
    try:
        response = TestClient(app).post(f"/api/admin/knowledge/source-candidates/{candidate_id}/approve")
    finally:
        app.dependency_overrides = original
        db.close()
        engine.dispose()

    assert response.status_code == 200
    assert response.json()["candidate"]["status"] == "approved"
    assert response.json()["next_ingestion_uses_candidate"] is True
