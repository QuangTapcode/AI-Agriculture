from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, Unicode, UnicodeText
from sqlalchemy.orm import synonym
from sqlalchemy.sql import func

from ..core.database import Base


class HarvestSchedule(Base):
    __tablename__ = "HarvestSchedule"

    ScheduleID = Column("ScheduleID", Integer, primary_key=True, index=True)
    UserID = Column("UserID", Integer, ForeignKey("Users.UserID"), nullable=False, index=True)
    CropID = Column("CropID", Integer, ForeignKey("CropTypes.CropID"), nullable=False, index=True)
    PlantingDate = Column("PlantingDate", Date, nullable=False)
    AreaSize = Column("AreaSize", Float, nullable=True)
    Region = Column("Region", Unicode(100), nullable=False)
    ExpectedHarvestDate = Column("ExpectedHarvestDate", Date, nullable=True)
    ActualHarvestDate = Column("ActualHarvestDate", Date, nullable=True)
    EstimatedYieldKg = Column("EstimatedYieldKg", Float, nullable=True)
    ActualYieldKg = Column("ActualYieldKg", Float, nullable=True)
    FertilizerUsed = Column("FertilizerUsed", Unicode(200), nullable=True)
    PesticideUsed = Column("PesticideUsed", Unicode(200), nullable=True)
    Status = Column("Status", Unicode(50), nullable=False, default="Dang trong")
    Notes = Column("Notes", UnicodeText, nullable=True)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)
    UpdatedAt = Column("UpdatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("ScheduleID")
    user_id = synonym("UserID")
    crop_id = synonym("CropID")
    planting_date = synonym("PlantingDate")
    area_size = synonym("AreaSize")
    region = synonym("Region")
    expected_harvest_date = synonym("ExpectedHarvestDate")
    actual_harvest_date = synonym("ActualHarvestDate")
    estimated_yield_kg = synonym("EstimatedYieldKg")
    actual_yield_kg = synonym("ActualYieldKg")
    status = synonym("Status")
    notes = synonym("Notes")
    created_at = synonym("CreatedAt")
    updated_at = synonym("UpdatedAt")


class HarvestForecast(Base):
    __tablename__ = "HarvestForecastResults"

    ForecastID = Column("ForecastID", Integer, primary_key=True, index=True)
    ScheduleID = Column("ScheduleID", Integer, ForeignKey("HarvestSchedule.ScheduleID"), nullable=False, index=True)
    ExpectedHarvestDate = Column("ExpectedHarvestDate", Date, nullable=False)
    ConfidenceScore = Column("ConfidenceScore", Float, nullable=True)
    WeatherWarning = Column("WeatherWarning", UnicodeText, nullable=True)
    LaborRecommendation = Column("LaborRecommendation", UnicodeText, nullable=True)
    TransportRecommendation = Column("TransportRecommendation", UnicodeText, nullable=True)
    ModelVersion = Column("ModelVersion", Unicode(50), nullable=True, default="mock-v1")
    GeneratedAt = Column("GeneratedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("ForecastID")
    schedule_id = synonym("ScheduleID")
    expected_harvest_date = synonym("ExpectedHarvestDate")
    confidence = synonym("ConfidenceScore")
    confidence_score = synonym("ConfidenceScore")
    warning = synonym("WeatherWarning")
    weather_warning = synonym("WeatherWarning")
    recommendation = synonym("LaborRecommendation")
    labor_recommendation = synonym("LaborRecommendation")
    transport_recommendation = synonym("TransportRecommendation")
    model_version = synonym("ModelVersion")
    created_at = synonym("GeneratedAt")
    generated_at = synonym("GeneratedAt")
