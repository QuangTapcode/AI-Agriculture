import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import get_current_user, get_optional_current_user
from app.api.assistant_library import load_memory
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models.conversation import AIConversation
from app.models.ingestion import DataIngestionLog
from app.models.knowledge import KnowledgeDocument
from app.services.rag_service import RagService, chunk_pages, extract_pages, rag_service


@pytest.fixture
def rag(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "RAG_STORAGE_PATH", str(tmp_path / "chroma"))
    monkeypatch.setattr(settings, "RAG_ENABLED", True)
    monkeypatch.setattr(settings, "RAG_MIN_SIMILARITY", 0.5)
    monkeypatch.setattr(RagService, "embed", lambda self, texts: [
        [1.0, 0.0, 0.0] if "lúa" in text.lower() else [0.0, 1.0, 0.0] for text in texts
    ])
    return rag_service


@pytest.fixture
def api(monkeypatch, rag):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    user = SimpleNamespace(UserID=1001, Region=None)
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_optional_current_user] = lambda: user
    monkeypatch.setattr(settings, "AI_PROVIDER", "ollama")
    yield TestClient(app), db, user
    app.dependency_overrides = original
    db.close()
    engine.dispose()


def add_turn(db, owner, session, question="Chăm sóc lúa?", answer="Theo dõi ruộng.", context=None):
    row = AIConversation(UserID=owner, SessionID=session, UserMessage=question, AIResponse=answer,
                         ContextSnapshot=json.dumps(context or {}, ensure_ascii=False))
    db.add(row)
    db.commit()
    return row


def test_index_retrieve_persist_and_delete_are_owner_scoped(rag):
    doc = rag.ingest(1, "huong-dan.md", "Chăm sóc lúa: kiểm tra khả năng thoát nước.".encode())
    assert doc["chunks"] == 1
    assert RagService().documents(1)[0]["id"] == doc["id"]
    assert rag.ingest(1, "copy.md", "Chăm sóc lúa: kiểm tra khả năng thoát nước.".encode())["duplicate"]
    result = rag.retrieve("lúa", 1)
    assert result["sources"][0]["citation"] == "TL1"
    assert result["sources"][0]["page"] == 1
    assert "thoát nước" in result["sources"][0]["excerpt"]
    assert rag.retrieve("cà phê", 1)["status"] == "no_match"
    assert rag.retrieve("lúa", 2)["sources"] == []
    rag.delete(2, doc["id"])
    assert rag.documents(1)
    rag.delete(1, doc["id"])
    assert rag.retrieve("lúa", 1)["status"] == "empty"


def test_chunking_and_invalid_documents():
    chunks = chunk_pages([(2, "lúa " * 800), (3, "Trang tiếp theo")])
    assert all(len(c["text"]) <= 1000 for c in chunks)
    assert chunks[-1]["page"] == 3
    assert len(chunks) > 3
    for filename, content in [("bad.exe", b"test"), ("empty.txt", b" "), ("bad.txt", b"\xff"), ("bad.pdf", b"broken")]:
        with pytest.raises(ValueError):
            extract_pages(filename, content)


def test_text_exported_from_pdf_keeps_page_boundaries():
    pages = extract_pages("guide.txt", "Trang một\fTrang hai".encode("utf-8"))

    assert pages == [(1, "Trang một"), (2, "Trang hai")]


def test_embedding_failure_does_not_publish_partial_document(rag, monkeypatch):
    def fail(*args):
        raise RuntimeError("embedding offline")
    monkeypatch.setattr(RagService, "embed", fail)
    with pytest.raises(RuntimeError):
        rag.ingest(1, "guide.txt", b"content")
    assert rag.documents(1) == []


def test_unavailable_retrieval_is_explicit(rag, monkeypatch):
    rag.ingest(1, "guide.txt", "lúa".encode())
    monkeypatch.setattr(RagService, "embed", lambda *args: (_ for _ in ()).throw(RuntimeError("offline")))
    assert rag.retrieve("lúa", 1) == {"status": "unavailable", "sources": []}


def test_retrieval_excludes_arabica_document_for_robusta_question(rag):
    rag.ingest(
        0,
        "Hướng dẫn cà phê chè Arabica Tây Bắc.md",
        "Kỹ thuật trồng cà phê chè và chuẩn bị đất vườn ươm.".encode("utf-8"),
    )

    result = rag.retrieve("Trồng cà phê vối Robusta tại Đắk Lắk", None)

    assert result["status"] == "no_match"
    assert result["sources"] == []


def test_shared_knowledge_is_visible_without_leaking_another_users_documents(rag):
    rag.ingest(0, "official.txt", "lúa canh tác từ nguồn chính thức".encode())
    rag.ingest(1, "private.txt", "lúa ghi chú riêng của nông hộ".encode())
    assert {item["name"] for item in rag.retrieve("lúa", 1)["sources"]} == {
        "official.txt", "private.txt"
    }
    assert {item["name"] for item in rag.retrieve("lúa", 2)["sources"]} == {"official.txt"}
    assert {item["name"] for item in rag.retrieve("lúa", None)["sources"]} == {"official.txt"}


def test_search_pagination_legacy_and_owner_isolation(api):
    client, db, user = api
    add_turn(db, user.UserID, "session-a", "Lượt đầu")
    add_turn(db, user.UserID, "session-a", "Hỏi tiếp", "Nội dung tìm kiếm độc nhất")
    add_turn(db, user.UserID, "session-b")
    add_turn(db, 2002, "private-session", "Bí mật")
    old = add_turn(db, user.UserID, "frontend-session", "Câu hỏi cũ")
    legacy_id = f"legacy-{old.ConvID}"
    result = client.get('/api/ai-chat/conversations?q=độc nhất').json()
    assert result['total'] == 1
    assert result['history'][0]['turn_count'] == 2
    assert result['history'][0]['user_message'] == 'Lượt đầu'
    page = client.get('/api/ai-chat/conversations?limit=1&offset=1').json()
    assert len(page['history']) == 1 and page['has_more']
    assert client.get('/api/ai-chat/conversations/private-session').status_code == 404
    assert client.delete('/api/ai-chat/conversations/private-session').status_code == 404
    opened = client.get(f'/api/ai-chat/conversations/{legacy_id}').json()
    assert opened['session_id'] != 'frontend-session'
    assert len(opened['turns']) == 1
    add_turn(db, user.UserID, opened['session_id'], 'Tiếp tục')
    assert client.get(f"/api/ai-chat/conversations/{opened['session_id']}").json()['total'] == 2


def test_delete_removes_whole_session_from_history_and_memory(api):
    client, db, user = api
    for _ in range(2):
        add_turn(db, user.UserID, 'session-a')
    add_turn(db, user.UserID, 'session-b')
    assert client.delete('/api/ai-chat/conversations/session-a').json()['deleted_count'] == 2
    assert load_memory(db, user.UserID, 'session-a')[0] == []
    assert client.get('/api/ai-chat/conversations').json()['total'] == 1
    assert client.get('/api/ai-chat/history').json()['total'] == 1
    assert client.get('/api/chat/history').json()['total'] == 1
    client.delete('/api/ai-chat/history')
    assert client.get('/api/ai-chat/conversations').json()['total'] == 0


def test_chat_retrieves_before_generation_and_resumes_memory(api, rag, monkeypatch):
    client, db, user = api
    rag.ingest(user.UserID, 'lua.md', 'Chăm sóc lúa: kiểm tra thoát nước.'.encode())
    add_turn(db, user.UserID, 'session-a', 'Tôi đang trồng lúa.', context={'crop_name': 'lúa'})
    add_turn(db, user.UserID, 'session-b', 'KHONG_GUI_SESSION_KHAC')
    add_turn(db, 2002, 'session-a', 'KHONG_GUI_USER_KHAC')
    captured = {}
    class FakeClient:
        def complete(self, messages, system_prompt, max_tokens):
            captured.update(messages=messages, system=system_prompt)
            return {'answer': 'Kiểm tra thoát nước [TL1].', 'model': 'qwen3:4b'}
    monkeypatch.setattr('app.api.ai_chat.get_ai_client', lambda: FakeClient())
    response = client.post('/api/ai-chat/message', json={'message': 'Tôi cần làm gì tiếp?', 'session_id': 'session-a'})
    assert response.status_code == 200, response.text
    data = response.json()['data']
    assert data['rag']['sources'][0]['name'] == 'lua.md'
    assert data['history_saved'] is True
    prompt = json.dumps(captured, ensure_ascii=False)
    assert 'Tôi đang trồng lúa' in prompt and 'kiểm tra thoát nước' in prompt
    assert 'KHONG_GUI' not in prompt
    assert [m['role'] for m in captured['messages']] == ['user', 'assistant', 'user']
    opened = client.get('/api/ai-chat/conversations/session-a').json()
    assert opened['turns'][-1]['rag']['sources'][0]['name'] == 'lua.md'
    assert opened['total'] == 2


def test_document_upload_and_validation(api):
    client, _, user = api
    response = client.post('/api/ai-chat/documents', files={'file': ('guide.txt', 'lúa'.encode(), 'text/plain')})
    assert response.status_code == 200, response.text
    assert client.get('/api/ai-chat/documents').json()['documents'][0]['name'] == 'guide.txt'
    assert client.post('/api/ai-chat/documents', files={'file': ('file.exe', b'wrong')}).status_code == 422
    client.delete('/api/ai-chat/documents/' + response.json()['id'])
    assert client.get('/api/ai-chat/documents').json()['documents'] == []


def test_fresh_document_library_handles_concurrent_api_requests(api):
    """Opening an empty library must stay available when the UI loads its panels together."""
    client, _, _ = api
    workers = 8
    barrier = Barrier(workers)

    def open_library(_):
        barrier.wait()
        return client.get('/api/ai-chat/documents')

    with ThreadPoolExecutor(max_workers=workers) as pool:
        responses = list(pool.map(open_library, range(workers)))

    assert [response.status_code for response in responses] == [200] * workers
    assert all(response.json() == {'documents': []} for response in responses)


def test_knowledge_status_reports_latest_nightly_run(api, rag):
    client, db, _ = api
    rag.ingest(0, 'official.txt', 'Hướng dẫn kỹ thuật canh tác lúa.'.encode())
    db.add(KnowledgeDocument(
        SourceName='Official', CanonicalURL='https://example.org/rice', URLHash='url-hash',
        ContentHash='content-hash', Title='Rice', Version=1, Status='approved',
    ))
    db.add(DataIngestionLog(
        SourceName='configured_sources', JobName='knowledge_agent', Status='success',
        RecordsFetched=21, RecordsSaved=2,
    ))
    db.commit()

    result = client.get('/api/ai-chat/knowledge-status')

    assert result.status_code == 200
    data = result.json()
    assert data['last_run']['status'] == 'success'
    assert data['last_run']['records_fetched'] == 21
    assert data['last_run']['started_at'].endswith('+00:00')
    assert data['approved_documents'] == 1
    assert data['indexed_documents'] == 1
    assert data['indexed_chunks'] == 1


def test_empty_question_rejected(api):
    client, _, _ = api
    assert client.post('/api/ai-chat/message', json={'message': '   '}).status_code == 422


def test_library_and_history_require_authentication(api):
    client, _, _ = api
    app.dependency_overrides.pop(get_current_user)
    assert client.get('/api/ai-chat/documents').status_code == 401
    assert client.get('/api/ai-chat/conversations').status_code == 401
    assert client.post('/api/ai-chat/documents', files={'file': ('test.txt', b'test')}).status_code == 401


def test_generation_failure_uses_only_retrieved_excerpts(api, rag, monkeypatch):
    client, _, user = api
    rag.ingest(user.UserID, 'lua.md', 'Chăm sóc lúa: kiểm tra thoát nước.'.encode())
    async def fail(*args):
        raise RuntimeError('offline')
    monkeypatch.setattr('app.api.ai_chat._call_local_ai', fail)
    response = client.post('/api/ai-chat/message', json={'message': 'Chăm sóc lúa?', 'session_id': 'fallback'})
    assert response.status_code == 200
    data = response.json()['data']
    assert 'chưa tạo được' in data['reply'] and '[TL1]' in data['reply']
    assert data['history_saved']


def test_memory_is_bounded_and_excludes_deleted_turns(api):
    _, db, user = api
    for i in range(10):
        add_turn(db, user.UserID, 'long', f'Câu {i} ' + 'x' * 3000, 'y' * 3000)
    history, _ = load_memory(db, user.UserID, 'long')
    assert len(history) == 6
    assert history[0]['content'].startswith('Câu 7 ')
    assert sum(len(m['content']) for m in history) <= 3900


def test_schema_upgrade_preserves_existing_conversations(monkeypatch):
    from app.core import database
    from sqlalchemy import inspect, text
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE AIConversations (ConvID INTEGER PRIMARY KEY, UserMessage TEXT)'))
        connection.execute(text("INSERT INTO AIConversations VALUES (1, 'existing')"))
    monkeypatch.setattr(database, 'engine', engine)
    monkeypatch.setattr(database, 'active_database_url', 'sqlite://')
    database._apply_lightweight_schema_upgrades()
    database._apply_lightweight_schema_upgrades()
    assert 'deleted_at' in {column['name'] for column in inspect(engine).get_columns('AIConversations')}
    with engine.connect() as connection:
        assert connection.execute(text('SELECT UserMessage FROM AIConversations')).scalar() == 'existing'
    engine.dispose()
