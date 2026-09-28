# ADR 0001: Hybrid search, RRF ranking, and bounded agentic RAG

- Status: accepted
- Date: 2026-09-28
- Scope: `backend/app/services/rag_service.py`, `rag_ranking.py`, `agentic_rag_service.py`

## Context

The previous retriever used only Chroma cosine similarity. That works for
semantically similar text, but it can miss exact agricultural terms, crop names,
varieties, disease names, and numeric units. A vector top-k result can also be
returned even when the evidence is weak or belongs to a nearby crop.

The assistant needs three properties at the same time:

1. exact-term recall from the document text and metadata;
2. a stable ranking that combines semantic and lexical evidence;
3. a bounded retry path when the first retrieval result is irrelevant.

## Decision

Keep Chroma as the vector store and add two local layers:

- **Hybrid search:** retrieve vector candidates from Chroma and calculate BM25
  over the bounded collection snapshot. The candidate lists are fused with
  reciprocal rank fusion (RRF).
- **RAG ranking:** each source exposes `vector_score`, `lexical_score`,
  `rrf_score`, and the final fused `score`. Metadata crop/region filters and
  one-chunk-per-document diversity are applied before the response is built.
- **Agentic RAG:** `AgenticRagService` performs a deterministic
  plan → retrieve → grade → rewrite loop. It runs at most
  `RAG_AGENT_MAX_STEPS` steps, stops when the evidence reaches
  `RAG_AGENT_MIN_RELEVANCE`, and returns an `agentic` trace in the RAG payload.
  The planner does not call an LLM, so the retry decision remains predictable
  and does not invent search terms from model memory.

```text
User question
    |
    v
Agentic planner -- crop/region/intent focused query
    |
    v
Hybrid retriever
    |-- Chroma vector candidates
    |-- BM25 lexical candidates
    '-- RRF + metadata/diversity ranking
    |
    v
Evidence grader -- enough? -- no --> bounded query rewrite (once by default)
    |
    '-- yes
    v
Grounding policy -> model prompt with citations or explicit refusal
```

## Configuration

| Variable | Default | Meaning |
|---|---:|---|
| `RAG_HYBRID_CANDIDATE_K` | `24` | Vector candidates per collection before fusion |
| `RAG_HYBRID_VECTOR_WEIGHT` | `0.55` | Weight for normalized vector similarity |
| `RAG_HYBRID_LEXICAL_WEIGHT` | `0.45` | Weight for normalized BM25 signal |
| `RAG_RRF_K` | `60` | RRF smoothing constant |
| `RAG_AGENT_MAX_STEPS` | `2` | Maximum retrieval attempts per request |
| `RAG_AGENT_MIN_RELEVANCE` | `0.18` | Evidence grade needed to stop rewriting |

## Trade-offs

- BM25 scans the collection snapshot, so retrieval does more local CPU work than
  vector-only search. The collection is bounded by the existing 10,000-chunk
  limit and avoids adding a second external search service.
- The agent loop may perform one extra embedding/query call. The fixed step cap
  prevents an open-ended tool loop and keeps latency observable in the existing
  timing payload.
- RRF is transparent and easy to tune, but it is not a learned cross-encoder.
  A future reranker can replace `rag_ranking.py` without changing the API
  contract.

## Verification

The behavior is covered by:

- `backend/tests/test_rag_hybrid.py`: lexical hit survives a misleading vector
  top-k result;
- `backend/tests/test_agentic_rag.py`: weak evidence triggers a focused rewrite;
- `backend/tests/test_ai_chat_intent.py`: public chat response exposes hybrid,
  RRF, and agentic metadata;
- existing RAG, grounding, query-discovery, and evaluator suites.
