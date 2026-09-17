import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.services.source_discovery_service import SourceDiscoveryService
from app.tasks.celery_app import celery_app


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def page(url: str, html: str) -> httpx.Response:
    return httpx.Response(
        200,
        text=html,
        headers={"content-type": "text/html; charset=utf-8"},
        request=httpx.Request("GET", url),
    )


def test_extracts_official_candidates_and_ignores_private_or_non_http_links(monkeypatch):
    service = SourceDiscoveryService()
    seed = {
        "name": "Cổng khuyến nông",
        "url": "https://seed.gov.vn/library",
        "allowed_domain": "seed.gov.vn",
    }
    html = """
      <a href="https://new-agency.gov.vn/guides">Hướng dẫn chính thức</a>
      <a href="https://example.com/ad">Quảng cáo</a>
      <a href="http://127.0.0.1/admin">Nội bộ</a>
      <a href="mailto:info@example.org">Email</a>
    """
    monkeypatch.setattr(service.ingestion, "fetch", lambda url, allowed_domain: page(url, html))

    result = service.discover([seed], max_candidates=10)

    assert [candidate["url"] for candidate in result] == ["https://new-agency.gov.vn/guides"]
    assert result[0]["is_official_domain"] is True
    assert result[0]["status"] == "pending"


def test_persists_candidates_once_and_keeps_unknown_domains_pending(db, monkeypatch):
    service = SourceDiscoveryService()
    seed = {
        "name": "Nguồn gốc",
        "url": "https://seed.gov.vn/library",
        "allowed_domain": "seed.gov.vn",
    }
    html = '<a href="https://unknown.example.org/agri">Tài liệu nông nghiệp</a>'
    monkeypatch.setattr(service.ingestion, "fetch", lambda url, allowed_domain: page(url, html))

    first = service.run(db, sources=[seed])
    second = service.run(db, sources=[seed])

    assert first["discovered"] == 1
    assert first["created"] == 1
    assert second["discovered"] == 1
    assert second["created"] == 0
    assert second["duplicates"] == 1
    row = service.list_candidates(db)[0]
    assert row["status"] == "pending"
    assert row["is_official_domain"] is False


def test_run_reports_seed_errors_without_aborting_other_sources(db, monkeypatch):
    service = SourceDiscoveryService()
    good = {"name": "Tốt", "url": "https://seed.gov.vn/a", "allowed_domain": "seed.gov.vn"}
    bad = {"name": "Lỗi", "url": "https://down.gov.vn/a", "allowed_domain": "down.gov.vn"}

    def fake_fetch(url, allowed_domain):
        if "down.gov.vn" in url:
            raise RuntimeError("timeout")
        return page(url, '<a href="https://new.gov.vn/a">Nguồn mới</a>')

    monkeypatch.setattr(service.ingestion, "fetch", fake_fetch)
    result = service.run(db, sources=[good, bad])

    assert result["created"] == 1
    assert result["errors"] == 1
    assert {item["source_name"] for item in result["source_results"]} == {"Tốt", "Lỗi"}


def test_nightly_discovery_schedule_is_registered():
    schedule = celery_app.conf.beat_schedule["discover-knowledge-sources-nightly"]
    assert schedule["task"] == "app.tasks.source_discovery_tasks.discover_knowledge_sources"
