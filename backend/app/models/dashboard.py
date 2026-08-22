from sqlalchemy import Boolean, Column, DateTime, Float, Integer, Unicode, UnicodeText
from sqlalchemy.orm import synonym
from sqlalchemy.sql import func

from ..core.database import Base


class DataSource(Base):
    __tablename__ = "DataSources"

    SourceID = Column("SourceID", Integer, primary_key=True, index=True)
    Name = Column("Name", Unicode(120), nullable=False, unique=True, index=True)
    Type = Column("Type", Unicode(50), nullable=False, default="api")
    URL = Column("URL", Unicode(500), nullable=True)
    RefreshInterval = Column("RefreshInterval", Integer, nullable=True)
    ReliabilityScore = Column("ReliabilityScore", Float, nullable=True)
    LastSuccessAt = Column("LastSuccessAt", DateTime, nullable=True)
    LastError = Column("LastError", UnicodeText, nullable=True)
    IsActive = Column("IsActive", Boolean, nullable=False, default=True)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("SourceID")
    name = synonym("Name")
    source_type = synonym("Type")
    url = synonym("URL")
    refresh_interval = synonym("RefreshInterval")
    reliability_score = synonym("ReliabilityScore")
    last_success_at = synonym("LastSuccessAt")
    last_error = synonym("LastError")
    is_active = synonym("IsActive")
    created_at = synonym("CreatedAt")


class RegionalPriceSnapshot(Base):
    __tablename__ = "RegionalPriceSnapshots"

    SnapshotID = Column("SnapshotID", Integer, primary_key=True, index=True)
    CropID = Column("CropID", Integer, nullable=False, index=True)
    Region = Column("Region", Unicode(100), nullable=False, index=True)
    AvgPrice = Column("AvgPrice", Float, nullable=False)
    MinPrice = Column("MinPrice", Float, nullable=True)
    MaxPrice = Column("MaxPrice", Float, nullable=True)
    PriceDate = Column("PriceDate", DateTime, nullable=False, index=True)
    SourceID = Column("SourceID", Integer, nullable=True, index=True)
    SourceName = Column("SourceName", Unicode(120), nullable=True)
    SourceURL = Column("SourceURL", Unicode(500), nullable=True)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("SnapshotID")
    crop_id = synonym("CropID")
    region = synonym("Region")
    avg_price = synonym("AvgPrice")
    min_price = synonym("MinPrice")
    max_price = synonym("MaxPrice")
    price_date = synonym("PriceDate")
    source_id = synonym("SourceID")
    source_name = synonym("SourceName")
    source_url = synonym("SourceURL")
    created_at = synonym("CreatedAt")


class AirQualityObservation(Base):
    __tablename__ = "AirQualityObservations"

    ObservationID = Column("ObservationID", Integer, primary_key=True, index=True)
    Region = Column("Region", Unicode(100), nullable=False, index=True)
    ObservedAt = Column("ObservedAt", DateTime, nullable=False, index=True)
    AQI = Column("AQI", Float, nullable=True)
    PM25 = Column("PM25", Float, nullable=True)
    PM10 = Column("PM10", Float, nullable=True)
    O3 = Column("O3", Float, nullable=True)
    RiskScore = Column("RiskScore", Float, nullable=True)
    SourceName = Column("SourceName", Unicode(100), nullable=True)
    SourceUpdatedAt = Column("SourceUpdatedAt", DateTime, nullable=True)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("ObservationID")
    region = synonym("Region")
    observed_at = synonym("ObservedAt")
    aqi = synonym("AQI")
    pm25 = synonym("PM25")
    pm10 = synonym("PM10")
    o3 = synonym("O3")
    risk_score = synonym("RiskScore")
    source_name = synonym("SourceName")
    source_updated_at = synonym("SourceUpdatedAt")
    created_at = synonym("CreatedAt")


class DashboardCache(Base):
    __tablename__ = "DashboardCache"

    CacheID = Column("CacheID", Integer, primary_key=True, index=True)
    Key = Column("Key", Unicode(255), nullable=False, unique=True, index=True)
    PayloadJSON = Column("PayloadJSON", UnicodeText, nullable=False)
    ExpiresAt = Column("ExpiresAt", DateTime, nullable=False, index=True)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("CacheID")
    key = synonym("Key")
    payload_json = synonym("PayloadJSON")
    expires_at = synonym("ExpiresAt")
    created_at = synonym("CreatedAt")
