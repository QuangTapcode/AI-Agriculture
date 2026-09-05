from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, Unicode, UnicodeText
from sqlalchemy.orm import synonym
from sqlalchemy.sql import func

from ..core.database import Base


class Season(Base):
    __tablename__ = "Seasons"

    SeasonID = Column("SeasonID", Integer, primary_key=True, index=True)
    UserID = Column("UserID", Integer, ForeignKey("Users.UserID"), nullable=True, index=True)
    CropName = Column("CropName", Unicode(100), nullable=False, index=True)
    Region = Column("Region", Unicode(100), nullable=False, index=True)
    FarmName = Column("FarmName", Unicode(150), nullable=True)
    Area = Column("Area", Float, nullable=True)
    AreaUnit = Column("AreaUnit", Unicode(20), nullable=False, default="ha")
    StartDate = Column("StartDate", Date, nullable=False)
    ExpectedHarvestDate = Column("ExpectedHarvestDate", Date, nullable=False, index=True)
    ActualHarvestDate = Column("ActualHarvestDate", Date, nullable=True)
    Status = Column("Status", Unicode(30), nullable=False, default="active", index=True)
    HealthStatus = Column("HealthStatus", Unicode(30), nullable=False, default="good", index=True)
    Note = Column("Note", UnicodeText, nullable=True)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)
    UpdatedAt = Column("UpdatedAt", DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    id = synonym("SeasonID")
    user_id = synonym("UserID")
    crop_name = synonym("CropName")
    region = synonym("Region")
    farm_name = synonym("FarmName")
    area = synonym("Area")
    area_unit = synonym("AreaUnit")
    start_date = synonym("StartDate")
    expected_harvest_date = synonym("ExpectedHarvestDate")
    actual_harvest_date = synonym("ActualHarvestDate")
    status = synonym("Status")
    health_status = synonym("HealthStatus")
    note = synonym("Note")
    created_at = synonym("CreatedAt")
    updated_at = synonym("UpdatedAt")
