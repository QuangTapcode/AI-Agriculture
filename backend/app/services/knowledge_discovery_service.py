"""Query-triggered discovery for the bounded, official-source RAG pipeline."""

import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.knowledge import KnowledgeDiscoveryJob, KnowledgeDocument
from app.services.ai_intent_service import normalize_user_text
from app.services.knowledge_ingestion_service import knowledge_ingestion_service
from app.services.source_discovery_service import source_discovery_service

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("queued", "running")
STOP_WORDS = {
    "va", "voi", "cho", "toi", "minh", "ban", "cua", "la", "nhu", "the", "nao",
    "can", "co", "gi", "nac", "mot", "nhung", "tai", "sao", "hay", "duoc", "khong",
    "cach", "xu", "ly", "tren", "theo", "giup", "nen", "voi", "khi",
    "huong", "dan", "tung", "muc",
}
INTENT_TERMS = {
    "cultivation_advice": ("ky thuat", "canh tac", "trong trot"),
    "quality_analysis": ("sau benh", "bao ve thuc vat"),
    "weather_analysis": ("thoi tiet", "khi hau"),
    "price_analysis": ("gia", "thi truong", "nong san"),
    "harvest_analysis": ("mua vu", "thu hoach"),
    "livestock_advice": ("chăn nuôi", "dinh dưỡng vật nuôi"),
}

# Keep common crop varieties together so the browser search receives a useful
# topic instead of three unrelated tokens ("nho", "ngon", "tay"). The list
# is intentionally small and deterministic; new phrases can be added when a
# source registry starts supporting another crop variety.
TOPIC_PHRASES = (
    ("nho ngon tay", "nho ngón tay"),
    ("nuoi lon", "nuôi lợn"),
    ("ca phe robusta", "cà phê Robusta"),
    ("ca phe arabica", "cà phê Arabica"),
)


def extract_query_keywords(
    question: str,
    *,
    crop: str | None = None,
    region: str | None = None,
    intent: str | None = None,
) -> list[str]:
    """Return deterministic keywords without asking the model to invent URLs."""
    normalized = normalize_user_text(question)
    phrases = [display for normalized_phrase, display in TOPIC_PHRASES if normalized_phrase in normalized]
    if "cho an" in normalized and "tuoi" in normalized:
        phrases.append("cho ăn theo độ tuổi")
    phrase_tokens = {
        token
        for phrase in phrases
        for token in normalize_user_text(phrase).split()
    }
    words = [word for word in normalized.split() if len(word) >= 3 and word not in STOP_WORDS]
    original = question.casefold()
    if "nhỏ" in original and re.search(r"(?<!\w)nho(?!\w)", original) is None:
        words = [word for word in words if word != "nho"]
    words = [word for word in words if word not in phrase_tokens]
    values = [normalize_user_text(value) for value in (crop, region) if value]
    result: list[str] = []
    intent_values = list(INTENT_TERMS.get(intent or "", ()))
    for value in [*phrases, *values, *intent_values, *words]:
        if value and value not in result:
            result.append(value)
    return result[:12]


def _question_hash(question: str) -> str:
    return hashlib.sha256(normalize_user_text(question).encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    """Return a naive UTC datetime for the existing database columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _serialize(job: KnowledgeDiscoveryJob) -> dict:
    try:
        keywords = json.loads(job.Keywords or "[]")
    except (TypeError, ValueError):
        keywords = []
    if job.Status in ACTIVE_STATUSES:
        verification_status = "pending"
        apply_status = "pending"
    elif job.Status in {"failed", "unavailable"}:
        verification_status = "failed"
        apply_status = "not_applied"
    elif job.DocumentsIndexed:
        verification_status = "passed"
        apply_status = "applied"
    elif job.DocumentsProcessed:
        verification_status = "checked"
        apply_status = "not_applied"
    else:
        verification_status = "not_run"
        apply_status = "not_applied"
    return {
        "job_id": job.JobID,
        "status": job.Status,
        "question": job.Question,
        "keywords": keywords,
        "intent": job.Intent,
        "crop": job.Crop,
        "region": job.Region,
        "candidates_found": job.CandidatesFound,
        "documents_processed": job.DocumentsProcessed,
        "documents_indexed": job.DocumentsIndexed,
        "verification_status": verification_status,
        "apply_status": apply_status,
        "error": job.ErrorMessage,
        "created_at": job.CreatedAt.isoformat() if job.CreatedAt else None,
        "started_at": job.StartedAt.isoformat() if job.StartedAt else None,
        "finished_at": job.FinishedAt.isoformat() if job.FinishedAt else None,
    }


def _rejection_reason(db: Session, url: str) -> str:
    """Return a short, user-facing reason for a quality-gate rejection."""
    canonical = (url or "").split("#", 1)[0].rstrip("/") or (url or "")
    url_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    row = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.URLHash == url_hash,
        KnowledgeDocument.Status == "rejected",
    ).order_by(desc(KnowledgeDocument.FetchedAt), desc(KnowledgeDocument.DocumentKey)).first()
    if row is None:
        return "không đạt kiểm tra chất lượng; mở Kho tài liệu ở trạng thái Không đạt để xem chi tiết"
    try:
        report = json.loads(row.QualityReport or "{}")
    except (TypeError, ValueError):
        report = {}
    checks: list[str] = []
    if report.get("minimum_length") is False:
        checks.append("nội dung quá ngắn")
    if report.get("agriculture_relevant") is False:
        checks.append("thiếu thuật ngữ nông nghiệp")
    coverage = report.get("question_coverage") or {}
    if coverage.get("total") and not coverage.get("passed"):
        checks.append("không vượt kiểm tra câu hỏi")
    if checks:
        return "; ".join(checks)
    return "không đạt kiểm tra chất lượng; mở Kho tài liệu ở trạng thái Không đạt để xem chi tiết"


class KnowledgeDiscoveryService:
    def enqueue(
        self,
        db: Session,
        *,
        question: str,
        user_id: int | None,
        intent: str | None = None,
        crop: str | None = None,
        region: str | None = None,
        force: bool = False,
    ) -> dict:
        if not settings.KNOWLEDGE_QUERY_DISCOVERY_ENABLED:
            return {"status": "disabled", "job_id": None, "message": "Tự tìm nguồn đang tắt."}

        question = question.strip()
        question_hash = _question_hash(question)
        existing_query = db.query(KnowledgeDiscoveryJob).filter(
            KnowledgeDiscoveryJob.QuestionHash == question_hash,
            KnowledgeDiscoveryJob.UserID == user_id,
        )
        existing = existing_query.filter(KnowledgeDiscoveryJob.Status.in_(ACTIVE_STATUSES)).order_by(
            desc(KnowledgeDiscoveryJob.CreatedAt)
        ).first()
        if existing:
            result = _serialize(existing)
            result.update({"status": existing.Status, "deduplicated": True,
                           "message": "Câu hỏi này đang được tìm nguồn."})
            return result

        cooldown_seconds = max(0, int(settings.KNOWLEDGE_QUERY_DISCOVERY_COOLDOWN_SECONDS))
        if cooldown_seconds and not force:
            cutoff = _utcnow() - timedelta(seconds=cooldown_seconds)
            recent = existing_query.filter(
                KnowledgeDiscoveryJob.CreatedAt >= cutoff,
                KnowledgeDiscoveryJob.Status.in_(("indexed", "completed", "no_match")),
            ).order_by(desc(KnowledgeDiscoveryJob.CreatedAt)).first()
            if recent:
                result = _serialize(recent)
                result.update({"deduplicated": True,
                               "message": "Câu hỏi này đã được tìm nguồn gần đây."})
                return result

        keywords = extract_query_keywords(question, crop=crop, region=region, intent=intent)
        job = KnowledgeDiscoveryJob(
            UserID=user_id,
            Question=question,
            QuestionHash=question_hash,
            Keywords=json.dumps(keywords, ensure_ascii=False),
            Intent=intent,
            Crop=crop,
            Region=region,
            Status="queued",
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        try:
            from app.tasks.knowledge_discovery_tasks import discover_for_question

            discover_for_question.delay(job.JobID)
        except Exception as exc:
            logger.warning("Could not enqueue query discovery job %s: %s", job.JobID, exc)
            job.Status = "unavailable"
            job.ErrorMessage = "Không khởi động được worker tìm nguồn."
            job.FinishedAt = _utcnow()
            db.commit()
            result = _serialize(job)
            result["message"] = "Chưa thể khởi động tác vụ tìm nguồn."
            return result

        result = _serialize(job)
        result["message"] = "Đã bắt đầu tìm nguồn chính thức liên quan."
        return result

    def run(self, db: Session, job_id: int) -> dict:
        job = db.get(KnowledgeDiscoveryJob, job_id)
        if not job:
            raise LookupError("Không tìm thấy tác vụ tìm nguồn.")
        if job.Status not in ACTIVE_STATUSES:
            return _serialize(job)

        job.Status = "running"
        job.StartedAt = _utcnow()
        db.commit()
        errors: list[str] = []
        discovery_warnings: list[str] = []
        rejected_count = 0
        try:
            try:
                keywords = json.loads(job.Keywords or "[]")
            except (TypeError, ValueError):
                keywords = []
            candidates = source_discovery_service.discover_for_query(
                keywords,
                crop=job.Crop,
                region=job.Region,
                max_candidates=settings.KNOWLEDGE_QUERY_DISCOVERY_MAX_CANDIDATES,
                warnings=discovery_warnings,
            )
            job.CandidatesFound = len(candidates)
            errors.extend(discovery_warnings)
            for candidate in candidates:
                try:
                    if candidate.get("source_is_new"):
                        try:
                            source_discovery_service.record_query_source_candidate(db, candidate)
                        except Exception as exc:
                            errors.append(f"{candidate.get('url', 'unknown')}: cannot record the new source ({exc})")
                            logger.exception("Could not record the newly discovered source %s", candidate.get("url"))
                    source = candidate["source"]
                    outcome = knowledge_ingestion_service.process(db, source, candidate["url"])
                    job.DocumentsProcessed += 1
                    if outcome == "approved":
                        job.DocumentsIndexed += 1
                    elif outcome == "rejected":
                        rejected_count += 1
                        errors.append(f"{candidate.get('url', 'unknown')}: {_rejection_reason(db, candidate.get('url', ''))}")
                except Exception as exc:
                    errors.append(f"{candidate.get('url', 'unknown')}: {exc}")
                    logger.exception("Query discovery ingestion failed for %s", candidate.get("url"))

            if job.DocumentsIndexed:
                job.Status = "indexed"
            elif job.CandidatesFound:
                job.Status = "completed"
            else:
                job.Status = "no_match"
        except Exception as exc:
            logger.exception("Query discovery failed for job %s", job_id)
            errors.append(str(exc))
            job.Status = "failed"
        if rejected_count and not errors:
            errors.append(f"Đã kiểm tra {rejected_count} tài liệu nhưng chưa tài liệu nào đạt quality gate.")
        job.ErrorMessage = "\n".join(errors)[:4000] or None
        job.FinishedAt = _utcnow()
        db.commit()
        db.refresh(job)
        return _serialize(job)

    def get(self, db: Session, job_id: int, *, user_id: int | None) -> dict | None:
        query = db.query(KnowledgeDiscoveryJob).filter(KnowledgeDiscoveryJob.JobID == job_id)
        if user_id is not None:
            query = query.filter(KnowledgeDiscoveryJob.UserID == user_id)
        job = query.first()
        return _serialize(job) if job else None


knowledge_discovery_service = KnowledgeDiscoveryService()
