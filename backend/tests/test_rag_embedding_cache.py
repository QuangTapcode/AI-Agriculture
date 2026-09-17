from app.services.rag_service import RagService


def test_embedding_cache_reuses_same_query_without_repeating_ollama(monkeypatch):
    service = RagService()
    calls = []

    def fake_request(texts):
        calls.append(texts)
        return [[float(len(texts[0]))]]

    monkeypatch.setattr(service, "_request_embeddings", fake_request)

    first = service.embed(["cà phê Đắk Lắk"])
    second = service.embed(["cà phê Đắk Lắk"])

    assert first == second
    assert calls == [["cà phê Đắk Lắk"]]


def test_embedding_cache_preserves_input_order_and_only_fetches_misses(monkeypatch):
    service = RagService()
    calls = []

    def fake_request(texts):
        calls.append(texts)
        return [[float(index)] for index, _ in enumerate(texts, start=1)]

    monkeypatch.setattr(service, "_request_embeddings", fake_request)

    result = service.embed(["a", "b"])
    again = service.embed(["b", "c"])

    assert result == [[1.0], [2.0]]
    assert again == [[2.0], [1.0]]
    assert calls == [["a", "b"], ["c"]]


def test_embedding_cache_preserves_duplicate_positions(monkeypatch):
    service = RagService()
    calls = []
    monkeypatch.setattr(service, "_request_embeddings", lambda texts: calls.append(texts) or [[7.0] for _ in texts])

    assert service.embed(["same", "same"]) == [[7.0], [7.0]]
    assert calls == [["same"]]
