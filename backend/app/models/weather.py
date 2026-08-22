from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, Unicode, UnicodeText, UniqueConstraint
from sqlalchemy.orm import synonym
from sqlalchemy.sql import func

from ..core.database import Base


class WeatherData(Base):
    __tablename__ = "WeatherData"

    WeatherID = Column("WeatherID", Integer, primary_key=True, index=True)
    Region = Column("Region", Unicode(100), nullable=False, index=True)
    RecordDate = Column("RecordDate", Date, nullable=False, index=True)
    TempMin = Column("TempMin", Float, nullable=True)
    TempMax = Column("TempMax", Float, nullable=True)
    Humidity = Column("Humidity", Float, nullable=True)
    Rainfall = Column("Rainfall", Float, nullable=True)
    SunshineHours = Column("SunshineHours", Float, nullable=True)
    WeatherDesc = Column("WeatherDesc", Unicode(100), nullable=True)
    Latitude = Column("Latitude", Float, nullable=True)
    Longitude = Column("Longitude", Float, nullable=True)
    WindSpeed = Column("WindSpeed", Float, nullable=True)
    UVIndex = Column("UVIndex", Float, nullable=True)
    Pressure = Column("Pressure", Float, nullable=True)
    WeatherCode = Column("WeatherCode", Integer, nullable=True)
    SourceName = Column("SourceName", Unicode(100), nullable=True)
    SourceURL = Column("SourceURL", Unicode(500), nullable=True)
    SourceUpdatedAt = Column("SourceUpdatedAt", DateTime, nullable=True)
    FetchedAt = Column("FetchedAt", DateTime, nullable=True)
    IsRealtime = Column("IsRealtime", Boolean, nullable=True, default=False)
    IsMock = Column("IsMock", Boolean, nullable=True, default=False)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("WeatherID")
    region = synonym("Region")
    record_date = synonym("RecordDate")
    temp_min = synonym("TempMin")
    temp_max = synonym("TempMax")
    humidity = synonym("Humidity")
    rainfall = synonym("Rainfall")
    sunshine_hours = synonym("SunshineHours")
    weather_desc = synonym("WeatherDesc")
    latitude = synonym("Latitude")
    longitude = synonym("Longitude")
    wind_speed = synonym("WindSpeed")
    uv_index = synonym("UVIndex")
    pressure = synonym("Pressure")
    weather_code = synonym("WeatherCode")
    source_name = synonym("SourceName")
    source_url = synonym("SourceURL")
    source_updated_at = synonym("SourceUpdatedAt")
    fetched_at = synonym("FetchedAt")
    is_realtime = synonym("IsRealtime")
    is_mock = synonym("IsMock")
    created_at = synonym("CreatedAt")

    @property
    def temperature(self) -> float | None:
        if self.TempMin is None and self.TempMax is None:
            return None
        if self.TempMin is None:
            return self.TempMax
        if self.TempMax is None:
            return self.TempMin
        return (self.TempMin + self.TempMax) / 2

    @property
    def condition(self) -> str | None:
        return self.WeatherDesc

    @property
    def recorded_at(self):
        return self.CreatedAt


class WeatherLocation(Base):
    __tablename__ = "WeatherLocations"

    LocationID = Column("LocationID", Integer, primary_key=True, index=True)
    Region = Column("Region", Unicode(100), nullable=False, unique=True, index=True)
    Province = Column("Province", Unicode(100), nullable=True, index=True)
    District = Column("District", Unicode(100), nullable=True)
    Ward = Column("Ward", Unicode(100), nullable=True)
    Latitude = Column("Latitude", Float, nullable=True)
    Longitude = Column("Longitude", Float, nullable=True)
    IsDefault = Column("IsDefault", Boolean, nullable=False, default=False)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("LocationID")
    region = synonym("Region")
    province = synonym("Province")
    district = synonym("District")
    ward = synonym("Ward")
    latitude = synonym("Latitude")
    longitude = synonym("Longitude")
    is_default = synonym("IsDefault")
    created_at = synonym("CreatedAt")


class WeatherObservation(Base):
    __tablename__ = "WeatherObservations"

    ObservationID = Column("ObservationID", Integer, primary_key=True, index=True)
    LocationID = Column("LocationID", Integer, ForeignKey("WeatherLocations.LocationID"), nullable=True, index=True)
    Region = Column("Region", Unicode(100), nullable=False, index=True)
    ObservedAt = Column("ObservedAt", DateTime, nullable=False, index=True)
    Temperature = Column("Temperature", Float, nullable=True)
    Humidity = Column("Humidity", Float, nullable=True)
    Rainfall = Column("Rainfall", Float, nullable=True)
    WindSpeed = Column("WindSpeed", Float, nullable=True)
    UVIndex = Column("UVIndex", Float, nullable=True)
    Pressure = Column("Pressure", Float, nullable=True)
    WeatherCode = Column("WeatherCode", Integer, nullable=True)
    WeatherDesc = Column("WeatherDesc", Unicode(100), nullable=True)
    SourceName = Column("SourceName", Unicode(100), nullable=True)
    SourceURL = Column("SourceURL", Unicode(500), nullable=True)
    SourceUpdatedAt = Column("SourceUpdatedAt", DateTime, nullable=True)
    FetchedAt = Column("FetchedAt", DateTime, nullable=True)
    IsRealtime = Column("IsRealtime", Boolean, nullable=True, default=False)
    IsMock = Column("IsMock", Boolean, nullable=True, default=False)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("ObservationID")
    location_id = synonym("LocationID")
    region = synonym("Region")
    observed_at = synonym("ObservedAt")
    temperature = synonym("Temperature")
    humidity = synonym("Humidity")
    rainfall = synonym("Rainfall")
    wind_speed = synonym("WindSpeed")
    uv_index = synonym("UVIndex")
    pressure = synonym("Pressure")
    weather_code = synonym("WeatherCode")
    weather_desc = synonym("WeatherDesc")
    source_name = synonym("SourceName")
    source_url = synonym("SourceURL")
    source_updated_at = synonym("SourceUpdatedAt")
    fetched_at = synonym("FetchedAt")
    is_realtime = synonym("IsRealtime")
    is_mock = synonym("IsMock")
    created_at = synonym("CreatedAt")


class WeatherForecast(Base):
    __tablename__ = "WeatherForecasts"
    __table_args__ = (
        UniqueConstraint("Region", "ForecastDate", "ForecastType", "ForecastAt", name="UQ_WeatherForecast_Slot"),
    )

    ForecastID = Column("ForecastID", Integer, primary_key=True, index=True)
    Region = Column("Region", Unicode(100), nullable=False, index=True)
    ForecastDate = Column("ForecastDate", Date, nullable=False, index=True)
    ForecastAt = Column("ForecastAt", DateTime, nullable=True, index=True)
    ForecastType = Column("ForecastType", Unicode(20), nullable=False, default="daily")
    TempMin = Column("TempMin", Float, nullable=True)
    TempMax = Column("TempMax", Float, nullable=True)
    Temperature = Column("Temperature", Float, nullable=True)
    ApparentTemperature = Column("ApparentTemperature", Float, nullable=True)
    Humidity = Column("Humidity", Float, nullable=True)
    DewPoint = Column("DewPoint", Float, nullable=True)
    Rainfall = Column("Rainfall", Float, nullable=True)
    RainProbability = Column("RainProbability", Float, nullable=True)
    WindSpeed = Column("WindSpeed", Float, nullable=True)
    WindGusts = Column("WindGusts", Float, nullable=True)
    UVIndex = Column("UVIndex", Float, nullable=True)
    Visibility = Column("Visibility", Float, nullable=True)
    CloudCover = Column("CloudCover", Float, nullable=True)
    Pressure = Column("Pressure", Float, nullable=True)
    WeatherCode = Column("WeatherCode", Integer, nullable=True)
    WeatherDesc = Column("WeatherDesc", Unicode(100), nullable=True)
    Recommendation = Column("Recommendation", UnicodeText, nullable=True)
    SourceName = Column("SourceName", Unicode(100), nullable=True)
    SourceURL = Column("SourceURL", Unicode(500), nullable=True)
    SourceUpdatedAt = Column("SourceUpdatedAt", DateTime, nullable=True)
    FetchedAt = Column("FetchedAt", DateTime, nullable=True)
    IsRealtime = Column("IsRealtime", Boolean, nullable=True, default=False)
    IsMock = Column("IsMock", Boolean, nullable=True, default=False)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("ForecastID")
    region = synonym("Region")
    forecast_date = synonym("ForecastDate")
    forecast_at = synonym("ForecastAt")
    forecast_type = synonym("ForecastType")
    temp_min = synonym("TempMin")
    temp_max = synonym("TempMax")
    temperature = synonym("Temperature")
    humidity = synonym("Humidity")
    rainfall = synonym("Rainfall")
    apparent_temperature = synonym("ApparentTemperature")
    dew_point = synonym("DewPoint")
    rain_probability = synonym("RainProbability")
    wind_speed = synonym("WindSpeed")
    wind_gusts = synonym("WindGusts")
    uv_index = synonym("UVIndex")
    visibility = synonym("Visibility")
    cloud_cover = synonym("CloudCover")
    pressure = synonym("Pressure")
    weather_code = synonym("WeatherCode")
    weather_desc = synonym("WeatherDesc")
    recommendation = synonym("Recommendation")
    source_name = synonym("SourceName")
    source_url = synonym("SourceURL")
    source_updated_at = synonym("SourceUpdatedAt")
    fetched_at = synonym("FetchedAt")
    is_realtime = synonym("IsRealtime")
    is_mock = synonym("IsMock")
    created_at = synonym("CreatedAt")


class WeatherAlert(Base):
    __tablename__ = "WeatherAlerts"

    AlertID = Column("AlertID", Integer, primary_key=True, index=True)
    UserID = Column("UserID", Integer, ForeignKey("Users.UserID"), nullable=True, index=True)
    Region = Column("Region", Unicode(100), nullable=False, index=True)
    AlertType = Column("AlertType", Unicode(50), nullable=False, index=True)
    Severity = Column("Severity", Unicode(20), nullable=False, default="medium", index=True)
    Title = Column("Title", Unicode(200), nullable=False)
    Message = Column("Message", UnicodeText, nullable=False)
    Recommendation = Column("Recommendation", UnicodeText, nullable=True)
    TriggerValue = Column("TriggerValue", Float, nullable=True)
    TriggerUnit = Column("TriggerUnit", Unicode(30), nullable=True)
    ForecastDate = Column("ForecastDate", Date, nullable=True, index=True)
    DedupKey = Column("DedupKey", Unicode(255), nullable=True, unique=True, index=True)
    Source = Column("Source", Unicode(50), nullable=False, default="rule")
    NotifyMethod = Column("NotifyMethod", Unicode(20), nullable=False, default="Email")
    Receiver = Column("Receiver", Unicode(255), nullable=True)
    LastTriggered = Column("LastTriggered", DateTime, nullable=True)
    LastValue = Column("LastValue", Float, nullable=True)
    IsActive = Column("IsActive", Boolean, nullable=False, default=True)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("AlertID")
    user_id = synonym("UserID")
    region = synonym("Region")
    alert_type = synonym("AlertType")
    severity = synonym("Severity")
    title = synonym("Title")
    message = synonym("Message")
    recommendation = synonym("Recommendation")
    trigger_value = synonym("TriggerValue")
    trigger_unit = synonym("TriggerUnit")
    forecast_date = synonym("ForecastDate")
    dedup_key = synonym("DedupKey")
    source = synonym("Source")
    notify_method = synonym("NotifyMethod")
    receiver = synonym("Receiver")
    last_triggered_at = synonym("LastTriggered")
    last_value = synonym("LastValue")
    is_active = synonym("IsActive")
    created_at = synonym("CreatedAt")


class FarmPlot(Base):
    __tablename__ = "FarmPlots"

    PlotID = Column("PlotID", Integer, primary_key=True, index=True)
    UserID = Column("UserID", Integer, ForeignKey("Users.UserID"), nullable=True, index=True)
    PlotName = Column("PlotName", Unicode(150), nullable=False, default="Thua ruong")
    Region = Column("Region", Unicode(100), nullable=False, index=True)
    Latitude = Column("Latitude", Float, nullable=True)
    Longitude = Column("Longitude", Float, nullable=True)
    CropName = Column("CropName", Unicode(100), nullable=True, index=True)
    GrowthStage = Column("GrowthStage", Unicode(100), nullable=True)
    AreaHectare = Column("AreaHectare", Float, nullable=True)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("PlotID")
    user_id = synonym("UserID")
    plot_name = synonym("PlotName")
    region = synonym("Region")
    latitude = synonym("Latitude")
    longitude = synonym("Longitude")
    crop_name = synonym("CropName")
    growth_stage = synonym("GrowthStage")
    area_hectare = synonym("AreaHectare")
    created_at = synonym("CreatedAt")


class CropWeatherRule(Base):
    __tablename__ = "CropWeatherRules"

    RuleID = Column("RuleID", Integer, primary_key=True, index=True)
    CropName = Column("CropName", Unicode(100), nullable=False, index=True)
    GrowthStage = Column("GrowthStage", Unicode(100), nullable=True, index=True)
    RuleType = Column("RuleType", Unicode(50), nullable=False)
    ConditionField = Column("ConditionField", Unicode(50), nullable=False)
    Operator = Column("Operator", Unicode(10), nullable=False)
    ThresholdValue = Column("ThresholdValue", Float, nullable=False)
    Unit = Column("Unit", Unicode(30), nullable=True)
    Severity = Column("Severity", Unicode(20), nullable=False, default="medium")
    Message = Column("Message", UnicodeText, nullable=False)
    Recommendation = Column("Recommendation", UnicodeText, nullable=True)
    IsActive = Column("IsActive", Boolean, nullable=False, default=True)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("RuleID")
    crop_name = synonym("CropName")
    growth_stage = synonym("GrowthStage")
    rule_type = synonym("RuleType")
    condition_field = synonym("ConditionField")
    operator = synonym("Operator")
    threshold_value = synonym("ThresholdValue")
    unit = synonym("Unit")
    severity = synonym("Severity")
    message = synonym("Message")
    recommendation = synonym("Recommendation")
    is_active = synonym("IsActive")
    created_at = synonym("CreatedAt")


class WeatherRecommendation(Base):
    __tablename__ = "WeatherRecommendations"

    RecommendationID = Column("RecommendationID", Integer, primary_key=True, index=True)
    Region = Column("Region", Unicode(100), nullable=False, index=True)
    CropName = Column("CropName", Unicode(100), nullable=True, index=True)
    GrowthStage = Column("GrowthStage", Unicode(100), nullable=True)
    ActionType = Column("ActionType", Unicode(50), nullable=False, index=True)
    Decision = Column("Decision", Unicode(100), nullable=False)
    Reason = Column("Reason", UnicodeText, nullable=False)
    Timing = Column("Timing", Unicode(100), nullable=True)
    Priority = Column("Priority", Unicode(20), nullable=False, default="medium")
    Source = Column("Source", Unicode(50), nullable=False, default="rule")
    RecommendationDate = Column("RecommendationDate", Date, nullable=False, index=True)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("RecommendationID")
    region = synonym("Region")
    crop_name = synonym("CropName")
    growth_stage = synonym("GrowthStage")
    action_type = synonym("ActionType")
    decision = synonym("Decision")
    reason = synonym("Reason")
    timing = synonym("Timing")
    priority = synonym("Priority")
    source = synonym("Source")
    recommendation_date = synonym("RecommendationDate")
    created_at = synonym("CreatedAt")
