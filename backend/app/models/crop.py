from sqlalchemy import Column, DateTime, Float, Integer, Unicode, UnicodeText
from sqlalchemy.orm import synonym
from sqlalchemy.sql import func

from ..core.database import Base


class Crop(Base):
    __tablename__ = "CropTypes"

    CropID = Column("CropID", Integer, primary_key=True, index=True)
    CropName = Column("CropName", Unicode(100), nullable=False, unique=True, index=True)
    CropNameEN = Column("CropNameEN", Unicode(100), nullable=True)
    Category = Column("Category", Unicode(50), nullable=False, default="Khac")  # khop CHECK constraint: khong dau
    GrowthDurationDays = Column("GrowthDurationDays", Integer, nullable=True)
    HarvestSeason = Column("HarvestSeason", Unicode(100), nullable=True)
    TypicalPriceMin = Column("TypicalPriceMin", Float, nullable=True)
    TypicalPriceMax = Column("TypicalPriceMax", Float, nullable=True)
    Description = Column("Description", UnicodeText, nullable=True)
    ImageURL = Column("ImageURL", Unicode(500), nullable=True)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("CropID")
    name = synonym("CropName")
    crop_name = synonym("CropName")
    crop_name_en = synonym("CropNameEN")
    category = synonym("Category")
    growth_duration_days = synonym("GrowthDurationDays")
    avg_growth_days = synonym("GrowthDurationDays")
    harvest_season = synonym("HarvestSeason")
    typical_price_min = synonym("TypicalPriceMin")
    typical_price_max = synonym("TypicalPriceMax")
    description = synonym("Description")
    image_url = synonym("ImageURL")
    created_at = synonym("CreatedAt")

    @property
    def default_unit(self) -> str:
        return "kg"


CropType = Crop
