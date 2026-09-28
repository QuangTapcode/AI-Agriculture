"""Local document retrieval. Collections are isolated by owner and embedding model."""
import hashlib
import io
import logging
import math
import re
import unicodedata
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from threading import Lock
from time import monotonic

import httpx

from app.core.config import settings
from app.services.rag_ranking import rank_hybrid_candidates

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


def _has_normalized_term(text: str, term: str) -> bool:
    if not term:
        return True
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None


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


def chunk_pages(pages: list[tuple[int, str]], chunk_size: int = 1000,
                overlap: int = 150) -> list[dict]:
    chunk_size = max(1, int(chunk_size))
    overlap = min(max(0, int(overlap)), chunk_size - 1)
    chunks = []
    for page, text in pages:
        text = text.replace("\x00", "").strip()
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start + int(chunk_size * 0.7), end)
                if boundary > start:
                    end = boundary
            excerpt = text[start:end].strip()
            if excerpt:
                chunks.append({"page": page, "text": excerpt})
            if end == len(text):
                break
            start = end - overlap
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
        chunks = chunk_pages(
            extract_pages(filename, content),
            chunk_size=settings.RAG_CHUNK_SIZE,
            overlap=settings.RAG_CHUNK_OVERLAP,
        )
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
            rows = []
            vector_scores = {}
            vector_candidate_count = 0
            for collection_index, collection in enumerate(available):
                snapshot = collection.get(include=["documents", "metadatas"])
                for row_index, (document, meta) in enumerate(zip(
                    snapshot.get("documents") or [], snapshot.get("metadatas") or [],
                )):
                    meta = meta or {}
                    searchable = _normalized_search_text(
                        " ".join(str(meta.get(field) or "") for field in (
                            "name", "source_name", "crop", "region",
                        )) + " " + str(document or "")
                    )
                    if _source_conflicts_with_query(query, meta):
                        continue
                    if crop_term and not _has_normalized_term(searchable, crop_term):
                        continue
                    row_key = f"{collection_index}:{meta.get('document_id') or row_index}:{meta.get('chunk') or row_index}"
                    rows.append({"id": row_key, "document": document or "", "metadata": meta})

                query_args = {
                    "query_embeddings": query_embedding,
                    "n_results": min(
                        max(1, int(getattr(settings, "RAG_HYBRID_CANDIDATE_K", 24))),
                        collection.count(),
                    ),
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
                vector_candidate_count += len((result.get("documents") or [[]])[0])
                for row_index, (text, meta, distance) in enumerate(zip(
                    (result.get("documents") or [[]])[0],
                    (result.get("metadatas") or [[]])[0],
                    (result.get("distances") or [[]])[0],
                )):
                    meta = meta or {}
                    if _source_conflicts_with_query(query, meta):
                        continue
                    if crop_term:
                        searchable = _normalized_search_text(
                            " ".join(str(meta.get(field) or "") for field in (
                                "name", "source_name", "crop", "region",
                            ))
                            + " " + str(text or "")
                        )
                        if not _has_normalized_term(searchable, crop_term):
                            continue
                    row_key = f"{collection_index}:{meta.get('document_id') or row_index}:{meta.get('chunk') or row_index}"
                    score = max(0.0, min(1.0, 1 - float(distance)))
                    if score >= settings.RAG_MIN_SIMILARITY:
                        vector_scores[row_key] = max(vector_scores.get(row_key, 0.0), score)

            ranked = rank_hybrid_candidates(
                rows,
                vector_scores,
                query,
                limit=min(max(1, int(settings.RAG_TOP_K)) * 3, 18),
                rrf_k=max(1, int(getattr(settings, "RAG_RRF_K", 60))),
                vector_weight=float(getattr(settings, "RAG_HYBRID_VECTOR_WEIGHT", 0.55)),
                lexical_weight=float(getattr(settings, "RAG_HYBRID_LEXICAL_WEIGHT", 0.45)),
            )
            sources = []
            seen = set()
            per_document = {}
            for candidate in ranked:
                meta = candidate.metadata
                key = (meta.get("document_id"), meta.get("chunk"))
                if key in seen:
                    continue
                document_id = meta.get("document_id") or candidate.key
                if per_document.get(document_id, 0) >= settings.RAG_MAX_CHUNKS_PER_DOCUMENT:
                    continue
                seen.add(key)
                per_document[document_id] = per_document.get(document_id, 0) + 1
                sources.append({"citation": f"TL{len(sources) + 1}", "document_id": meta["document_id"],
                                "name": meta["name"], "page": meta["page"], "chunk": meta["chunk"],
                                "excerpt": candidate.document, "score": candidate.rank_score,
                                "vector_score": candidate.vector_score,
                                "lexical_score": candidate.lexical_score,
                                "rrf_score": candidate.rrf_score,
                                "source_name": meta.get("source_name"), "source_url": meta.get("source_url"),
                                "published_at": meta.get("published_at"), "region": meta.get("region"),
                                "crop": meta.get("crop"), "version": meta.get("version")})
                if len(sources) >= min(max(1, settings.RAG_TOP_K), 6):
                    break
            if not sources:
                return {"status": "no_match", "sources": []}
            return {
                "status": "ready",
                "sources": sources,
                "retrieval": {
                    "mode": "hybrid",
                    "ranking": "rrf",
                    "vector_candidates": vector_candidate_count,
                    "lexical_candidates": len(rows),
                    "returned": len(sources),
                },
            }
        except Exception:
            logger.exception("Document retrieval unavailable")
            return {"status": "unavailable", "sources": []}


rag_service = RagService()
