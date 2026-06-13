from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.response import api_response
from app.core.database import get_db
from app.schemas.price_schema import (
    PriceForecastRequest,
    PricingSuggestRequest,
)
from app.services.pricing_service import pricing_service

router = APIRouter(prefix="/api/pricing", tags=["pricing"])


class PriceLookupRequest(BaseModel):
    crop_name: str = Field(..., min_length=1)
    region: str = Field(..., min_length=1)
    quality_grade: str = "grade_1"
    force_refresh: bool = False


class PricingEngineRequest(BaseModel):
    crop: str | None = None
    crop_name: str | None = None
    region: str = "Ha Noi"
    quantity: float = Field(default=1, gt=0)
    quality_grade: str = "grade_1"
    days: int = Field(default=7, ge=1, le=30)

    @property
    def resolved_crop(self) -> str:
        crop_name = (self.crop_name or "").strip()
        if crop_name:
            return crop_name
        crop = (self.crop or "").strip()
        return crop or "lua"


class PricingRefreshRequest(BaseModel):
    crop_name: str = Field(..., min_length=1)
    region: str = Field(..., min_length=1)
    quality_grade: str = "grade_1"


@router.get("/current")
async def get_current_price_query(
    crop_name: str = Query(..., min_length=1),
    region: str = Query(..., min_length=1),
    quality_grade: str = Query(default="grade_1"),
    force_refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    data = pricing_service.get_current_price(
        db,
        crop_name,
        region,
        quality_grade,
        include_weather=False,
        force_refresh=force_refresh,
    )
    return api_response(
        data,
        source=data.get("source", "database"),
        source_name=data.get("source_name"),
        is_mock=data.get("is_mock", False),
        is_realtime=data.get("source") == "realtime_api",
        cache_status=data.get("cache_status", "from_db"),
        last_updated=data.get("last_updated"),
        fetched_at=data.get("fetched_at"),
        confidence=data.get("confidence", 0.0),
        message="OK" if not data.get("is_mock") else "Dữ liệu mô phỏng",
    )


@router.post("/current")
async def get_current_price(request: PriceLookupRequest, db: Session = Depends(get_db)):
    data = pricing_service.get_current_price(
        db,
        request.crop_name,
        request.region,
        request.quality_grade,
        include_weather=False,
        force_refresh=request.force_refresh,
    )
    return api_response(
        data,
        source=data.get("source", "database"),
        source_name=data.get("source_name"),
        is_mock=data.get("is_mock", False),
        is_realtime=data.get("source") == "realtime_api",
        cache_status=data.get("cache_status", "from_db"),
        last_updated=data.get("last_updated"),
        fetched_at=data.get("fetched_at"),
        confidence=data.get("confidence", 0.0),
        message="OK" if not data.get("is_mock") else "Dữ liệu mô phỏng",
    )


@router.post("/refresh")
async def refresh_price(request: PricingRefreshRequest, db: Session = Depends(get_db)):
    data = pricing_service.refresh_current_price(
        db,
        request.crop_name,
        request.region,
        request.quality_grade,
    )
    return api_response(
        data,
        source=data.get("source", "database"),
        source_name=data.get("source_name"),
        is_mock=data.get("is_mock", False),
        is_realtime=data.get("source") == "realtime_api",
        cache_status=data.get("cache_status", "from_db"),
        last_updated=data.get("last_updated"),
        fetched_at=data.get("fetched_at"),
        confidence=data.get("confidence", 0.0),
        message=data.get("message", "Đã làm mới giá"),
    )


@router.post("/suggest")
async def suggest_price(request: PricingSuggestRequest, db: Session = Depends(get_db)):
    data = pricing_service.suggest_price(db, request)
    return api_response(
        data,
        source=data.get("source", "database"),
        source_name=data.get("source_name"),
        is_mock=data.get("is_mock", False),
        cache_status=data.get("cache_status", "computed"),
        last_updated=data.get("last_updated"),
        fetched_at=data.get("fetched_at"),
        confidence=data.get("confidence", 0.72),
    )


@router.post("/forecast")
async def forecast_price(request: PriceForecastRequest, db: Session = Depends(get_db)):
    data = pricing_service.forecast_price_with_db(db, request.crop_name, request.region, request.days)
    return api_response(
        data,
        source=data.get("source", "cache"),
        source_name=data.get("source_name"),
        is_mock=data.get("is_mock", False),
        cache_status=data.get("cache_status", "miss"),
        last_updated=data.get("last_updated"),
        fetched_at=data.get("fetched_at"),
        confidence=data.get("confidence", 0.0),
    )


@router.get("/history")
async def get_price_history_query(
    crop_name: str = Query(..., min_length=1),
    region: str = Query(..., min_length=1),
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    history = pricing_service.get_price_history(db, crop_name, region, days)
    is_mock = any(item.get("is_mock") for item in history)
    data = {
        "crop_name": crop_name,
        "crop": crop_name,
        "region": region,
        "history": history,
        "source_type": "mock" if is_mock else "database",
    }
    return api_response(
        data,
        source="mock" if is_mock else "database",
        source_name="PriceHistory DB" if not is_mock else "Pricing demo history",
        is_mock=is_mock,
        cache_status="mock" if is_mock else "from_db",
        confidence=0.68 if not is_mock else 0.42,
    )


@router.get("/history/{crop_name}/{region}")
async def get_price_history(crop_name: str, region: str, days: int = Query(default=30, ge=1, le=365), db: Session = Depends(get_db)):
    history = pricing_service.get_price_history(db, crop_name, region, days)
    is_mock = any(item.get("is_mock") for item in history)
    data = {
        "crop_name": crop_name,
        "crop": crop_name,
        "region": region,
        "history": history,
        "source_type": "mock" if is_mock else "database",
    }
    return api_response(
        data,
        source="mock" if is_mock else "database",
        source_name="PriceHistory DB" if not is_mock else "Pricing demo history",
        is_mock=is_mock,
        cache_status="mock" if is_mock else "from_db",
        confidence=0.68 if not is_mock else 0.42,
    )


@router.get("/weather-forecast")
async def weather_price_forecast(
    crop_name: str,
    region: str,
    quality_grade: str = "grade_1",
    db: Session = Depends(get_db),
):
    from app.services.weather_pricing_service import get_weather_adjusted_pricing

    current = pricing_service.get_current_price(
        db, crop_name, region, quality_grade, include_weather=False
    )
    if current.get("_api_error"):
        return api_response(current)
    base_price = float(current["current_price"])
    weather_info = get_weather_adjusted_pricing(db, crop_name, region, base_price)

    data = {
        "crop_name": crop_name,
        "region": region,
        "quality_grade": quality_grade,
        "base_price": round(base_price, 2),
        "weather_adjusted_price": round(weather_info["adjusted_price"], 2),
        "weather_factor": weather_info["weather_factor"],
        "price_change_pct": weather_info["price_change_pct"],
        "weather_summary": weather_info["weather_summary"],
        "weather_explanation": weather_info["weather_explanation"],
        "crop_category": weather_info["crop_category"],
        "forecast_days": weather_info["forecast_days"],
        "forecast": weather_info["forecast"],
        "unit": "VNĐ/kg",
    }
    return api_response(
        data,
        source="ai_generated",
        source_name="Weather Pricing Engine",
        confidence=0.72,
        cache_status="computed",
    )


@router.get("/compare-regions/{crop_name}")
async def compare_regions(crop_name: str, region: str = "Ha Noi", db: Session = Depends(get_db)):
    data = pricing_service.compare_regions(db, crop_name, region)
    return api_response(
        data,
        source=data.get("source", "database"),
        source_name=data.get("source_name"),
        is_mock=data.get("is_mock", False),
        cache_status=data.get("cache_status", "from_db"),
        last_updated=data.get("last_updated"),
        confidence=data.get("confidence", 0.0),
    )


@router.post("/compare-regions")
async def compare_regions_post(request: PricingEngineRequest, db: Session = Depends(get_db)):
    data = pricing_service.compare_regions(db, request.resolved_crop, request.region)
    return api_response(
        data,
        source=data.get("source", "database"),
        source_name=data.get("source_name"),
        is_mock=data.get("is_mock", False),
        cache_status=data.get("cache_status", "from_db"),
        last_updated=data.get("last_updated"),
        confidence=data.get("confidence", 0.0),
    )


@router.post("/ai-explanation")
async def ai_pricing_explanation(request: PricingEngineRequest, db: Session = Depends(get_db)):
    data = pricing_service.explain_pricing(db, request.resolved_crop, request.region, request.quality_grade)
    return api_response(
        data,
        source="ai_generated" if not data.get("is_mock") else "mock",
        source_name=data.get("source_name"),
        is_mock=data.get("is_mock", False),
        cache_status=data.get("cache_status", "computed"),
        last_updated=data.get("last_updated"),
        confidence=data.get("confidence", 0.0),
    )


@router.post("/engine")
async def pricing_engine(request: PricingEngineRequest, db: Session = Depends(get_db)):
    data = pricing_service.build_pricing_engine(
        db,
        crop_name=request.resolved_crop,
        region=request.region,
        quantity=request.quantity,
        quality_grade=request.quality_grade,
        days=request.days,
    )
    return api_response(
        data,
        source="ai_generated" if not data.get("is_mock") else "mock",
        source_name=data.get("source_name"),
        is_mock=data.get("is_mock", False),
        cache_status=data.get("cache_status", "computed"),
        last_updated=data.get("last_updated"),
        confidence=data.get("confidence", 0.0),
    )
