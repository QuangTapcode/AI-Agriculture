from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, Unicode, UnicodeText
from sqlalchemy.orm import synonym
from sqlalchemy.sql import func

from ..core.database import Base


class MarketSuggestion(Base):
    __tablename__ = "MarketSuggestions"

    SuggestionID = Column("SuggestionID", Integer, primary_key=True, index=True)
    UserID = Column("UserID", Integer, ForeignKey("Users.UserID"), nullable=False, index=True)
    CropID = Column("CropID", Integer, ForeignKey("CropTypes.CropID"), nullable=False, index=True)
    Region = Column("Region", Unicode(100), nullable=False)
    QuantityKg = Column("QuantityKg", Float, nullable=False)
    QualityGrade = Column("QualityGrade", Unicode(20), nullable=True)
    RecommendedChannel = Column("RecommendedChannel", Unicode(50), nullable=True)
    EstimatedProfit = Column("EstimatedProfit", Float, nullable=True)
    Reason = Column("Reason", UnicodeText, nullable=True)
    Warning = Column("Warning", UnicodeText, nullable=True)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("SuggestionID")
    user_id = synonym("UserID")
    crop_id = synonym("CropID")
    region = synonym("Region")
    quantity_kg = synonym("QuantityKg")
    quality_grade = synonym("QualityGrade")
    recommended_channel = synonym("RecommendedChannel")
    estimated_profit = synonym("EstimatedProfit")
    reason = synonym("Reason")
    warning = synonym("Warning")
    created_at = synonym("CreatedAt")


class MarketChannel(Base):
    __tablename__ = "MarketChannels"

    ChannelID = Column("ChannelID", Integer, primary_key=True, index=True)
    ChannelCode = Column("ChannelCode", Unicode(50), nullable=False, unique=True, index=True)
    ChannelName = Column("ChannelName", Unicode(100), nullable=False)
    CommissionRate = Column("CommissionRate", Float, nullable=False, default=0)
    MinQuantityKg = Column("MinQuantityKg", Float, nullable=False, default=0)
    RequiredQualityRank = Column("RequiredQualityRank", Integer, nullable=False, default=1)
    PriceFactor = Column("PriceFactor", Float, nullable=False, default=1)
    Region = Column("Region", Unicode(100), nullable=True, index=True)
    IsActive = Column("IsActive", Integer, nullable=False, default=1)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)
    UpdatedAt = Column("UpdatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("ChannelID")
    channel_code = synonym("ChannelCode")
    channel_name = synonym("ChannelName")
    commission_rate = synonym("CommissionRate")
    min_quantity_kg = synonym("MinQuantityKg")
    required_quality_rank = synonym("RequiredQualityRank")
    price_factor = synonym("PriceFactor")
    region = synonym("Region")
    is_active = synonym("IsActive")
    created_at = synonym("CreatedAt")
    updated_at = synonym("UpdatedAt")


class RetailPriceSnapshot(Base):
    __tablename__ = "RetailPriceSnapshots"

    SnapshotID = Column("SnapshotID", Integer, primary_key=True, index=True)
    CropName = Column("CropName", Unicode(100), nullable=False, index=True)
    ProductName = Column("ProductName", Unicode(300), nullable=True)
    Region = Column("Region", Unicode(100), nullable=True, index=True)
    RetailerName = Column("RetailerName", Unicode(120), nullable=False, index=True)
    PricePerKg = Column("PricePerKg", Float, nullable=False)
    Unit = Column("Unit", Unicode(50), nullable=True, default="VND/kg")
    SourceName = Column("SourceName", Unicode(120), nullable=False)
    SourceURL = Column("SourceURL", Unicode(500), nullable=False)
    ObservedAt = Column("ObservedAt", DateTime, nullable=True)
    FetchedAt = Column("FetchedAt", DateTime, nullable=False)
    IsRealtime = Column("IsRealtime", Boolean, nullable=False, default=False)
    IsMock = Column("IsMock", Boolean, nullable=False, default=False)
    Metadata = Column("Metadata", JSON, nullable=True)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("SnapshotID")
    crop_name = synonym("CropName")
    product_name = synonym("ProductName")
    region = synonym("Region")
    retailer_name = synonym("RetailerName")
    price_per_kg = synonym("PricePerKg")
    unit = synonym("Unit")
    source_name = synonym("SourceName")
    source_url = synonym("SourceURL")
    observed_at = synonym("ObservedAt")
    fetched_at = synonym("FetchedAt")
    is_realtime = synonym("IsRealtime")
    is_mock = synonym("IsMock")
    metadata_json = synonym("Metadata")
    created_at = synonym("CreatedAt")


class MarketAnalysisResult(Base):
    __tablename__ = "MarketAnalysisResults"

    AnalysisID = Column("AnalysisID", Integer, primary_key=True, index=True)
    CropName = Column("CropName", Unicode(100), nullable=False, index=True)
    Region = Column("Region", Unicode(100), nullable=False, index=True)
    PayloadJSON = Column("PayloadJSON", UnicodeText, nullable=False)
    SourceName = Column("SourceName", Unicode(120), nullable=False)
    SourceURL = Column("SourceURL", Unicode(500), nullable=False)
    FetchedAt = Column("FetchedAt", DateTime, nullable=False, index=True)
    IsRealtime = Column("IsRealtime", Boolean, nullable=False, default=False)
    IsMock = Column("IsMock", Boolean, nullable=False, default=False)
    Status = Column("Status", Unicode(30), nullable=False, default="ready")
    ErrorMessage = Column("ErrorMessage", UnicodeText, nullable=True)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("AnalysisID")
    crop_name = synonym("CropName")
    region = synonym("Region")
    payload_json = synonym("PayloadJSON")
    source_name = synonym("SourceName")
    source_url = synonym("SourceURL")
    fetched_at = synonym("FetchedAt")
    is_realtime = synonym("IsRealtime")
    is_mock = synonym("IsMock")
    status = synonym("Status")
    error_message = synonym("ErrorMessage")
    created_at = synonym("CreatedAt")
