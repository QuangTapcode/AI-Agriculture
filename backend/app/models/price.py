from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, Unicode, UniqueConstraint
from sqlalchemy.orm import synonym
from sqlalchemy.sql import func

from ..core.database import Base


class MarketPrice(Base):
    __tablename__ = "MarketPrices"
    __table_args__ = (
        # DB-level guard against concurrent duplicate upserts.
        # Mirrors the Python dedup key in bulk_upsert_market_prices.
        UniqueConstraint(
            "CropID", "Region", "PriceDate", "QualityGrade", "MarketType",
            name="uq_marketprices_upsert_key",
        ),
    )

    PriceID = Column("PriceID", Integer, primary_key=True, index=True)
    CropID = Column("CropID", Integer, ForeignKey("CropTypes.CropID"), nullable=False, index=True)
    Region = Column("Region", Unicode(100), nullable=False, index=True)
    PricePerKg = Column("PricePerKg", Float, nullable=False)
    QualityGrade = Column("QualityGrade", Unicode(20), nullable=False, default="Loai 1")
    MarketType = Column("MarketType", Unicode(50), nullable=False, default="Ban le")
    SourceURL = Column("SourceURL", Unicode(500), nullable=True)
    SourceName = Column("SourceName", Unicode(100), nullable=True)
    SourceType = Column("SourceType", Unicode(50), nullable=True)
    ObservedAt = Column("ObservedAt", DateTime, nullable=True)
    FetchedAt = Column("FetchedAt", DateTime, nullable=True)
    ConfidenceScore = Column("ConfidenceScore", Float, nullable=True)
    IsRealtime = Column("IsRealtime", Boolean, nullable=True, default=False)
    IsMock = Column("IsMock", Boolean, nullable=True, default=False)
    Metadata = Column("Metadata", JSON, nullable=True)
    PriceDate = Column("PriceDate", Date, nullable=False, index=True)
    UpdatedAt = Column("UpdatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("PriceID")
    crop_id = synonym("CropID")
    region = synonym("Region")
    price = synonym("PricePerKg")
    price_per_kg = synonym("PricePerKg")
    quality_grade = synonym("QualityGrade")
    market_type = synonym("MarketType")
    source_url = synonym("SourceURL")
    source_name = synonym("SourceName")
    source_type = synonym("SourceType")
    observed_at = synonym("ObservedAt")
    fetched_at = synonym("FetchedAt")
    confidence_score = synonym("ConfidenceScore")
    is_realtime = synonym("IsRealtime")
    is_mock = synonym("IsMock")
    metadata_json = synonym("Metadata")
    price_date = synonym("PriceDate")
    date = synonym("PriceDate")
    updated_at = synonym("UpdatedAt")
    collected_at = synonym("UpdatedAt")

    @property
    def unit(self) -> str:
        return "VND/kg"


class PriceHistory(Base):
    __tablename__ = "PriceHistory"
    __table_args__ = (
        # Composite index for the most common query pattern:
        # get_price_history filters CropID + Region + RecordDate together.
        Index("ix_pricehistory_crop_region_date", "CropID", "Region", "RecordDate"),
    )

    HistoryID = Column("HistoryID", Integer, primary_key=True, index=True)
    CropID = Column("CropID", Integer, ForeignKey("CropTypes.CropID"), nullable=False, index=True)
    Region = Column("Region", Unicode(100), nullable=False, index=True)
    AvgPrice = Column("AvgPrice", Float, nullable=False)
    MinPrice = Column("MinPrice", Float, nullable=True)
    MaxPrice = Column("MaxPrice", Float, nullable=True)
    Volume = Column("Volume", Float, nullable=True)
    RecordDate = Column("RecordDate", Date, nullable=False, index=True)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("HistoryID")
    crop_id = synonym("CropID")
    region = synonym("Region")
    avg_price = synonym("AvgPrice")
    min_price = synonym("MinPrice")
    max_price = synonym("MaxPrice")
    volume = synonym("Volume")
    record_date = synonym("RecordDate")
    date = synonym("RecordDate")
    created_at = synonym("CreatedAt")


class PriceForecastResult(Base):
    __tablename__ = "PriceForecastResults"

    ForecastID = Column("ForecastID", Integer, primary_key=True, index=True)
    CropID = Column("CropID", Integer, ForeignKey("CropTypes.CropID"), nullable=False, index=True)
    Region = Column("Region", Unicode(100), nullable=False, index=True)
    ForecastDate = Column("ForecastDate", Date, nullable=False, index=True)
    PredictedPrice = Column("PredictedPrice", Float, nullable=False)
    ConfidenceLow = Column("ConfidenceLow", Float, nullable=True)
    ConfidenceHigh = Column("ConfidenceHigh", Float, nullable=True)
    PriceTrend = Column("PriceTrend", Unicode(20), nullable=True)
    ModelVersion = Column("ModelVersion", Unicode(50), nullable=True, default="mock-v1")
    GeneratedAt = Column("GeneratedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("ForecastID")
    crop_id = synonym("CropID")
    region = synonym("Region")
    forecast_date = synonym("ForecastDate")
    predicted_price = synonym("PredictedPrice")
    confidence_low = synonym("ConfidenceLow")
    confidence_high = synonym("ConfidenceHigh")
    price_trend = synonym("PriceTrend")
    model_version = synonym("ModelVersion")
    generated_at = synonym("GeneratedAt")


class PricingRequest(Base):
    __tablename__ = "PricingRequests"

    RequestID = Column("RequestID", Integer, primary_key=True, index=True)
    UserID = Column("UserID", Integer, ForeignKey("Users.UserID"), nullable=True, index=True)
    CropID = Column("CropID", Integer, ForeignKey("CropTypes.CropID"), nullable=False, index=True)
    Region = Column("Region", Unicode(100), nullable=False)
    QuantityKg = Column("QuantityKg", Float, nullable=False)
    QualityGrade = Column("QualityGrade", Unicode(20), nullable=True)
    SuggestedPrice = Column("SuggestedPrice", Float, nullable=True)
    MinPrice = Column("MinPrice", Float, nullable=True)
    MaxPrice = Column("MaxPrice", Float, nullable=True)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("RequestID")
    user_id = synonym("UserID")
    crop_id = synonym("CropID")
    region = synonym("Region")
    quantity_kg = synonym("QuantityKg")
    quality_grade = synonym("QualityGrade")
    suggested_price = synonym("SuggestedPrice")
    min_price = synonym("MinPrice")
    max_price = synonym("MaxPrice")
    created_at = synonym("CreatedAt")
