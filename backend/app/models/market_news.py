from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, Unicode, UnicodeText
from sqlalchemy.orm import synonym
from sqlalchemy.sql import func

from ..core.database import Base


class MarketNews(Base):
    __tablename__ = "MarketNews"

    NewsID = Column("NewsID", Integer, primary_key=True, index=True)
    Title = Column("Title", Unicode(300), nullable=False)
    Summary = Column("Summary", UnicodeText, nullable=True)
    Content = Column("Content", UnicodeText, nullable=True)
    URL = Column("URL", Unicode(500), nullable=True)
    SourceName = Column("SourceName", Unicode(100), nullable=True)
    SourceURL = Column("SourceURL", Unicode(500), nullable=True, unique=True)
    PublishedAt = Column("PublishedAt", DateTime, nullable=True, index=True)
    FetchedAt = Column("FetchedAt", DateTime, nullable=True)
    CropID = Column("CropID", Integer, ForeignKey("CropTypes.CropID"), nullable=True, index=True)
    Region = Column("Region", Unicode(100), nullable=True, index=True)
    CropTags = Column("CropTags", JSON, nullable=True)
    RegionTags = Column("RegionTags", JSON, nullable=True)
    Sentiment = Column("Sentiment", Unicode(20), nullable=True)
    ImpactLevel = Column("ImpactLevel", Unicode(20), nullable=True)
    ImpactScore = Column("ImpactScore", Float, nullable=True)
    IsRealtime = Column("IsRealtime", Boolean, nullable=True, default=False)
    IsMock = Column("IsMock", Boolean, nullable=True, default=False)
    Metadata = Column("Metadata", JSON, nullable=True)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("NewsID")
    title = synonym("Title")
    summary = synonym("Summary")
    content = synonym("Content")
    url = synonym("URL")
    source_name = synonym("SourceName")
    source_url = synonym("SourceURL")
    published_at = synonym("PublishedAt")
    fetched_at = synonym("FetchedAt")
    crop_id = synonym("CropID")
    region = synonym("Region")
    crop_tags = synonym("CropTags")
    region_tags = synonym("RegionTags")
    sentiment = synonym("Sentiment")
    impact_level = synonym("ImpactLevel")
    impact_score = synonym("ImpactScore")
    is_realtime = synonym("IsRealtime")
    is_mock = synonym("IsMock")
    metadata_json = synonym("Metadata")
    created_at = synonym("CreatedAt")
