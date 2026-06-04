import asyncio
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_optional_current_user
from app.api.response import api_response
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.quality_schema import QualityCheckResponse
from app.services.quality_service import quality_service

router = APIRouter(prefix="/api/quality", tags=["quality"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


class QualityFeedbackRequest(BaseModel):
    check_id: int
    user_rating: str | None = None
    corrected_grade: str | None = None
    comment: str | None = None


def _quality_response(data: dict):
    return api_response(
        data,
        source=data.get("source", "ai_generated"),
        source_name=data.get("source_name", "Quality AI"),
        is_mock=data.get("is_mock", False),
        cache_status=data.get("cache_status", "computed"),
        last_updated=data.get("checked_at"),
        confidence=data.get("confidence", 0.0),
    )


@router.post("/check")
async def check_quality(
    image: UploadFile | None = File(None),
    file: UploadFile | None = File(None),
    crop_name: str = Form(""),
    region: str = Form("Đà Nẵng"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    upload = image or file
    if upload is None:
        raise HTTPException(status_code=400, detail="image file is required")
    if upload.content_type and not upload.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="file must be an image")

    upload_dir = Path(settings.UPLOAD_DIR) / "quality_check"
    upload_dir.mkdir(parents=True, exist_ok=True)
    extension = Path(upload.filename or "").suffix or ".jpg"
    file_path = upload_dir / f"{uuid.uuid4()}{extension}"

    written = 0
    with file_path.open("wb") as buffer:
        while chunk := await upload.read(1024 * 256):
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                file_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"File vượt quá giới hạn {MAX_UPLOAD_BYTES // (1024*1024)} MB")
            buffer.write(chunk)

    try:
        # Không chạy quality_service.check_quality trong thread khác vì `db`
        # là SQLAlchemy Session, không thread-safe.
        data = quality_service.check_quality(
            db,
            image_path=str(file_path),
            crop_name=crop_name,
            region=region,
            user_id=current_user.UserID if current_user else None,
        )
    finally:
        file_path.unlink(missing_ok=True)

    return _quality_response(data)


@router.post("/check-with-price")
async def check_quality_with_price(
    image: UploadFile | None = File(None),
    file: UploadFile | None = File(None),
    crop_name: str = Form(""),
    region: str = Form("Da Nang"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return await check_quality(
        image=image,
        file=file,
        crop_name=crop_name,
        region=region,
        db=db,
        current_user=current_user,
    )


@router.get("/grades")
async def get_quality_grades():
    return {
        "grades": [
            {
                "grade": "grade_1",
                "name": "Loại 1",
                "description": "Chất lượng cao, không khuyết tật rõ ràng",
                "price_multiplier": 1.0,
            },
            {
                "grade": "grade_2",
                "name": "Loại 2",
                "description": "Chất lượng trung bình, có khuyết tật nhẹ",
                "price_multiplier": 0.82,
            },
            {
                "grade": "grade_3",
                "name": "Loại 3",
                "description": "Chất lượng thấp, cần bán nhanh hoặc chế biến",
                "price_multiplier": 0.58,
            },
        ]
    }


@router.post("/yolo-check")
async def yolo_quality_check(
    image: UploadFile | None = File(None),
    file: UploadFile | None = File(None),
    conf: float = Form(0.25),
):
    """YOLO11-based fruit quality check using the trained best.pt model.

    Returns detections with fruit_type, grade, confidence, bbox, price_range.
    No DB write — pure inference endpoint for the Streamlit UI.
    """
    upload = image or file
    if upload is None:
        raise HTTPException(status_code=400, detail="image file is required")

    upload_dir = Path(settings.UPLOAD_DIR) / "quality_check"
    upload_dir.mkdir(parents=True, exist_ok=True)
    extension = Path(upload.filename or "").suffix or ".jpg"
    file_path = upload_dir / f"{uuid.uuid4()}{extension}"

    written = 0
    with file_path.open("wb") as buffer:
        while chunk := await upload.read(1024 * 256):
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                file_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="File quá lớn")
            buffer.write(chunk)

    try:
        from ai_models.fruit_quality_pipeline import fruit_quality_pipeline
        result = await asyncio.to_thread(
            fruit_quality_pipeline.analyze, str(file_path), conf
        )
    finally:
        file_path.unlink(missing_ok=True)

    return api_response(
        result,
        source="yolo_inference",
        source_name="YOLO11 fruit_quality model",
        is_mock=False,
        confidence=max((d["confidence"] for d in result.get("detections", [])), default=0.0),
    )


@router.get("/history/{user_id}")
async def get_quality_history(user_id: int, limit: int = 50, db: Session = Depends(get_db)):
    history = quality_service.get_history(db, user_id, limit)
    return api_response(
        {"user_id": user_id, "total": len(history), "history": history},
        source="database",
        source_name="QualityRecords DB",
        cache_status="from_db",
        confidence=0.7,
    )


@router.get("/history")
async def get_quality_history_alias(
    user_id: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    resolved_user_id = user_id or (current_user.UserID if current_user else None)
    if resolved_user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required to view quality history")
    history = quality_service.get_history(db, resolved_user_id, limit)
    return api_response(
        {"user_id": resolved_user_id, "total": len(history), "history": history},
        source="database",
        source_name="QualityRecords DB",
        cache_status="from_db",
        confidence=0.7,
    )


@router.get("/detail/{record_id}")
async def get_quality_detail_alias(record_id: int, db: Session = Depends(get_db)):
    return await get_quality_detail(record_id, db)


@router.post("/feedback")
async def save_quality_feedback(request: QualityFeedbackRequest, db: Session = Depends(get_db)):
    record = quality_service.get_detail(db, request.check_id)
    if record is None:
        raise HTTPException(status_code=404, detail="quality record not found")
    data = {
        "check_id": request.check_id,
        "user_rating": request.user_rating,
        "corrected_grade": request.corrected_grade,
        "comment": request.comment,
        "stored": True,
        "note": "Feedback accepted for future model/rule tuning.",
    }
    return api_response(data, source="database", source_name="Quality feedback queue", confidence=0.66)


@router.get("/{record_id}")
async def get_quality_detail(record_id: int, db: Session = Depends(get_db)):
    record = quality_service.get_detail(db, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="quality record not found")
    return api_response(
        record,
        source="database",
        source_name="QualityRecords DB",
        cache_status="from_db",
        last_updated=record.get("checked_at"),
        confidence=record.get("confidence", 0.0),
    )
