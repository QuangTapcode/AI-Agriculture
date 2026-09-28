"""Small, deterministic agent loop around hybrid retrieval.

The loop is intentionally local and bounded: it plans a focused query, grades
the returned evidence, rewrites once when the evidence is weak, and stops. It
does not ask an LLM to decide whether an unrelated document is relevant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import settings
from app.services.ai_intent_service import normalize_user_text
from app.services.rag_ranking import tokenize
from app.services.rag_service import rag_service


_STOPWORDS = {
    "cho", "cua", "cay", "tai", "o", "va", "la", "gi", "nhu", "the",
    "trong", "voi", "mot", "nhung", "can", "nen", "bao", "nhieu",
}


@dataclass(frozen=True)
class EvidenceGrade:
    score: float
    reason: str


def _has_term(text: str, term: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None


class AgenticRagService:
    """Plan, retrieve, grade and rewrite within a small fixed step budget."""

    def __init__(self, retriever=None, *, max_steps: int | None = None,
                 min_relevance: float | None = None):
        self.retriever = retriever or rag_service
        self.max_steps = max(1, int(max_steps if max_steps is not None else settings.RAG_AGENT_MAX_STEPS))
        self.min_relevance = float(
            min_relevance if min_relevance is not None else settings.RAG_AGENT_MIN_RELEVANCE
        )

    @staticmethod
    def _plan_queries(query: str, *, crop: str | None, region: str | None,
                      intent: str | None, max_steps: int) -> list[str]:
        terms = [term for term in tokenize(query) if term not in _STOPWORDS]
        focus = " ".join(dict.fromkeys(terms))
        planned = [query]
        if crop or region or intent:
            planned.append(" ".join(part for part in (crop, region, intent, focus) if part))
        if crop:
            planned.append(" ".join(part for part in (crop, focus) if part))
        result = []
        for item in planned:
            item = " ".join(str(item).split()).strip()
            if item and normalize_user_text(item) not in {normalize_user_text(old) for old in result}:
                result.append(item)
            if len(result) >= max_steps:
                break
        return result or [query]

    @staticmethod
    def _grade(query: str, result: dict, *, crop: str | None) -> EvidenceGrade:
        sources = result.get("sources") or [] if isinstance(result, dict) else []
        if not sources:
            return EvidenceGrade(0.0, "no_sources")
        query_terms = set(tokenize(query)) - _STOPWORDS
        best = EvidenceGrade(0.0, "weak_overlap")
        normalized_crop = normalize_user_text(crop or "")
        for source in sources:
            evidence = normalize_user_text(" ".join(
                str(source.get(field) or "")
                for field in ("name", "source_name", "excerpt", "crop", "region")
            ))
            if normalized_crop and not _has_term(evidence, normalized_crop):
                continue
            evidence_terms = set(tokenize(evidence))
            overlap = len(query_terms & evidence_terms) / max(1, len(query_terms))
            source_score = max(0.0, min(1.0, float(source.get("score") or 0.0)))
            crop_signal = 0.35 if normalized_crop else 0.0
            score = min(1.0, 0.45 * source_score + crop_signal + 0.20 * overlap)
            reason = "crop_and_topic_match" if normalized_crop else "topic_match"
            if score > best.score:
                best = EvidenceGrade(round(score, 4), reason)
        return best

    def retrieve(self, query: str, owner: int | None, crop: str | None = None,
                 *, region: str | None = None, intent: str | None = None) -> dict:
        queries = self._plan_queries(
            query, crop=crop, region=region, intent=intent, max_steps=self.max_steps,
        )
        grades = []
        chosen = None
        chosen_grade = EvidenceGrade(0.0, "no_sources")
        for step, planned_query in enumerate(queries, start=1):
            result = self.retriever.retrieve(planned_query, owner, crop)
            grade = self._grade(planned_query, result, crop=crop)
            grades.append({"step": step, "query": planned_query, "score": grade.score, "reason": grade.reason})
            if chosen is None or grade.score > chosen_grade.score:
                chosen, chosen_grade = result, grade
            if grade.score >= self.min_relevance and result.get("status") == "ready":
                break

        chosen = chosen or {"status": "no_match", "sources": []}
        if chosen_grade.score < self.min_relevance and chosen.get("status") not in {
            "empty", "unavailable", "disabled",
        }:
            chosen = {**chosen, "status": "no_match", "sources": []}
            outcome = "no_relevant_evidence"
        elif len(grades) > 1:
            outcome = "evidence_found_after_rewrite"
        else:
            outcome = "evidence_found_first_pass"
        return {
            **chosen,
            "agentic": {
                "mode": "plan_retrieve_grade_rewrite",
                "steps": len(grades),
                "queries": queries[:len(grades)],
                "grades": grades,
                "outcome": outcome,
            },
        }


agentic_rag_service = AgenticRagService()
