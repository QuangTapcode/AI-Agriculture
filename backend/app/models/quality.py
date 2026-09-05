from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, Unicode, UnicodeText
from sqlalchemy.orm import synonym
from sqlalchemy.sql import func

from ..core.database import Base


class QualityCheck(Base):
    __tablename__ = "QualityRecords"

    RecordID = Column("RecordID", Integer, primary_key=True, index=True)
    ScheduleID = Column("ScheduleID", Integer, ForeignKey("HarvestSchedule.ScheduleID"), nullable=True)
    UserID = Column("UserID", Integer, ForeignKey("Users.UserID"), nullable=False, index=True)
    CropID = Column("CropID", Integer, ForeignKey("CropTypes.CropID"), nullable=False, index=True)
    ImagePath = Column("ImagePath", Unicode(500), nullable=False)
    AIGrade = Column("AIGrade", Unicode(20), nullable=True)
    ConfidenceScore = Column("ConfidenceScore", Float, nullable=True)
    DetectedIssues = Column("DetectedIssues", UnicodeText, nullable=True)
    DefectDetails = Column("DefectDetails", UnicodeText, nullable=True)
    ModelVersion = Column("ModelVersion", Unicode(100), nullable=True)
    InferenceTimeMs = Column("InferenceTimeMs", Float, nullable=True)
    ImageWidth = Column("ImageWidth", Integer, nullable=True)
    ImageHeight = Column("ImageHeight", Integer, nullable=True)
    SuggestedPriceSource = Column("SuggestedPriceSource", Unicode(100), nullable=True)
    SuggestedPriceMin = Column("SuggestedPriceMin", Float, nullable=True)
    SuggestedPriceMax = Column("SuggestedPriceMax", Float, nullable=True)
    Recommendation = Column("Recommendation", UnicodeText, nullable=True)
    CheckDate = Column("CheckDate", DateTime, server_default=func.now(), nullable=False)

    id = synonym("RecordID")
    schedule_id = synonym("ScheduleID")
    user_id = synonym("UserID")
    crop_id = synonym("CropID")
    image_path = synonym("ImagePath")
    quality_grade = synonym("AIGrade")
    ai_grade = synonym("AIGrade")
    confidence = synonym("ConfidenceScore")
    confidence_score = synonym("ConfidenceScore")
    detected_issues = synonym("DetectedIssues")
    defect_details = synonym("DefectDetails")
    model_version = synonym("ModelVersion")
    inference_time_ms = synonym("InferenceTimeMs")
    image_width = synonym("ImageWidth")
    image_height = synonym("ImageHeight")
    suggested_price_source = synonym("SuggestedPriceSource")
    suggested_price_min = synonym("SuggestedPriceMin")
    suggested_price_max = synonym("SuggestedPriceMax")
    recommendation = synonym("Recommendation")
    checked_at = synonym("CheckDate")
    check_date = synonym("CheckDate")


QualityRecord = QualityCheck
