"""Authenticated document library and multi-turn conversation history."""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import String, case, cast, func, or_
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.conversation import AIConversation as Conversation
from app.models.ingestion import DataIngestionLog
from app.models.knowledge import KnowledgeDiscoveryJob, KnowledgeDocument, KnowledgeSourceCandidate
from app.models.user import User
from app.services.knowledge_ingestion_service import configured_sources
from app.services.rag_service import MAX_UPLOAD_BYTES, rag_service
from app.services.source_discovery_service import source_discovery_service
from app.services.knowledge_discovery_service import knowledge_discovery_service
from app.services.ai_intent_service import (
    classify_user_intent,
    extract_crop_from_message,
    extract_region_from_message,
)

router = APIRouter(prefix="/api/ai-chat", tags=["ai-chat"])
logger = logging.getLogger(__name__)


class KnowledgeDiscoveryRequest(BaseModel):
    """Topic submitted from the document library's immediate search control."""

    question: str = Field(..., min_length=3, max_length=8000)
    crop: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    intent: str | None = Field(default=None, max_length=50)


def visible_rows(db, user_id):
    return db.query(Conversation).filter(Conversation.UserID == user_id, Conversation.deleted_at.is_(None))


def session_key():
    # The former UI reused this ID for every conversation. Preserve old turns separately.
    return case((or_(Conversation.SessionID.is_(None), Conversation.SessionID == "frontend-session",
                     Conversation.SessionID == ""),
                 "legacy-" + cast(Conversation.ConvID, String)), else_=Conversation.SessionID)


def snapshot(row):
    try:
        value = json.loads(row.ContextSnapshot or "{}")
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def utc_iso(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def parse_quality_report(value):
    """Decode the persisted ingestion report without hiding malformed data."""
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        report = json.loads(value)
    except (TypeError, ValueError):
        return {"error": "Không đọc được báo cáo kiểm tra chất lượng."}
    return report if isinstance(report, dict) else {"error": "Báo cáo kiểm tra chất lượng không hợp lệ."}


def quality_rejection_details(value):
    """Return human-readable reasons derived only from the stored quality report."""
    report = parse_quality_report(value)
    reasons = []
    if report.get("error"):
        reasons.append(str(report["error"]))
    if report.get("minimum_length") is False:
        reasons.append("Nội dung chưa đạt độ dài tối thiểu")
    if report.get("agriculture_relevant") is False:
        reasons.append("Không đủ dấu hiệu nội dung nông nghiệp")
    coverage = report.get("question_coverage")
    if isinstance(coverage, dict) and coverage.get("total", 0) and coverage.get("passed", 0) == 0:
        reasons.append("Không vượt kiểm tra độ phù hợp với bộ câu hỏi")
    if not reasons:
        reasons.append(
            "Không có báo cáo kiểm tra chất lượng để xác định lý do."
            if not report else "Không đạt tiêu chuẩn kiểm tra chất lượng"
        )
    return reasons


def serialize_turn(row):
    context = snapshot(row)
    return {"id": row.ConvID, "user_message": row.UserMessage, "ai_response": row.AIResponse,
            "topic": row.Topic, "created_at": row.CreatedAt.replace(tzinfo=timezone.utc).isoformat(),
            "model": row.ModelName, "rag": context.get("rag", {"status": "not_used", "sources": []}),
            "knowledge_update": context.get("knowledge_update", {"status": "not_needed"})}


def load_memory(db, user_id, session_id):
    if user_id is None or not session_id or session_id == "frontend-session":
        return [], {}
    rows = visible_rows(db, user_id).filter(session_key() == session_id).order_by(
        Conversation.CreatedAt.desc(), Conversation.ConvID.desc()).limit(3).all()
    history = []
    for row in reversed(rows):
        history.extend([{"role": "user", "content": row.UserMessage[:500]},
                        {"role": "assistant", "content": row.AIResponse[:800]}])
    return history, snapshot(rows[0]) if rows else {}


@router.get("/conversations")
def conversations(q: str = Query(default="", max_length=200), offset: int = Query(default=0, ge=0),
                  limit: int = Query(default=20, ge=1, le=100),
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    key = session_key()
    base = visible_rows(db, user.UserID)
    if q.strip():
        matching = base.filter(or_(Conversation.UserMessage.contains(q.strip(), autoescape=True),
                                  Conversation.AIResponse.contains(q.strip(), autoescape=True))).with_entities(key)
        base = base.filter(key.in_(matching))
    groups = base.with_entities(key.label("session_id"), func.min(Conversation.ConvID).label("first_id"),
                                func.max(Conversation.ConvID).label("last_id"),
                                func.count(Conversation.ConvID).label("turn_count"),
                                func.max(Conversation.CreatedAt).label("updated_at")).group_by(key)
    total = groups.count()
    rows = groups.order_by(func.max(Conversation.CreatedAt).desc(), func.max(Conversation.ConvID).desc()).offset(offset).limit(limit).all()
    ids = {id_ for row in rows for id_ in (row.first_id, row.last_id)}
    turns = {row.ConvID: row for row in base.filter(Conversation.ConvID.in_(ids)).all()} if ids else {}
    items = []
    for row in rows:
        first, last = turns[row.first_id], turns[row.last_id]
        items.append({"id": row.session_id, "user_message": first.UserMessage, "ai_response": last.AIResponse,
                      "topic": last.Topic, "turn_count": row.turn_count,
                      "created_at": row.updated_at.replace(tzinfo=timezone.utc).isoformat()})
    return {"history": items, "total": total, "has_more": offset + len(items) < total}


@router.get("/conversations/{session_id}")
def conversation(session_id: str, offset: int = Query(default=0, ge=0),
                 limit: int = Query(default=100, ge=1, le=100),
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = visible_rows(db, user.UserID).filter(session_key() == session_id)
    total = query.count()
    if not total:
        raise HTTPException(404, "Không tìm thấy hội thoại.")
    rows = query.order_by(Conversation.CreatedAt, Conversation.ConvID).offset(offset).limit(limit).all()
    return {"session_id": session_id, "turns": [serialize_turn(row) for row in rows],
            "total": total, "has_more": offset + len(rows) < total}


@router.delete("/conversations/{session_id}")
def delete_conversation(session_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    count = visible_rows(db, user.UserID).filter(session_key() == session_id).update(
        {Conversation.deleted_at: datetime.utcnow()}, synchronize_session=False)
    if not count:
        raise HTTPException(404, "Không tìm thấy hội thoại.")
    db.commit()
    return {"deleted_count": count}


@router.get("/documents")
def documents(user: User = Depends(get_current_user)):
    try:
        return {"documents": rag_service.documents(user.UserID)}
    except Exception:
        logger.exception("Cannot read document library")
        raise HTTPException(503, "Kho tài liệu chưa sẵn sàng. Kiểm tra cấu hình Chroma.")


@router.get("/knowledge-status")
def knowledge_status(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    """Read-only evidence for the most recent scheduled knowledge ingestion."""
    latest = db.query(DataIngestionLog).filter(
        DataIngestionLog.JobName == "knowledge_agent"
    ).order_by(DataIngestionLog.StartedAt.desc(), DataIngestionLog.LogID.desc()).first()
    approved = db.query(func.count(KnowledgeDocument.DocumentKey)).filter(
        KnowledgeDocument.Status == "approved"
    ).scalar() or 0
    try:
        indexed_documents = len(rag_service.documents(0))
        indexed_chunks = rag_service.collection(0).count()
        index_status = "ready"
    except Exception:
        logger.exception("Cannot read shared knowledge status")
        indexed_documents = None
        indexed_chunks = None
        index_status = "unavailable"
    last_run = None if latest is None else {
        "status": latest.Status,
        "records_fetched": latest.RecordsFetched,
        "records_saved": latest.RecordsSaved,
        "started_at": utc_iso(latest.StartedAt),
        "finished_at": utc_iso(latest.FinishedAt),
        "has_error": bool(latest.ErrorMessage),
        "error": latest.ErrorMessage[:1000] if latest.ErrorMessage else None,
    }

    latest_job = db.query(KnowledgeDiscoveryJob).filter(
        KnowledgeDiscoveryJob.UserID == _user.UserID
    ).order_by(KnowledgeDiscoveryJob.CreatedAt.desc(), KnowledgeDiscoveryJob.JobID.desc()).first()
    latest_query_discovery = knowledge_discovery_service.get(
        db, latest_job.JobID, user_id=_user.UserID
    ) if latest_job else None
    return {
        "enabled": settings.KNOWLEDGE_AGENT_ENABLED,
        "schedule_hour": settings.KNOWLEDGE_AGENT_HOUR,
        "configured_sources": len(configured_sources()) + db.query(KnowledgeSourceCandidate).filter(
            KnowledgeSourceCandidate.Status == "approved"
        ).count(),
        "approved_documents": approved,
        "indexed_documents": indexed_documents,
        "indexed_chunks": indexed_chunks,
        "index_status": index_status,
        "last_run": last_run,
        "latest_query_discovery": latest_query_discovery,
    }


@router.post("/knowledge-discovery")
def start_knowledge_discovery(
    request: KnowledgeDiscoveryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start a query-triggered source search immediately, without the nightly schedule."""
    question = request.question.strip()
    if not question:
        raise HTTPException(422, "Chủ đề tìm kiếm không được để trống.")

    crop = (request.crop or extract_crop_from_message(question) or "").strip() or None
    region = (request.region or extract_region_from_message(question) or "").strip() or None
    intent = (request.intent or classify_user_intent(question) or "general_question").strip()
    return knowledge_discovery_service.enqueue(
        db,
        question=question,
        user_id=user.UserID,
        intent=intent,
        crop=crop,
        region=region,
        force=True,
    )


@router.get("/knowledge-documents")
def knowledge_documents(
    status: str = Query("approved", pattern="^(all|approved|pending|rejected|failed|superseded)$"),
    q: str = Query("", max_length=200),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List shared documents with their database and vector-index state."""
    latest = db.query(DataIngestionLog).filter(
        DataIngestionLog.JobName == "knowledge_agent"
    ).order_by(DataIngestionLog.StartedAt.desc(), DataIngestionLog.LogID.desc()).first()

    query = db.query(KnowledgeDocument)
    if status != "all":
        query = query.filter(KnowledgeDocument.Status == status)
    search = q.strip()
    if search:
        like = f"%{search}%"
        query = query.filter(or_(
            KnowledgeDocument.Title.ilike(like),
            KnowledgeDocument.SourceName.ilike(like),
            KnowledgeDocument.Crop.ilike(like),
            KnowledgeDocument.Region.ilike(like),
        ))
    rows = query.order_by(KnowledgeDocument.FetchedAt.desc(), KnowledgeDocument.DocumentKey.desc()).limit(limit).all()

    try:
        indexed_rows = rag_service.documents(0)
        indexed_by_id = {item["id"]: item for item in indexed_rows}
        indexed_chunks = rag_service.collection(0).count()
        index_status = "ready"
    except Exception:
        logger.exception("Cannot read shared document index")
        indexed_by_id = {}
        indexed_chunks = None
        index_status = "unavailable"

    counts = {key: 0 for key in ("approved", "pending", "rejected", "failed", "superseded")}
    for row_status, count in db.query(
        KnowledgeDocument.Status, func.count(KnowledgeDocument.DocumentKey)
    ).group_by(KnowledgeDocument.Status).all():
        counts[row_status] = count

    documents = []
    for row in rows:
        indexed = indexed_by_id.get(row.RagDocumentID)
        quality_report = parse_quality_report(row.QualityReport)
        quality_checks = quality_rejection_details(row.QualityReport) if row.Status in {"rejected", "failed"} else []
        documents.append({
            "id": row.DocumentKey,
            "title": row.Title or "Tài liệu chưa có tiêu đề",
            "source_name": row.SourceName,
            "source_url": row.CanonicalURL,
            "published_at": utc_iso(row.PublishedAt),
            "fetched_at": utc_iso(row.FetchedAt),
            "approved_at": utc_iso(row.ApprovedAt),
            "region": row.Region,
            "crop": row.Crop,
            "version": row.Version,
            "status": row.Status,
            "quality_score": row.QualityScore,
            "quality_report": quality_report or None,
            "quality_checks": quality_checks,
            "rejection_reason": "; ".join(quality_checks) if quality_checks else None,
            "indexed": indexed is not None,
            "chunks": indexed["chunks"] if indexed else 0,
            "is_new": bool(latest and row.FetchedAt and row.FetchedAt >= latest.StartedAt),
        })

    return {
        "documents": documents,
        "summary": {
            **counts,
            "total": sum(counts.values()),
            "indexed_documents": len(indexed_by_id),
            "indexed_chunks": indexed_chunks,
            "index_status": index_status,
            "last_run_started_at": utc_iso(latest.StartedAt) if latest else None,
            "last_run_status": latest.Status if latest else None,
        },
    }


@router.get("/knowledge-source-candidates")
def knowledge_source_candidates(
    status: str = Query("pending", pattern="^(pending|approved|rejected|all)$"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Show discovered sources; only administrators can approve them."""
    return {"candidates": source_discovery_service.list_candidates(db, status=status, limit=limit)}


@router.get("/knowledge-discovery/{job_id}")
def knowledge_discovery_status(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return progress for a discovery job created by this user."""
    job = knowledge_discovery_service.get(db, job_id, user_id=user.UserID)
    if not job:
        raise HTTPException(404, "Không tìm thấy tác vụ tìm nguồn.")
    return {"job": job}


@router.post("/documents")
def upload_document(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    try:
        return rag_service.ingest(user.UserID, file.filename or "document.txt", file.file.read(MAX_UPLOAD_BYTES + 1))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except Exception:
        logger.exception("Document ingestion failed")
        raise HTTPException(503, "Chưa nạp được tài liệu. Kiểm tra Chroma và model embedding trong Ollama rồi thử lại.")
    finally:
        file.file.close()


@router.delete("/documents/{document_id}")
def delete_document(document_id: str, user: User = Depends(get_current_user)):
    try:
        rag_service.delete(user.UserID, document_id)
        return {"deleted": True}
    except Exception:
        logger.exception("Document deletion failed")
        raise HTTPException(503, "Chưa xóa được tài liệu. Hãy thử lại.")
