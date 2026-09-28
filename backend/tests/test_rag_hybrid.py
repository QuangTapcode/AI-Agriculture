from app.core.config import settings
from app.services.rag_service import RagService


class FakeCollection:
    def __init__(self):
        self.rows = [
            {
                "id": "generic-1",
                "document": "Tài liệu hướng dẫn chăm sóc lúa sau mưa.",
                "metadata": {"document_id": "generic", "name": "lua.txt", "page": 1, "chunk": 1},
            },
            {
                "id": "coffee-1",
                "document": "Bệnh gỉ sắt trên cà phê: triệu chứng và biện pháp phòng trừ.",
                "metadata": {"document_id": "coffee", "name": "coffee.txt", "page": 2, "chunk": 1},
            },
        ]

    def count(self):
        return len(self.rows)

    def query(self, **_kwargs):
        row = self.rows[0]
        return {
            "documents": [[row["document"]]],
            "metadatas": [[row["metadata"]]],
            "distances": [[0.05]],
        }

    def get(self, **_kwargs):
        return {
            "ids": [row["id"] for row in self.rows],
            "documents": [row["document"] for row in self.rows],
            "metadatas": [row["metadata"] for row in self.rows],
        }


def test_hybrid_search_keeps_lexical_match_missed_by_vector_top_k(monkeypatch):
    service = RagService()
    collection = FakeCollection()
    monkeypatch.setattr(service, "collection", lambda _owner: collection)
    monkeypatch.setattr(service, "embed", lambda _texts: [[1.0, 0.0]])
    monkeypatch.setattr(settings, "RAG_TOP_K", 2)
    monkeypatch.setattr(settings, "RAG_MIN_SIMILARITY", 0.35)

    result = service.retrieve("triệu chứng bệnh gỉ sắt trên cà phê", None)

    assert result["status"] == "ready"
    assert {source["name"] for source in result["sources"]} == {"lua.txt", "coffee.txt"}
    assert result["retrieval"]["mode"] == "hybrid"
    assert result["retrieval"]["ranking"] == "rrf"
