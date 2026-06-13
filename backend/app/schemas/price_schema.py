from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, constr


class PriceRequest(BaseModel):
    crop_name: constr(strip_whitespace=True, min_length=1) = Field(...)
    region: constr(strip_whitespace=True, min_length=1) = Field(...)
    quality_grade: str = "grade_1"


class PriceResponse(BaseModel):
    crop_name: str
    region: str
    current_price: Decimal
    quality_grade: str
    price_trend: str
    forecast_7days: list[dict] | None = None
    last_updated: datetime
    source_name: str | None = None
    source_url: str | None = None
    price_date: date | None = None
    cache_status: str = "unknown"
    is_mock: bool = False
    data_age_minutes: int | None = None


class PricingSuggestRequest(BaseModel):
    crop_name: constr(strip_whitespace=True, min_length=1) = Field(...)
    region: constr(strip_whitespace=True, min_length=1) = Field(...)
    quantity: float = Field(1, gt=0)
    quality_grade: str = "grade_1"


class PricingSuggestResponse(BaseModel):
    crop_name: str
    region: str
    quantity: float
    quality_grade: str
    min_price: Decimal
    suggested_price: Decimal
    max_price: Decimal
    unit: str = "VND/kg"
    nearby_region_prices: list[dict] = Field(default_factory=list)
    message: str
    source_name: str | None = None
    source_url: str | None = None
    price_date: date | None = None
    cache_status: str = "unknown"
    is_mock: bool = False
    last_updated: datetime | None = None


class PriceImportItem(BaseModel):
    crop_name: constr(strip_whitespace=True, min_length=1) = Field(...)
    region: constr(strip_whitespace=True, min_length=1) = Field(...)
    price: Decimal = Field(..., gt=0)
    unit: str = "VND/kg"
    quality_grade: str = "grade_1"
    source_name: str = "manual"
    source_url: str | None = None
    price_date: date | None = None
    market_type: str | None = None


class PriceImportRequest(BaseModel):
    records: list[PriceImportItem] = Field(..., min_length=1)


class PriceImportResponse(BaseModel):
    status: str
    records_received: int
    records_saved: int
    records_updated: int
    errors: list[str] = Field(default_factory=list)


class PriceForecastRequest(BaseModel):
    crop_name: constr(strip_whitespace=True, min_length=1) = Field(...)
    region: constr(strip_whitespace=True, min_length=1) = Field(...)
    days: int = Field(7, ge=1, le=30)


class PriceForecastResponse(BaseModel):
    crop_name: str
    region: str
    forecast_data: list[dict]
    trend: str
    recommendation: str


class PricePredictionRequest(BaseModel):
    crop_name: constr(strip_whitespace=True, min_length=1) = Field(...)
    region: constr(strip_whitespace=True, min_length=1) = Field(...)
    forecast_days: int = Field(7, ge=1, le=30)


class PredictedPrice(BaseModel):
    date: date
    predicted_price: Decimal
    min_price: Decimal
    max_price: Decimal


class PricePredictionResponse(BaseModel):
    crop_name: str
    region: str
    forecast_days: int
    trend: str
    best_selling_time: str
    predicted_prices: list[PredictedPrice]
    warning: str | None = None
