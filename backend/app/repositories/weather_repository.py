from datetime import date, datetime, timedelta

from sqlalchemy import asc, desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.weather import WeatherData, WeatherForecast


def upsert_weather_cache(
    db: Session,
    *,
    region: str,
    record_date: date,
    temp_min: float | None = None,
    temp_max: float | None = None,
    rainfall: float | None = None,
    temperature: float | None = None,
    humidity: float | None = None,
    condition: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    wind_speed: float | None = None,
    uv_index: float | None = None,
    pressure: float | None = None,
    weather_code: int | None = None,
    source_name: str | None = "Open-Meteo",
    source_url: str | None = "https://api.open-meteo.com/v1/forecast",
    source_updated_at=None,
    fetched_at=None,
    is_realtime: bool = False,
    is_mock: bool = False,
) -> WeatherData | None:
    try:
        row = (
            db.query(WeatherData)
            .filter(WeatherData.Region == region, WeatherData.RecordDate == record_date)
            .first()
        )
        if row is None:
            row = WeatherData(Region=region, RecordDate=record_date)
            db.add(row)
        # Chỉ ba luồng gọi hàm này, và hai trong số đó (dự báo ngày, dự báo
        # giờ) không có nhiệt độ đo được. Gán thẳng sẽ xoá trắng số đo mà
        # luồng realtime vừa ghi, và trang thời tiết rơi lại về trung bình ngày.
        if temperature is not None:
            row.Temperature = temperature
        row.TempMin = temp_min
        row.TempMax = temp_max
        row.Rainfall = rainfall
        row.Humidity = humidity
        row.WeatherDesc = condition
        row.Latitude = latitude
        row.Longitude = longitude
        row.WindSpeed = wind_speed
        row.UVIndex = uv_index
        row.Pressure = pressure
        row.WeatherCode = weather_code
        row.SourceName = source_name
        row.SourceURL = source_url
        # Hàng của hôm nay có thể đang giữ quan trắc thật. Luồng dự báo gọi lại
        # cùng hàng này để hâm nóng cache nhưng không mang theo nhiệt độ, và mốc
        # của nó là giờ chạy chứ không phải giờ đo — ghi đè sẽ khiến tuổi dữ
        # liệu luôn báo 0 phút dù số đo đã cũ.
        if temperature is not None or row.Temperature is None:
            row.SourceUpdatedAt = source_updated_at
        row.FetchedAt = fetched_at
        row.IsRealtime = is_realtime
        row.IsMock = is_mock
        db.commit()
        db.refresh(row)
        return row
    except SQLAlchemyError:
        db.rollback()
        return None


def create_weather_data(db: Session, **data) -> WeatherData:
    temperature = data.pop("temperature", None)
    condition = data.pop("condition", None)
    weather = WeatherData(
        Region=data["region"],
        RecordDate=date.today(),
        TempMin=temperature,
        TempMax=temperature,
        Rainfall=data.get("rainfall"),
        Humidity=data.get("humidity"),
        WeatherDesc=condition,
    )
    try:
        db.add(weather)
        db.commit()
        db.refresh(weather)
    except SQLAlchemyError:
        db.rollback()
    return weather


def get_latest_weather(db: Session, region: str) -> WeatherData | None:
    try:
        today = date.today()
        return (
            db.query(WeatherData)
            .filter(
                WeatherData.Region == region,
                WeatherData.RecordDate <= today,
                WeatherData.SourceURL.isnot(None),
                WeatherData.SourceName.isnot(None),
                WeatherData.FetchedAt.isnot(None),
                WeatherData.IsMock == False,  # noqa: E712
            )
            .order_by(desc(WeatherData.RecordDate), desc(WeatherData.CreatedAt))
            .first()
        )
    except SQLAlchemyError:
        db.rollback()
        return None


def get_weather_forecast(db: Session, region: str, days: int = 7) -> list[WeatherData]:
    """Lấy dữ liệu thời tiết từ hôm nay đến N ngày tới từ WeatherData (Open-Meteo)."""
    try:
        today = date.today()
        until = today + timedelta(days=days)
        return (
            db.query(WeatherData)
            .filter(
                WeatherData.Region == region,
                WeatherData.RecordDate >= today,
                WeatherData.RecordDate <= until,
                WeatherData.SourceURL.isnot(None),
                WeatherData.SourceName.isnot(None),
                WeatherData.FetchedAt.isnot(None),
                WeatherData.IsMock == False,  # noqa: E712
            )
            .order_by(asc(WeatherData.RecordDate))
            .all()
        )
    except SQLAlchemyError:
        db.rollback()
        return []


def upsert_weather_forecast_cache(
    db: Session,
    *,
    region: str,
    forecast_date: date,
    forecast_type: str,
    forecast_at: datetime | None = None,
    temp_min: float | None = None,
    temp_max: float | None = None,
    temperature: float | None = None,
    apparent_temperature: float | None = None,
    humidity: float | None = None,
    dew_point: float | None = None,
    rainfall: float | None = None,
    rain_probability: float | None = None,
    wind_speed: float | None = None,
    wind_gusts: float | None = None,
    uv_index: float | None = None,
    visibility: float | None = None,
    cloud_cover: float | None = None,
    pressure: float | None = None,
    weather_code: int | None = None,
    condition: str | None = None,
    recommendation: str | None = None,
    source_name: str | None = "Open-Meteo",
    source_url: str | None = "https://api.open-meteo.com/v1/forecast",
    source_updated_at=None,
    fetched_at=None,
    is_realtime: bool = False,
    is_mock: bool = False,
) -> WeatherForecast | None:
    try:
        row = (
            db.query(WeatherForecast)
            .filter(
                WeatherForecast.Region == region,
                WeatherForecast.ForecastDate == forecast_date,
                WeatherForecast.ForecastType == forecast_type,
                WeatherForecast.ForecastAt == forecast_at,
            )
            .first()
        )
        if row is None:
            row = WeatherForecast(
                Region=region,
                ForecastDate=forecast_date,
                ForecastType=forecast_type,
                ForecastAt=forecast_at,
            )
            db.add(row)
        row.TempMin = temp_min
        row.TempMax = temp_max
        row.Temperature = temperature
        row.ApparentTemperature = apparent_temperature
        row.Humidity = humidity
        row.DewPoint = dew_point
        row.Rainfall = rainfall
        row.RainProbability = rain_probability
        row.WindSpeed = wind_speed
        row.WindGusts = wind_gusts
        row.UVIndex = uv_index
        row.Visibility = visibility
        row.CloudCover = cloud_cover
        row.Pressure = pressure
        row.WeatherCode = weather_code
        row.WeatherDesc = condition
        row.Recommendation = recommendation
        row.SourceName = source_name
        row.SourceURL = source_url
        row.SourceUpdatedAt = source_updated_at
        row.FetchedAt = fetched_at
        row.IsRealtime = is_realtime
        row.IsMock = is_mock
        db.commit()
        db.refresh(row)
        return row
    except SQLAlchemyError:
        db.rollback()
        return None


def get_cached_hourly_forecasts(db: Session, region: str, hours: int = 24) -> list[WeatherForecast]:
    try:
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        return (
            db.query(WeatherForecast)
            .filter(
                WeatherForecast.Region == region,
                WeatherForecast.ForecastType == "hourly",
                WeatherForecast.ForecastAt.isnot(None),
                WeatherForecast.ForecastAt >= now,
                WeatherForecast.SourceURL.isnot(None),
                WeatherForecast.SourceName.isnot(None),
                WeatherForecast.FetchedAt.isnot(None),
                WeatherForecast.IsMock == False,  # noqa: E712
            )
            .order_by(asc(WeatherForecast.ForecastAt))
            .limit(max(int(hours or 24), 1))
            .all()
        )
    except SQLAlchemyError:
        db.rollback()
        return []
