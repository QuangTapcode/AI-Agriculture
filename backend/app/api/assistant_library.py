"""Authenticated document library and multi-turn conversation history."""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import String, case, cast, func, or_
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.conversation import AIConversation as Conversation
from app.models.ingestion import DataIngestionLog
from app.models.knowledge import KnowledgeDocument
from app.models.user import User
from app.services.knowledge_ingestion_service import configured_sources
from app.services.rag_service import MAX_UPLOAD_BYTES, rag_service

router = APIRouter(prefix="/api/ai-chat", tags=["ai-chat"])
logger = logging.getLogger(__name__)


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


def serialize_turn(row):
    context = snapshot(row)
    return {"id": row.ConvID, "user_message": row.UserMessage, "ai_response": row.AIResponse,
            "topic": row.Topic, "created_at": row.CreatedAt.replace(tzinfo=timezone.utc).isoformat(),
            "model": row.ModelName, "rag": context.get("rag", {"status": "not_used", "sources": []})}


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
    return {
        "enabled": settings.KNOWLEDGE_AGENT_ENABLED,
        "schedule_hour": settings.KNOWLEDGE_AGENT_HOUR,
        "configured_sources": len(configured_sources()),
        "approved_documents": approved,
        "indexed_documents": indexed_documents,
        "indexed_chunks": indexed_chunks,
        "index_status": index_status,
        "last_run": last_run,
    }


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
