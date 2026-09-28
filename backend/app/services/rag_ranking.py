"""Deterministic lexical/vector fusion used by the RAG retriever.

The module deliberately has no dependency on a search engine. Chroma remains
the vector store; BM25 is calculated over the bounded collection snapshot and
then fused with vector hits using reciprocal rank fusion (RRF).
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass


_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class RankedCandidate:
    key: str
    document: str
    metadata: dict
    vector_score: float
    lexical_score: float
    rrf_score: float
    rank_score: float


def tokenize(value: str | None) -> list[str]:
    """Tokenize already-normalized searchable text into stable ASCII terms."""
    normalized = unicodedata.normalize("NFD", value or "")
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    normalized = normalized.lower().replace("đ", "d")
    return [token for token in _TOKEN_RE.findall(normalized) if len(token) >= 2]


def _row_text(row: dict) -> str:
    metadata = row.get("metadata") or {}
    fields = (row.get("document"), metadata.get("name"), metadata.get("source_name"),
              metadata.get("crop"), metadata.get("region"))
    return " ".join(str(value or "") for value in fields)


def bm25_scores(query: str, rows: list[dict], *, k1: float = 1.5, b: float = 0.75) -> dict[str, float]:
    """Return BM25 scores for the collection snapshot keyed by row id."""
    query_terms = Counter(tokenize(query))
    if not query_terms or not rows:
        return {}

    documents = {str(row["id"]): tokenize(_row_text(row)) for row in rows}
    document_frequency = Counter(
        term
        for terms in documents.values()
        for term in set(terms)
    )
    average_length = sum(len(terms) for terms in documents.values()) / max(1, len(documents))
    total_documents = len(documents)
    scores: dict[str, float] = {}

    for key, terms in documents.items():
        frequencies = Counter(terms)
        length = len(terms)
        score = 0.0
        for term, query_frequency in query_terms.items():
            term_frequency = frequencies.get(term, 0)
            if not term_frequency:
                continue
            frequency = document_frequency.get(term, 0)
            inverse_document_frequency = math.log(
                1.0 + (total_documents - frequency + 0.5) / (frequency + 0.5)
            )
            denominator = term_frequency + k1 * (
                1.0 - b + b * length / max(1.0, average_length)
            )
            score += inverse_document_frequency * (
                (term_frequency * (k1 + 1.0)) / max(0.0001, denominator)
            ) * min(2, query_frequency)
        if score > 0:
            scores[key] = score
    return scores


def rank_hybrid_candidates(
    rows: list[dict],
    vector_scores: dict[str, float],
    query: str,
    *,
    limit: int,
    rrf_k: int = 60,
    vector_weight: float = 0.55,
    lexical_weight: float = 0.45,
) -> list[RankedCandidate]:
    """Fuse vector and BM25 results, keeping lexical-only hits in the pool."""
    if not rows or limit <= 0:
        return []

    lexical_scores = bm25_scores(query, rows)
    vector_ranked = sorted(vector_scores.items(), key=lambda item: item[1], reverse=True)
    lexical_ranked = sorted(lexical_scores.items(), key=lambda item: item[1], reverse=True)
    candidate_limit = max(limit * 3, 20)
    vector_rank = {key: index for index, (key, _) in enumerate(vector_ranked[:candidate_limit], start=1)}
    lexical_rank = {key: index for index, (key, _) in enumerate(lexical_ranked[:candidate_limit], start=1)}
    candidate_keys = set(vector_rank) | set(lexical_rank)
    rows_by_key = {str(row["id"]): row for row in rows}
    max_lexical = max(lexical_scores.values(), default=0.0)

    raw_rrf = {
        key: vector_weight / (rrf_k + vector_rank.get(key, rrf_k + candidate_limit + 1))
        + lexical_weight / (rrf_k + lexical_rank.get(key, rrf_k + candidate_limit + 1))
        for key in candidate_keys
    }
    max_rrf = max(raw_rrf.values(), default=1.0)
    candidates = []
    for key in candidate_keys:
        row = rows_by_key.get(key)
        if not row:
            continue
        vector_score = max(0.0, min(1.0, float(vector_scores.get(key, 0.0))))
        lexical_score = max(0.0, float(lexical_scores.get(key, 0.0)))
        lexical_signal = lexical_score / max_lexical if max_lexical else 0.0
        rrf_score = raw_rrf[key]
        rank_signal = rrf_score / max_rrf if max_rrf else 0.0
        rank_score = (
            0.75 * (vector_weight * vector_score + lexical_weight * lexical_signal)
            + 0.25 * rank_signal
        )
        candidates.append(RankedCandidate(
            key=key,
            document=str(row.get("document") or ""),
            metadata=dict(row.get("metadata") or {}),
            vector_score=round(vector_score, 6),
            lexical_score=round(lexical_score, 6),
            rrf_score=round(rrf_score, 8),
            rank_score=round(rank_score, 6),
        ))
    candidates.sort(key=lambda item: (item.rank_score, item.rrf_score, item.lexical_score), reverse=True)
    return candidates[:limit]
