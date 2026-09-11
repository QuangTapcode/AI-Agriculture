import hashlib
import logging
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.integrations.email_client import email_client
from app.models.support_request import SupportRequest
from app.schemas.public_contact_schema import ContactRequestCreate


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/public", tags=["public"])


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _send_admin_email(request_id: int, payload: ContactRequestCreate) -> None:
    receiver = os.getenv("ADMIN_NOTIFICATION_EMAIL", "").strip()
    if not receiver or not settings.SMTP_HOST:
        return
    result = email_client.send(
        receiver,
        f"[AgriAI] Yêu cầu hỗ trợ #{request_id}",
        "\n".join(
            [
                f"Người gửi: {payload.name}",
                f"Email: {payload.email or '—'}",
                f"Điện thoại: {payload.phone or '—'}",
                f"Chủ đề: {payload.topic}",
                "",
                payload.message,
            ]
        ),
    )
    if result.get("status") != "sent":
        logger.warning("Admin email for support request %s failed: %s", request_id, result.get("error"))


@router.post("/contact-requests", status_code=status.HTTP_201_CREATED)
def create_contact_request(
    payload: ContactRequestCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    forwarded_ip = request.headers.get("CF-Connecting-IP") or request.headers.get("X-Forwarded-For")
    client_ip = (forwarded_ip or (request.client.host if request.client else "unknown")).split(",", 1)[0].strip()
    normalized_contact = (payload.email or payload.phone or "").lower().replace(" ", "")
    ip_hash = _digest(client_ip)
    contact_hash = _digest(normalized_contact)
    window_start = datetime.now() - timedelta(minutes=15)

    recent_count = (
        db.query(SupportRequest)
        .filter(
            SupportRequest.CreatedAt >= window_start,
            or_(SupportRequest.IpHash == ip_hash, SupportRequest.ContactHash == contact_hash),
        )
        .count()
    )
    if recent_count >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau 15 phút.",
        )

    support_request = SupportRequest(
        Name=payload.name,
        Email=payload.email,
        Phone=payload.phone,
        Topic=payload.topic,
        Message=payload.message,
        Status="new",
        IpHash=ip_hash,
        ContactHash=contact_hash,
        CreatedAt=datetime.now(),
    )
    db.add(support_request)
    db.commit()
    db.refresh(support_request)

    background_tasks.add_task(_send_admin_email, support_request.RequestID, payload)
    data = {
        "id": support_request.RequestID,
        "status": support_request.Status,
        "created_at": support_request.CreatedAt,
    }
    return {
        "success": True,
        "data": data,
        "source": "database",
        "source_name": "SupportRequests DB",
        "source_url": None,
        "is_realtime": False,
        "is_cache": False,
        "is_mock": False,
        "warning": None,
        "updated_at": support_request.CreatedAt,
        "message": "Yêu cầu hỗ trợ đã được lưu.",
        "meta": {
            "status": "database",
            "sourceName": "SupportRequests DB",
            "sourceUrl": None,
            "updatedAt": support_request.CreatedAt,
            "warning": None,
            "isMock": False,
        },
    }
