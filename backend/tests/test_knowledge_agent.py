import json

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base
from app.models.knowledge import KnowledgeDocument
from app.services.knowledge_ingestion_service import KnowledgeIngestionService, configured_sources
from app.services.rag_service import RagService, extract_pages, rag_service
from app.tasks.celery_app import celery_app


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def agent(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "RAG_STORAGE_PATH", str(tmp_path / "rag"))
    monkeypatch.setattr(settings, "RAG_ENABLED", True)
    monkeypatch.setattr(settings, "KNOWLEDGE_AGENT_MIN_TEXT_CHARS", 80)
    monkeypatch.setattr(settings, "KNOWLEDGE_AGENT_QA_SIMILARITY", 0.2)
    monkeypatch.setattr(RagService, "embed", lambda self, texts: [[1.0, 0.0] for _ in texts])
    return KnowledgeIngestionService()


def response(url: str, text: str) -> httpx.Response:
    return httpx.Response(200, text=text, headers={"content-type": "text/html; charset=utf-8"},
                          request=httpx.Request("GET", url))


def agricultural_page(version: str) -> str:
    body = ("Hướng dẫn kỹ thuật canh tác lúa, quản lý đất, tưới nước và phòng sâu bệnh. " * 10) + version
    return f"<html><head><title>Quy trình lúa {version}</title></head><body><article>{body}</article></body></html>"


def test_source_configuration_filters_invalid_entries(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_AGENT_SOURCES_FILE", "")
    monkeypatch.setattr(settings, "KNOWLEDGE_AGENT_SOURCES_JSON", json.dumps([
        {"name": "Official", "url": "https://example.org/library"},
        {"name": "Missing URL"},
        {"name": "File", "url": "file:///tmp/a"},
    ]))
    assert configured_sources() == [{"name": "Official", "url": "https://example.org/library",
                                     "allowed_domain": "example.org"}]


def test_source_configuration_reads_json_file(monkeypatch, tmp_path):
    source_file = tmp_path / "sources.json"
    source_file.write_text(json.dumps([
        {"name": "Official file", "url": "https://example.org/guides"},
    ]), encoding="utf-8")
    monkeypatch.setattr(settings, "KNOWLEDGE_AGENT_SOURCES_FILE", str(source_file))
    monkeypatch.setattr(settings, "KNOWLEDGE_AGENT_SOURCES_JSON", "not-used")
    assert configured_sources()[0]["name"] == "Official file"


def test_discovery_filters_navigation_and_duplicate_article_links(agent, monkeypatch):
    listing = response("https://example.org/library", """
        <a href="/library">Trang hiện tại</a>
        <a href="/about">Giới thiệu</a>
        <a href="/article/view/42">Bài kỹ thuật</a>
        <a href="/article/view/42/pdf">Bản PDF trùng bài</a>
        <a href="/article/view/43">Bài kỹ thuật mới</a>
    """)
    monkeypatch.setattr(agent, "fetch", lambda candidate, domain: listing)
    source = {
        "name": "Official",
        "url": "https://example.org/library",
        "allowed_domain": "example.org",
        "include_regexes": [r"/article/view/\d+$"],
        "link_text_patterns": ["kỹ thuật"],
        "exclude_patterns": ["/about"],
        "max_documents": 5,
    }
    assert agent.discover(source) == [
        "https://example.org/article/view/42",
        "https://example.org/article/view/43",
    ]


def test_discovery_can_ingest_a_static_source_page(agent, monkeypatch):
    listing = response("https://example.org/technical-guide", "<main>Hướng dẫn kỹ thuật.</main>")
    monkeypatch.setattr(agent, "fetch", lambda candidate, domain: listing)
    source = {"name": "Official", "url": str(listing.url), "allowed_domain": "example.org",
              "include_start_page": True, "max_documents": 1}
    assert agent.discover(source) == ["https://example.org/technical-guide"]


def test_fetch_retries_temporary_server_error(agent, monkeypatch):
    calls = []

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url):
            calls.append(url)
            status = 500 if len(calls) == 1 else 200
            return httpx.Response(status, text="ok", request=httpx.Request("GET", url))

    monkeypatch.setattr("app.services.knowledge_ingestion_service.httpx.Client", Client)
    monkeypatch.setattr("app.services.knowledge_ingestion_service._validate_remote_url",
                        lambda *args: None)
    monkeypatch.setattr("app.services.knowledge_ingestion_service.time.sleep", lambda *args: None)
    monkeypatch.setattr(settings, "EXTERNAL_RETRY_COUNT", 1)

    assert agent.fetch("https://example.org/guide", "example.org").status_code == 200
    assert len(calls) == 2


def test_run_reports_partial_success_when_duplicates_exist(agent, db, monkeypatch):
    source = {"name": "Official", "url": "https://example.org/library",
              "allowed_domain": "example.org"}
    monkeypatch.setattr("app.services.knowledge_ingestion_service.configured_sources",
                        lambda: [source])
    monkeypatch.setattr(agent, "discover", lambda item: ["https://example.org/one", "https://example.org/two"])
    monkeypatch.setattr(agent, "process",
                        lambda session, item, url: "duplicate" if url.endswith("one") else (_ for _ in ()).throw(httpx.ReadError("temporary")))

    result = agent.run(db, force=True)

    assert result["status"] == "partial_success"
    assert result["duplicate"] == 1
    assert result["failed"] == 1


def test_approved_duplicate_and_updated_document_lifecycle(agent, db, monkeypatch):
    url = "https://example.org/guides/rice.html"
    source = {"name": "Official", "url": "https://example.org/library",
              "allowed_domain": "example.org", "region": "ĐBSCL", "crop": "Lúa"}
    current = {"html": agricultural_page("v1")}
    monkeypatch.setattr(agent, "fetch", lambda candidate, domain: response(candidate, current["html"]))

    assert agent.process(db, source, url) == "approved"
    first = db.query(KnowledgeDocument).one()
    assert first.Status == "approved" and first.Version == 1 and first.QualityScore >= 0.6
    assert rag_service.documents(0)[0]["id"] == first.RagDocumentID
    assert agent.process(db, source, url) == "duplicate"
    assert db.query(KnowledgeDocument).count() == 1

    current["html"] = agricultural_page("v2 updated")
    assert agent.process(db, source, url) == "approved"
    rows = db.query(KnowledgeDocument).order_by(KnowledgeDocument.Version).all()
    assert [row.Version for row in rows] == [1, 2]
    assert [row.Status for row in rows] == ["superseded", "approved"]
    assert {doc["id"] for doc in rag_service.documents(0)} == {rows[1].RagDocumentID}


def test_rejected_document_stays_out_of_shared_rag(agent, db, monkeypatch):
    url = "https://example.org/guides/empty.html"
    source = {"name": "Official", "url": url, "allowed_domain": "example.org"}
    monkeypatch.setattr(agent, "fetch", lambda candidate, domain: response(candidate, "<p>Thông báo ngắn.</p>"))
    assert agent.process(db, source, url) == "rejected"
    row = db.query(KnowledgeDocument).one()
    assert row.Status == "rejected"
    assert rag_service.documents(0) == []


def test_pdf_is_converted_to_text_before_embedding(agent, monkeypatch):
    pdf = httpx.Response(200, content=b"%PDF-fake", headers={"content-type": "application/pdf"},
                         request=httpx.Request("GET", "https://example.org/rice.pdf"))
    monkeypatch.setattr("app.services.knowledge_ingestion_service.extract_pages",
                        lambda *args: [(1, "Kỹ thuật canh tác lúa."), (2, "Quản lý sâu bệnh.")])
    extracted = agent.extract(str(pdf.url), pdf)
    assert extracted["filename"] == "rice.txt"
    assert extracted["content"].startswith("Kỹ thuật".encode())
    assert extract_pages(extracted["filename"], extracted["content"]) == [
        (1, "Kỹ thuật canh tác lúa."),
        (2, "Quản lý sâu bệnh."),
    ]


def test_pdf_filename_is_url_decoded_before_becoming_a_source_label(agent, monkeypatch):
    pdf = httpx.Response(
        200,
        content=b"%PDF-fake",
        headers={"content-type": "application/pdf"},
        request=httpx.Request("GET", "https://example.org/H%C6%B0%E1%BB%9Bng-d%E1%BA%ABn-c%C3%A0-ph%C3%AA.pdf"),
    )
    monkeypatch.setattr(
        "app.services.knowledge_ingestion_service.extract_pages",
        lambda *args: [(1, "Kỹ thuật canh tác cà phê và quản lý sâu bệnh.")],
    )

    extracted = agent.extract(str(pdf.url), pdf)

    assert extracted["title"] == "Hướng dẫn cà phê"
    assert extracted["filename"] == "Hướng-dẫn-cà-phê.txt"


def test_html_extraction_keeps_article_inside_aspnet_form(agent):
    page = response("https://example.org/rice", """
        <html><head><title>Kỹ thuật lúa</title></head><body>
        <form id="Form"><input name="__VIEWSTATE" value="noise">
        <article>Hướng dẫn kỹ thuật canh tác lúa và phòng sâu bệnh.</article>
        <button>Gửi</button></form></body></html>
    """)
    extracted = agent.extract(str(page.url), page)
    assert "Hướng dẫn kỹ thuật canh tác lúa" in extracted["text"]
    assert "__VIEWSTATE" not in extracted["text"]


def test_html_extraction_hash_is_not_changed_by_dynamic_page_chrome(agent):
    def extract(counter: int):
        page = response("https://example.org/rice", f"""
            <html><head><title>Kỹ thuật lúa</title></head><body>
            <div class="online-count">Đang xem: {counter}</div>
            <div itemprop="articleBody">Quy trình canh tác lúa ổn định. Số lần xem: {counter}</div>
            </body></html>
        """)
        return agent.extract(str(page.url), page)["content"]

    assert extract(10) == extract(999)


def test_nightly_task_is_registered():
    schedule = celery_app.conf.beat_schedule["ingest-knowledge-nightly"]
    assert schedule["task"] == "app.tasks.knowledge_tasks.ingest_knowledge_sources"
