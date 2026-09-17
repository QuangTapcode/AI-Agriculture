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
from time import monotonic

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


def _crop_metadata_values(crop: str | None) -> list[str]:
    """Return the spellings used by the ingestion metadata for a crop."""
    raw = str(crop or "").strip()
    if not raw:
        return []
    values = {raw, raw.title()}
    try:
        from app.services.data_quality_service import normalize_crop

        canonical = normalize_crop(raw)
        if canonical:
            values.update({canonical, canonical.title()})
    except Exception:
        # Retrieval must remain available even if the optional metadata
        # normalizer cannot be imported during application startup.
        pass
    return sorted(values)


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
    def __init__(self):
        self._embedding_cache: dict[str, tuple[float, list[float]]] = {}
        self._embedding_cache_lock = Lock()

    def collection(self, owner: int):
        path = Path(settings.RAG_STORAGE_PATH)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        model_key = hashlib.sha256(settings.RAG_EMBEDDING_MODEL.encode()).hexdigest()[:12]
        return _chroma(str(path.resolve())).get_or_create_collection(
            name=f"agri-user-{owner}-{model_key}",
            metadata={"hnsw:space": "cosine"}, embedding_function=None,
        )

    def _request_embeddings(self, texts: list[str]) -> list[list[float]]:
        with httpx.Client(timeout=settings.RAG_TIMEOUT_SECONDS) as client:
            response = client.post(f"{settings.AI_BASE_URL.rstrip('/')}/api/embed", json={
                "model": settings.RAG_EMBEDDING_MODEL, "input": texts,
                # A small embedding model runs on CPU, leaving the 4 GB GPU for chat.
                "truncate": False, "keep_alive": "10m", "options": {"num_gpu": settings.RAG_EMBED_NUM_GPU},
            })
            response.raise_for_status()
            vectors = response.json()["embeddings"]
        if len(vectors) != len(texts) or not all(vectors):
            raise ValueError("Embedding không hợp lệ.")
        return vectors

    @staticmethod
    def _embedding_key(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts with a bounded short lived cache.

        Query embeddings are repeated frequently while a farmer asks follow-up
        questions. Reusing a vector avoids a second Ollama model load without
        persisting user text outside the process.
        """
        if not texts:
            return []
        now = monotonic()
        ttl = max(0, int(settings.RAG_EMBED_CACHE_TTL_SECONDS))
        result: list[list[float] | None] = [None] * len(texts)
        misses: dict[str, tuple[int, str]] = {}
        with self._embedding_cache_lock:
            for index, text in enumerate(texts):
                key = self._embedding_key(text)
                cached = self._embedding_cache.get(key)
                if cached and ttl > 0 and now - cached[0] <= ttl:
                    result[index] = list(cached[1])
                else:
                    if cached:
                        self._embedding_cache.pop(key, None)
                    misses.setdefault(key, (index, text))
        if misses:
            missing_texts = [text for _, text in misses.values()]
            vectors = self._request_embeddings(missing_texts)
            vectors_by_key = dict(zip(misses, vectors))
            with self._embedding_cache_lock:
                if ttl > 0:
                    for key, vector in vectors_by_key.items():
                        self._embedding_cache[key] = (now, list(vector))
                max_size = max(1, int(settings.RAG_EMBED_CACHE_SIZE))
                while len(self._embedding_cache) > max_size:
                    self._embedding_cache.pop(next(iter(self._embedding_cache)))
            for key, (index, _) in misses.items():
                if ttl > 0:
                    result[index] = list(self._embedding_cache[key][1])
                else:
                    # Caching disabled: retain the vector for this call only.
                    result[index] = list(vectors_by_key[key])
        # A batch may contain the same text more than once. Fill every
        # duplicate position from the cache, preserving the caller's order.
        with self._embedding_cache_lock:
            for index, text in enumerate(texts):
                if result[index] is None:
                    cached = self._embedding_cache.get(self._embedding_key(text))
                    if cached:
                        result[index] = list(cached[1])
                    elif misses.get(self._embedding_key(text)):
                        result[index] = list(vectors_by_key[self._embedding_key(text)])
        if any(vector is None for vector in result):
            raise ValueError("Embedding không hợp lệ.")
        return [vector for vector in result if vector is not None]

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

    def retrieve(self, query: str, owner: int | None, crop: str | None = None) -> dict:
        if not settings.RAG_ENABLED:
            return {"status": "disabled", "sources": []}
        try:
            owners = [0] + ([owner] if owner is not None and owner != 0 else [])
            collections = [self.collection(item) for item in owners]
            available = [collection for collection in collections if collection.count()]
            if not available:
                return {"status": "empty", "sources": []}
            query_embedding = self.embed([query[:4000]])
            crop_term = _normalized_search_text(crop).strip()
            crop_values = _crop_metadata_values(crop)
            crop_where = {"crop": {"$in": crop_values}} if crop_values else None
            candidates = []
            for collection in available:
                query_args = {
                    "query_embeddings": query_embedding,
                    "n_results": min(max(1, settings.RAG_TOP_K), 6, collection.count()),
                    "include": ["documents", "metadatas", "distances"],
                }
                if crop_where:
                    query_args["where"] = crop_where
                try:
                    result = collection.query(**query_args)
                except Exception:
                    # Older Chroma versions may reject an $in filter. Fall
                    # back to vector retrieval and apply the same lexical crop
                    # check below instead of failing the whole assistant.
                    query_args.pop("where", None)
                    result = collection.query(**query_args)
                if crop_where and not (result.get("documents") or [[]])[0]:
                    # User uploads and older approved documents may not carry
                    # crop metadata. Retrieve their nearest chunks too, then
                    # keep only chunks whose title, source or text names the
                    # requested crop.
                    query_args.pop("where", None)
                    result = collection.query(**query_args)
                for text, meta, distance in zip(result["documents"][0], result["metadatas"][0], result["distances"][0]):
                    if _source_conflicts_with_query(query, meta):
                        continue
                    if crop_term:
                        searchable = _normalized_search_text(
                            " ".join(str(meta.get(field) or "") for field in ("name", "source_name", "crop"))
                            + " " + str(text or "")
                        )
                        if crop_term not in searchable:
                            continue
                    score = 1 - distance
                    if crop_term:
                        # Metadata-filtered hits should win over generic
                        # semantically similar documents from other crops.
                        score = min(1.0, score + 0.1)
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
