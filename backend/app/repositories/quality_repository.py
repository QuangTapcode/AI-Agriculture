import json
from datetime import datetime

from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.crop import Crop
from app.models.quality import QualityCheck
from app.repositories.common import ensure_crop, to_db_grade


def create_quality_check(
    db: Session,
    *,
    crop_name: str,
    region: str,
    image_path: str,
    quality_grade: str,
    disease_detected: bool,
    damage_level: str,
    suggested_price: float | None,
    confidence: float,
    user_id: int | None = None,
    suggested_price_min: float | None = None,
    suggested_price_max: float | None = None,
) -> QualityCheck:
    crop = ensure_crop(db, crop_name)

    detected_issues = {
        "disease_detected": disease_detected,
        "damage_level": damage_level,
    }

    if suggested_price_min is None and suggested_price is not None:
        suggested_price_min = round(float(suggested_price) * 0.92, 2)
    if suggested_price_max is None and suggested_price is not None:
        suggested_price_max = round(float(suggested_price) * 1.08, 2)

    quality_check = QualityCheck(
        CropID=crop.CropID,
        ImagePath=image_path,
        AIGrade=to_db_grade(quality_grade),
        ConfidenceScore=confidence,
        DetectedIssues=json.dumps(detected_issues, ensure_ascii=False),
        SuggestedPriceMin=suggested_price_min,
        SuggestedPriceMax=suggested_price_max,
        Recommendation="Kết quả kiểm định chất lượng.",
    )

    # Không fallback ngầm sang user đầu tiên/user giả.
    # Nếu request không có user hợp lệ thì chỉ trả object tạm để response vẫn đầy đủ,
    # nhưng không ghi DB sai chủ sở hữu.
    if user_id is None:
        quality_check.CheckDate = datetime.now()
        return quality_check

    try:
        from app.models.user import User

        user = db.query(User).filter(User.UserID == user_id).first()
        if user is None:
            quality_check.CheckDate = datetime.now()
            return quality_check

        quality_check.UserID = user.UserID
        db.add(quality_check)
        db.commit()
        db.refresh(quality_check)
    except SQLAlchemyError:
        db.rollback()
        quality_check.CheckDate = datetime.now()

    return quality_check


def get_quality_checks(
    db: Session,
    crop_name: str | None = None,
    region: str | None = None,
    limit: int = 20,
) -> list[QualityCheck]:
    try:
        query = db.query(QualityCheck)
        if crop_name:
            crop = ensure_crop(db, crop_name)
            query = query.filter(QualityCheck.CropID == crop.CropID)
        return query.order_by(desc(QualityCheck.CheckDate)).limit(limit).all()
    except SQLAlchemyError:
        db.rollback()
        return []


def get_quality_checks_by_user(db: Session, user_id: int, limit: int = 50) -> list[tuple[QualityCheck, Crop]]:
    try:
        return (
            db.query(QualityCheck, Crop)
            .join(Crop, Crop.CropID == QualityCheck.CropID)
            .filter(QualityCheck.UserID == user_id)
            .order_by(desc(QualityCheck.CheckDate))
            .limit(limit)
            .all()
        )
    except SQLAlchemyError:
        db.rollback()
        return []


def get_quality_check_by_id(db: Session, record_id: int) -> tuple[QualityCheck, Crop] | None:
    try:
        return (
            db.query(QualityCheck, Crop)
            .join(Crop, Crop.CropID == QualityCheck.CropID)
            .filter(QualityCheck.RecordID == record_id)
            .first()
        )
    except SQLAlchemyError:
        db.rollback()
        return None
