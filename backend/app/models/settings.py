from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Unicode
from sqlalchemy.orm import synonym
from sqlalchemy.sql import func

from ..core.database import Base


class UserSettings(Base):
    __tablename__ = "UserSettings"

    UserSettingID = Column("UserSettingID", Integer, primary_key=True, index=True)
    UserID = Column("UserID", Integer, ForeignKey("Users.UserID"), nullable=False, unique=True, index=True)
    Language = Column("Language", Unicode(10), nullable=False, default="vi")
    Unit = Column("Unit", Unicode(30), nullable=False, default="hectare")
    Theme = Column("Theme", Unicode(30), nullable=False, default="light")
    PriceAlerts = Column("PriceAlerts", Boolean, nullable=False, default=True)
    WeatherAlerts = Column("WeatherAlerts", Boolean, nullable=False, default=True)
    HarvestReminders = Column("HarvestReminders", Boolean, nullable=False, default=True)
    EmailChannel = Column("EmailChannel", Boolean, nullable=False, default=True)
    ZaloChannel = Column("ZaloChannel", Boolean, nullable=False, default=False)
    SmsChannel = Column("SmsChannel", Boolean, nullable=False, default=False)
    TwoFactorEnabled = Column("TwoFactorEnabled", Boolean, nullable=False, default=False)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)
    UpdatedAt = Column("UpdatedAt", DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    id = synonym("UserSettingID")
    user_id = synonym("UserID")
    language = synonym("Language")
    unit = synonym("Unit")
    theme = synonym("Theme")
    price_alerts = synonym("PriceAlerts")
    weather_alerts = synonym("WeatherAlerts")
    harvest_reminders = synonym("HarvestReminders")
    email_channel = synonym("EmailChannel")
    zalo_channel = synonym("ZaloChannel")
    sms_channel = synonym("SmsChannel")
    two_factor_enabled = synonym("TwoFactorEnabled")
    created_at = synonym("CreatedAt")
    updated_at = synonym("UpdatedAt")


class NotificationPreference(Base):
    __tablename__ = "NotificationPreferences"

    PreferenceID = Column("PreferenceID", Integer, primary_key=True, index=True)
    UserID = Column("UserID", Integer, ForeignKey("Users.UserID"), nullable=False, index=True)
    Channel = Column("Channel", Unicode(30), nullable=False)
    EventType = Column("EventType", Unicode(50), nullable=False)
    IsEnabled = Column("IsEnabled", Boolean, nullable=False, default=True)
    Receiver = Column("Receiver", Unicode(255), nullable=True)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)
    UpdatedAt = Column("UpdatedAt", DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    id = synonym("PreferenceID")
    user_id = synonym("UserID")
    channel = synonym("Channel")
    event_type = synonym("EventType")
    is_enabled = synonym("IsEnabled")
    receiver = synonym("Receiver")
    created_at = synonym("CreatedAt")
    updated_at = synonym("UpdatedAt")
