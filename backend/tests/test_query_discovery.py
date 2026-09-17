from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.main import app
from app.models.knowledge import KnowledgeDiscoveryJob, KnowledgeSourceCandidate
from app.services.ai_intent_service import extract_crop_from_message
from app.services.knowledge_discovery_service import KnowledgeDiscoveryService, extract_query_keywords
from app.services.source_discovery_service import SourceDiscoveryService


client = TestClient(app)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _page(url: str, html: str) -> httpx.Response:
    return httpx.Response(
        200,
        text=html,
        headers={"content-type": "text/html; charset=utf-8"},
        request=httpx.Request("GET", url),
    )


def test_query_keywords_keep_crop_and_region_but_drop_fillers():
    keywords = extract_query_keywords(
        "Tôi ở Đắk Lắk, trồng mới cà phê Robusta thế nào?",
        crop="cà phê",
        region="Đắk Lắk",
    )

    assert "ca phe" in keywords
    assert "dak lak" in keywords
    assert "toi" not in keywords
    assert len(keywords) <= 12


def test_query_keywords_add_intent_terms_for_source_recall():
    keywords = extract_query_keywords(
        "Bệnh trên cà phê xử lý thế nào?",
        crop="cà phê",
        intent="quality_analysis",
    )

    assert "sau benh" in keywords
    assert "bao ve thuc vat" in keywords
    assert "xu" not in keywords


def test_grape_crop_is_detected_and_kept_as_a_discovery_keyword():
    question = "Kỹ thuật trồng cây nho tại Ninh Thuận thế nào?"
    crop = extract_crop_from_message(question)

    assert crop == "nho"
    assert "nho" in extract_query_keywords(question, crop=crop, intent="cultivation_advice")


def test_query_keywords_keep_grape_variety_phrase_for_topic_search():
    keywords = extract_query_keywords(
        "Kỹ thuật trồng nho ngón tay tại Đà Nẵng",
        crop="nho",
        region="Đà Nẵng",
        intent="cultivation_advice",
    )

    assert "nho ngón tay" in keywords
    assert keywords.index("nho ngón tay") < keywords.index("nho")


def test_livestock_age_question_keeps_the_real_topic_without_grape_keyword():
    keywords = extract_query_keywords(
        "hướng dẫn nuôi lợn từ nhỏ, cách cho ăn theo từng mức tuổi",
        intent="livestock_advice",
    )

    assert "nuôi lợn" in keywords
    assert "dinh dưỡng vật nuôi" in keywords
    assert "nho" not in keywords
    assert "hướng dẫn" not in keywords
    assert "huong" not in keywords
    assert "nuoi" not in keywords


def test_query_discovery_only_returns_matching_documents_on_configured_domain(monkeypatch):
    service = SourceDiscoveryService()
    seed = {
        "name": "Nguon chinh thuc",
        "url": "https://seed.gov.vn/library",
        "allowed_domain": "seed.gov.vn",
        "include_patterns": ["/guide-"],
    }
    html = """
      <a href="/guide-coffee">Ky thuat ca phe</a>
      <a href="/guide-rice">Ky thuat lua</a>
      <a href="https://other.gov.vn/coffee">Nguon ngoai</a>
    """
    monkeypatch.setattr(service.ingestion, "fetch", lambda url, allowed_domain: _page(url, html))

    result = service.discover_for_query(["ca phe"], sources=[seed], max_candidates=5)

    assert [item["url"] for item in result] == ["https://seed.gov.vn/guide-coffee"]
    assert result[0]["source"]["allowed_domain"] == "seed.gov.vn"


def test_query_discovery_does_not_accept_generic_document_for_missing_crop(monkeypatch):
    service = SourceDiscoveryService()
    seed = {
        "name": "Khuyến nông trồng trọt",
        "url": "https://seed.gov.vn/library",
        "allowed_domain": "seed.gov.vn",
        "include_patterns": ["/guide-"],
    }
    html = """
      <a href="/guide-general">Kỹ thuật trồng trọt</a>
      <a href="/guide-grape">Kỹ thuật trồng nho</a>
    """
    monkeypatch.setattr(service.ingestion, "fetch", lambda url, allowed_domain: _page(url, html))
    # Isolate registry matching; verified topic fallbacks are covered by the
    # dedicated browser-discovery tests.
    monkeypatch.setattr(service, "_topic_source_hints", lambda _crop: [])

    result = service.discover_for_query(
        ["nho", "ky thuat", "canh tac"], sources=[seed], crop="nho", max_candidates=5,
    )

    assert [item["url"] for item in result] == ["https://seed.gov.vn/guide-grape"]


def test_query_discovery_continues_when_one_registry_is_unavailable(monkeypatch):
    service = SourceDiscoveryService()
    sources = [
        {"name": "Nguồn lỗi", "url": "https://down.gov.vn", "allowed_domain": "down.gov.vn",
         "include_patterns": ["/guide-"]},
        {"name": "Nguồn còn lại", "url": "https://ok.gov.vn", "allowed_domain": "ok.gov.vn",
         "include_patterns": ["/guide-"]},
    ]

    def fetch(url, _allowed_domain):
        if "down.gov.vn" in url:
            raise RuntimeError("timeout")
        return _page(url, '<a href="/guide-rice">Kỹ thuật lúa</a>')

    monkeypatch.setattr(service.ingestion, "fetch", fetch)
    assert [item["url"] for item in service.discover_for_query(["lua"], sources=sources)] == [
        "https://ok.gov.vn/guide-rice"
    ]


def test_enqueue_deduplicates_an_active_question(db, monkeypatch):
    service = KnowledgeDiscoveryService()
    scheduled = []
    monkeypatch.setattr(
        "app.tasks.knowledge_discovery_tasks.discover_for_question.delay",
        lambda job_id: scheduled.append(job_id),
    )

    first = service.enqueue(db, question="Ky thuat trong ca phe", user_id=7, intent="cultivation_advice")
    second = service.enqueue(db, question="  KY THUAT TRONG CA PHE  ", user_id=7, intent="cultivation_advice")

    assert first["status"] == "queued"
    assert second["deduplicated"] is True
    assert second["job_id"] == first["job_id"]
    assert scheduled == [first["job_id"]]


def test_enqueue_reports_disabled_without_creating_a_job(db, monkeypatch):
    from app.core.config import settings

    service = KnowledgeDiscoveryService()
    monkeypatch.setattr(settings, "KNOWLEDGE_QUERY_DISCOVERY_ENABLED", False)

    result = service.enqueue(db, question="Ky thuat trong ca phe", user_id=7)

    assert result["status"] == "disabled"
    assert db.query(KnowledgeDiscoveryJob).count() == 0


def test_run_job_promotes_only_approved_ingestion(db, monkeypatch):
    service = KnowledgeDiscoveryService()
    monkeypatch.setattr(
        "app.tasks.knowledge_discovery_tasks.discover_for_question.delay",
        lambda job_id: None,
    )
    job = service.enqueue(db, question="Ky thuat trong ca phe", user_id=7, intent="cultivation_advice")
    monkeypatch.setattr(
        "app.services.knowledge_discovery_service.source_discovery_service.discover_for_query",
        lambda keywords, **kwargs: [{
            "url": "https://seed.gov.vn/guide-coffee",
            "source": {"name": "Nguá»“n chÃ­nh thá»©c", "allowed_domain": "seed.gov.vn"},
        }],
    )
    processed = []
    monkeypatch.setattr(
        "app.services.knowledge_discovery_service.knowledge_ingestion_service.process",
        lambda session, source, url: processed.append((source, url)) or "approved",
    )

    result = service.run(db, job["job_id"])

    assert result["status"] == "indexed"
    assert result["candidates_found"] == 1
    assert result["documents_processed"] == 1
    assert result["documents_indexed"] == 1
    assert processed[0][1].endswith("guide-coffee")


def test_run_reports_quality_rejection_in_job_status(db, monkeypatch):
    service = KnowledgeDiscoveryService()
    monkeypatch.setattr(
        "app.tasks.knowledge_discovery_tasks.discover_for_question.delay",
        lambda job_id: None,
    )
    job = service.enqueue(db, question="Nho", user_id=7)
    monkeypatch.setattr(
        "app.services.knowledge_discovery_service.source_discovery_service.discover_for_query",
        lambda keywords, **kwargs: [{
            "url": "https://seed.gov.vn/grape",
            "source": {"name": "Nguồn chính thức", "allowed_domain": "seed.gov.vn"},
        }],
    )
    monkeypatch.setattr(
        "app.services.knowledge_discovery_service.knowledge_ingestion_service.process",
        lambda *_args: "rejected",
    )

    result = service.run(db, job["job_id"])

    assert result["status"] == "completed"
    assert result["documents_processed"] == 1
    assert result["documents_indexed"] == 0
    assert "không đạt kiểm tra chất lượng" in result["error"]


def test_run_saves_new_official_browser_domain_as_pending_source(db, monkeypatch):
    service = KnowledgeDiscoveryService()
    monkeypatch.setattr(
        "app.tasks.knowledge_discovery_tasks.discover_for_question.delay",
        lambda job_id: None,
    )
    job = service.enqueue(db, question="Ky thuat trong nho", user_id=7, intent="cultivation_advice")
    candidate = {
        "name": "Huong dan trong nho",
        "url": "https://khuyennong.ninhthuan.gov.vn/nho",
        "domain": "khuyennong.ninhthuan.gov.vn",
        "discovered_from": "Web search",
        "discovery_reason": "Official-domain result matched crop keywords.",
        "confidence_score": 0.9,
        "is_official_domain": True,
        "source_is_new": True,
        "source": {
            "name": "Huong dan trong nho",
            "url": "https://khuyennong.ninhthuan.gov.vn/nho",
            "allowed_domain": "khuyennong.ninhthuan.gov.vn",
            "crop": "nho",
        },
    }
    monkeypatch.setattr(
        "app.services.knowledge_discovery_service.source_discovery_service.discover_for_query",
        lambda keywords, **kwargs: [candidate],
    )
    monkeypatch.setattr(
        "app.services.knowledge_discovery_service.knowledge_ingestion_service.process",
        lambda *_args: "approved",
    )

    result = service.run(db, job["job_id"])
    saved = db.query(KnowledgeSourceCandidate).filter_by(URL=candidate["url"]).one()

    assert result["status"] == "indexed"
    assert saved.Status == "pending"
    assert saved.Domain == candidate["domain"]
    assert saved.IsOfficialDomain is True


def test_query_discovery_task_is_registered():
    from app.tasks.celery_app import celery_app

    assert "app.tasks.knowledge_discovery_tasks.discover_for_question" in celery_app.tasks


def test_no_match_queues_query_discovery(monkeypatch):
    monkeypatch.setattr(
        "app.api.ai_chat.rag_service.retrieve",
        lambda *args, **kwargs: {"status": "no_match", "sources": []},
    )
    calls = []

    def enqueue(*args, **kwargs):
        calls.append((args, kwargs))
        return {
            "status": "queued",
            "job_id": "job-1",
            "message": "Đã bắt đầu tìm nguồn chính thức liên quan.",
        }

    monkeypatch.setattr("app.api.ai_chat.knowledge_discovery_service.enqueue", enqueue)

    response = client.post(
        "/api/ai-chat/message",
        json={
            "message": "Tôi ở Đắk Lắk, trồng mới cà phê Robusta. Cần chuẩn bị đất thế nào?",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["knowledge_update"]["status"] == "queued"
    assert payload["data"]["knowledge_update"]["job_id"] == "job-1"
    assert calls


def test_grape_question_sends_grape_scope_to_discovery(monkeypatch):
    monkeypatch.setattr(
        "app.api.ai_chat.rag_service.retrieve",
        lambda *args, **kwargs: {"status": "no_match", "sources": []},
    )
    captured = {}

    def enqueue(*args, **kwargs):
        captured.update(kwargs)
        return {"status": "queued", "job_id": 42}

    monkeypatch.setattr("app.api.ai_chat.knowledge_discovery_service.enqueue", enqueue)

    response = client.post("/api/ai-chat/message", json={
        "message": "Kỹ thuật trồng cây nho tại Ninh Thuận thế nào?",
    })

    assert response.status_code == 200
    assert captured["crop"] == "nho"
    assert captured["region"] == "Ninh Thuận"
    assert captured["intent"] == "cultivation_advice"


def test_short_grape_topic_sends_grape_scope_to_discovery(monkeypatch):
    monkeypatch.setattr(
        "app.api.ai_chat.rag_service.retrieve",
        lambda *args, **kwargs: {"status": "no_match", "sources": []},
    )
    captured = {}

    def enqueue(*args, **kwargs):
        captured.update(kwargs)
        return {"status": "queued", "job_id": 44}

    monkeypatch.setattr("app.api.ai_chat.knowledge_discovery_service.enqueue", enqueue)
    async def fake_ai(_request, _context):
        return "Đang tìm tài liệu về nho.", "test-model"

    monkeypatch.setattr("app.api.ai_chat._chon_provider", lambda: (fake_ai, "ollama"))
    response = client.post("/api/ai-chat/message", json={"message": "Nho"})

    assert response.status_code == 200
    assert captured["crop"] == "nho"


def test_ready_rag_does_not_start_query_discovery(monkeypatch):
    monkeypatch.setattr(
        "app.api.ai_chat.rag_service.retrieve",
        lambda *args, **kwargs: {"status": "ready", "sources": [{
            "citation": "TL1", "name": "Ky thuat ca phe", "page": 1,
            "excerpt": "Noi dung tai lieu", "source_name": "Nguon chinh thuc",
        }]},
    )
    monkeypatch.setattr(
        "app.api.ai_chat.knowledge_discovery_service.enqueue",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not enqueue")),
    )
    async def fake_ai(_request, _context):
        return "Tra loi tu tai lieu [TL1]", "test-model"

    monkeypatch.setattr("app.api.ai_chat._chon_provider", lambda: (fake_ai, "ollama"))
    response = client.post(
        "/api/ai-chat/message",
        json={"message": "Ky thuat trong ca phe o Dak Lak", "region": "Dak Lak", "crop": "ca phe"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["knowledge_update"]["status"] == "not_needed"


def test_ready_but_irrelevant_rag_starts_query_discovery_for_missing_variety(monkeypatch):
    monkeypatch.setattr(
        "app.api.ai_chat.rag_service.retrieve",
        lambda *args, **kwargs: {"status": "ready", "sources": [{
            "citation": "TL1", "name": "Kỹ thuật trồng lúa", "page": 1,
            "excerpt": "Hướng dẫn canh tác lúa", "source_name": "Nguồn khuyến nông",
        }]},
    )
    captured = {}

    def enqueue(*args, **kwargs):
        captured.update(kwargs)
        return {"status": "queued", "job_id": 43, "keywords": ["nho ngón tay"]}

    monkeypatch.setattr("app.api.ai_chat.knowledge_discovery_service.enqueue", enqueue)
    async def fake_ai(_request, _context):
        return "Chưa có tài liệu đúng giống nho; đang tìm nguồn.", "test-model"

    monkeypatch.setattr("app.api.ai_chat._chon_provider", lambda: (fake_ai, "ollama"))
    response = client.post("/api/ai-chat/message", json={
        "message": "Kỹ thuật trồng nho ngón tay tại Đà Nẵng",
    })

    assert response.status_code == 200
    assert captured["crop"] == "nho"
    assert captured["region"] == "Đà Nẵng"
    assert response.json()["data"]["knowledge_update"]["job_id"] == 43


def test_matching_crop_evidence_is_kept_when_variety_is_missing(monkeypatch):
    monkeypatch.setattr(
        "app.api.ai_chat.rag_service.retrieve",
        lambda *args, **kwargs: {"status": "ready", "sources": [{
            "citation": "TL1", "name": "Hướng dẫn kỹ thuật trồng nho Hạ Đen", "page": 1,
            "excerpt": "Quy trình canh tác nho và chăm sóc giàn.",
            "source_name": "Nguồn khuyến nông", "crop": "Nho",
        }]},
    )
    monkeypatch.setattr(
        "app.api.ai_chat.knowledge_discovery_service.enqueue",
        lambda *args, **kwargs: {"status": "queued", "job_id": 45},
    )
    async def fake_ai(_request, _context):
        return "Có tài liệu về nho; chưa có tài liệu riêng cho nho ngón tay.", "test-model"

    monkeypatch.setattr("app.api.ai_chat._chon_provider", lambda: (fake_ai, "ollama"))
    response = client.post("/api/ai-chat/message", json={
        "message": "Kỹ thuật trồng nho ngón tay tại Đà Nẵng",
    })

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["knowledge_update"]["job_id"] == 45
    assert data["rag"]["sources"][0]["name"] == "Hướng dẫn kỹ thuật trồng nho Hạ Đen"


def test_livestock_question_rejects_grape_evidence_and_queues_its_own_topic(monkeypatch):
    monkeypatch.setattr(
        "app.api.ai_chat.rag_service.retrieve",
        lambda *args, **kwargs: {"status": "ready", "sources": [{
            "citation": "TL1",
            "name": "Hướng dẫn kỹ thuật trồng nho Hạ Đen",
            "page": 1,
            "excerpt": "Tỉa cành, tỉa quả và chăm sóc giàn nho.",
            "source_name": "Nguồn khuyến nông",
            "crop": "Nho",
        }]},
    )
    captured = {}

    def enqueue(*args, **kwargs):
        captured.update(kwargs)
        return {
            "status": "queued",
            "job_id": 51,
            "keywords": extract_query_keywords(
                kwargs["question"], crop=kwargs["crop"], region=kwargs["region"], intent=kwargs["intent"],
            ),
        }

    async def fake_ai(_request, context):
        assert context["rag"]["sources"] == []
        return "Chưa có tài liệu phù hợp; đang tìm nguồn chăn nuôi.", "test-model"

    monkeypatch.setattr("app.api.ai_chat.knowledge_discovery_service.enqueue", enqueue)
    monkeypatch.setattr("app.api.ai_chat._chon_provider", lambda: (fake_ai, "ollama"))

    response = client.post("/api/ai-chat/message", json={
        "message": "hướng dẫn nuôi lợn từ nhỏ, cách cho ăn theo từng mức tuổi",
        "session_id": "fresh-livestock-session",
    })

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "livestock_advice"
    assert data["crop"] is None
    assert data["rag"]["sources"] == []
    assert "nuôi lợn" in data["knowledge_update"]["keywords"]
    assert captured["crop"] is None


def test_livestock_feeding_question_does_not_treat_a_generic_pig_title_as_answer(monkeypatch):
    monkeypatch.setattr(
        "app.api.ai_chat.rag_service.retrieve",
        lambda *args, **kwargs: {"status": "ready", "sources": [{
            "citation": "TL1",
            "name": "Sổ tay chăn nuôi lợn quy mô nhỏ",
            "page": 1,
            "excerpt": "Những vấn đề thường gặp trong chăn nuôi lợn.",
            "source_name": "Khuyến nông Quốc gia",
        }]},
    )
    monkeypatch.setattr(
        "app.api.ai_chat.knowledge_discovery_service.enqueue",
        lambda *args, **kwargs: {
            "status": "queued",
            "job_id": 52,
            "keywords": extract_query_keywords(
                kwargs["question"], crop=kwargs["crop"], region=kwargs["region"], intent=kwargs["intent"],
            ),
        },
    )

    response = client.post("/api/ai-chat/message", json={
        "message": "hướng dẫn nuôi lợn từ nhỏ, cách cho ăn theo từng mức tuổi",
        "session_id": "fresh-livestock-feeding-session",
    })

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model"] == "rag-safety-livestock-v1"
    assert data["rag"]["sources"] == []
    assert data["knowledge_update"]["job_id"] == 52
    assert "nuôi lợn" in data["knowledge_update"]["keywords"]
    assert "chưa có đoạn tài liệu đủ" in data["reply"].lower()
