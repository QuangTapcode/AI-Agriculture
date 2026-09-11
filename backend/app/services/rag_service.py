"""Local document retrieval. Collections are isolated by owner and embedding model."""
import hashlib
import io
import logging
import math
import unicodedata
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from threading import Lock

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 300_000


def _normalized_search_text(value: str | None) -> str:
    text = unicodedata.normalize("NFD", value or "")
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return text.lower().replace("đ", "d")


def _source_conflicts_with_query(query: str, metadata: dict) -> bool:
    normalized_query = _normalized_search_text(query)
    normalized_title = _normalized_search_text(metadata.get("name"))
    asks_robusta = "robusta" in normalized_query or "ca phe voi" in normalized_query
    asks_arabica = "arabica" in normalized_query or "ca phe che" in normalized_query
    title_is_robusta = "robusta" in normalized_title or "ca phe voi" in normalized_title
    title_is_arabica = "arabica" in normalized_title or "ca phe che" in normalized_title
    return (asks_robusta and title_is_arabica) or (asks_arabica and title_is_robusta)


def extract_pages(filename: str, content: bytes, max_bytes: int = MAX_UPLOAD_BYTES,
                  max_text_chars: int = MAX_TEXT_CHARS) -> list[tuple[int, str]]:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".txt", ".md"}:
        raise ValueError("Chỉ hỗ trợ PDF, TXT và Markdown.")
    if not content or len(content) > max_bytes:
        raise ValueError("Tài liệu phải có nội dung và không vượt quá 10 MB.")
    if suffix == ".pdf":
        from pypdf import PdfReader
        try:
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted or len(reader.pages) > 300:
                raise ValueError("PDF phải không có mật khẩu và tối đa 300 trang.")
            pages = []
            length = 0
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                length += len(text)
                if length > max_text_chars:
                    raise ValueError("Tài liệu quá dài; hãy chia thành các tệp nhỏ hơn.")
                pages.append((i + 1, text))
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Không đọc được PDF. Hãy dùng PDF có lớp văn bản.") from exc
    else:
        try:
            text_pages = content.decode("utf-8-sig").split("\f")
            pages = [(index, text) for index, text in enumerate(text_pages, start=1)]
        except UnicodeDecodeError as exc:
            raise ValueError("Tệp văn bản cần được lưu bằng UTF-8.") from exc
    if sum(len(text) for _, text in pages) > max_text_chars:
        raise ValueError("Tài liệu quá dài; hãy chia thành các tệp nhỏ hơn.")
    if not any(text.strip() for _, text in pages):
        raise ValueError("Không có văn bản để tra cứu. PDF ảnh cần OCR trước khi nạp.")
    return pages


def chunk_pages(pages: list[tuple[int, str]]) -> list[dict]:
    chunks = []
    for page, text in pages:
        text = text.replace("\x00", "").strip()
        start = 0
        while start < len(text):
            end = min(start + 1000, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start + 700, end)
                if boundary > start:
                    end = boundary
            excerpt = text[start:end].strip()
            if excerpt:
                chunks.append({"page": page, "text": excerpt})
            if end == len(text):
                break
            start = end - 150
    return chunks


_chroma_init_lock = Lock()


@lru_cache(maxsize=4)
def _cached_chroma(path: str):
    import chromadb
    from chromadb.config import Settings
    return chromadb.PersistentClient(path=path, settings=Settings(anonymized_telemetry=False))


def _chroma(path: str):
    # functools.lru_cache may execute the wrapped function more than once when
    # concurrent calls miss the same key. Chroma's in-process system registry
    # cannot tolerate concurrent PersistentClient initialization for one path.
    with _chroma_init_lock:
        return _cached_chroma(path)


class RagService:
    def collection(self, owner: int):
        path = Path(settings.RAG_STORAGE_PATH)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        model_key = hashlib.sha256(settings.RAG_EMBEDDING_MODEL.encode()).hexdigest()[:12]
        return _chroma(str(path.resolve())).get_or_create_collection(
            name=f"agri-user-{owner}-{model_key}",
            metadata={"hnsw:space": "cosine"}, embedding_function=None,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        with httpx.Client(timeout=settings.RAG_TIMEOUT_SECONDS) as client:
            response = client.post(f"{settings.AI_BASE_URL.rstrip('/')}/api/embed", json={
                "model": settings.RAG_EMBEDDING_MODEL, "input": texts,
                # A small embedding model runs on CPU, leaving the 4 GB GPU for chat.
                "truncate": False, "keep_alive": "10m", "options": {"num_gpu": 0},
            })
            response.raise_for_status()
            vectors = response.json()["embeddings"]
        if len(vectors) != len(texts) or not all(vectors):
            raise ValueError("Embedding không hợp lệ.")
        return vectors

    def prepare(self, filename: str, content: bytes) -> dict:
        chunks = chunk_pages(extract_pages(filename, content))
        document_id = hashlib.sha256(content).hexdigest()
        embeddings = []
        for start in range(0, len(chunks), 16):
            embeddings.extend(self.embed([c["text"] for c in chunks[start:start + 16]]))
        name = filename.replace("\\", "/").split("/")[-1][:200]
        return {"id": document_id, "name": name, "chunks": chunks, "embeddings": embeddings}

    def publish(self, owner: int, prepared: dict, metadata: dict | None = None) -> dict:
        collection = self.collection(owner)
        document_id = prepared["id"]
        existing = collection.get(where={"document_id": document_id}, limit=1)
        if existing["ids"]:
            return {"id": document_id, "name": existing["metadatas"][0]["name"], "duplicate": True}
        chunks = prepared["chunks"]
        if collection.count() + len(chunks) > 10_000:
            raise ValueError("Kho tài liệu đã đầy. Hãy xóa tài liệu không cần thiết.")
        name = prepared["name"]
        created_at = datetime.now(timezone.utc).isoformat()
        extra = {key: value for key, value in (metadata or {}).items()
                 if value is not None and isinstance(value, (str, int, float, bool))}
        collection.upsert(
            ids=[f"{document_id}-{i}" for i in range(len(chunks))],
            documents=[c["text"] for c in chunks], embeddings=prepared["embeddings"],
            metadatas=[{"document_id": document_id, "name": name, "page": c["page"],
                        "chunk": i + 1, "created_at": created_at, **extra}
                       for i, c in enumerate(chunks)],
        )
        return {"id": document_id, "name": name, "chunks": len(chunks), "duplicate": False}

    def ingest(self, owner: int, filename: str, content: bytes, metadata: dict | None = None) -> dict:
        document_id = hashlib.sha256(content).hexdigest()
        existing = self.collection(owner).get(where={"document_id": document_id}, limit=1)
        if existing["ids"]:
            return {"id": document_id, "name": existing["metadatas"][0]["name"], "duplicate": True}
        return self.publish(owner, self.prepare(filename, content), metadata)

    def question_coverage(self, prepared: dict, questions: list[str], threshold: float) -> dict:
        if not questions:
            return {"passed": 0, "total": 0, "scores": []}
        query_vectors = self.embed([question[:4000] for question in questions])
        scores = []
        for query in query_vectors:
            best = 0.0
            for chunk in prepared["embeddings"]:
                denominator = math.sqrt(sum(x * x for x in query)) * math.sqrt(sum(x * x for x in chunk))
                if denominator:
                    best = max(best, sum(a * b for a, b in zip(query, chunk)) / denominator)
            scores.append(round(best, 4))
        return {"passed": sum(score >= threshold for score in scores), "total": len(scores), "scores": scores}

    def documents(self, owner: int) -> list[dict]:
        result = self.collection(owner).get(include=["metadatas"])
        documents = {}
        for meta in result["metadatas"]:
            item = documents.setdefault(meta["document_id"], {
                "id": meta["document_id"], "name": meta["name"],
                "created_at": meta["created_at"], "chunks": 0,
            })
            item["chunks"] += 1
        return sorted(documents.values(), key=lambda d: d["created_at"], reverse=True)

    def delete(self, owner: int, document_id: str):
        self.collection(owner).delete(where={"document_id": document_id})

    def retrieve(self, query: str, owner: int | None) -> dict:
        if not settings.RAG_ENABLED:
            return {"status": "disabled", "sources": []}
        try:
            owners = [0] + ([owner] if owner is not None and owner != 0 else [])
            collections = [self.collection(item) for item in owners]
            available = [collection for collection in collections if collection.count()]
            if not available:
                return {"status": "empty", "sources": []}
            query_embedding = self.embed([query[:4000]])
            candidates = []
            for collection in available:
                result = collection.query(
                    query_embeddings=query_embedding,
                    n_results=min(max(1, settings.RAG_TOP_K), 6, collection.count()),
                    include=["documents", "metadatas", "distances"],
                )
                for text, meta, distance in zip(result["documents"][0], result["metadatas"][0], result["distances"][0]):
                    if _source_conflicts_with_query(query, meta):
                        continue
                    score = 1 - distance
                    if score >= settings.RAG_MIN_SIMILARITY:
                        candidates.append((score, text, meta))
            candidates.sort(key=lambda item: item[0], reverse=True)
            sources = []
            seen = set()
            per_document = {}
            for score, excerpt, meta in candidates:
                key = (meta["document_id"], meta["chunk"])
                if key in seen:
                    continue
                document_id = meta["document_id"]
                if per_document.get(document_id, 0) >= settings.RAG_MAX_CHUNKS_PER_DOCUMENT:
                    continue
                seen.add(key)
                per_document[document_id] = per_document.get(document_id, 0) + 1
                sources.append({"citation": f"TL{len(sources) + 1}", "document_id": meta["document_id"],
                                "name": meta["name"], "page": meta["page"], "chunk": meta["chunk"],
                                "excerpt": excerpt, "score": round(score, 4),
                                "source_name": meta.get("source_name"), "source_url": meta.get("source_url"),
                                "published_at": meta.get("published_at"), "region": meta.get("region"),
                                "crop": meta.get("crop"), "version": meta.get("version")})
                if len(sources) >= min(max(1, settings.RAG_TOP_K), 6):
                    break
            return {"status": "ready" if sources else "no_match", "sources": sources}
        except Exception:
            logger.exception("Document retrieval unavailable")
            return {"status": "unavailable", "sources": []}


rag_service = RagService()
