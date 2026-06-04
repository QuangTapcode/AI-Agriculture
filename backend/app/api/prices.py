from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.response import api_response
from app.core.database import get_db
from app.models.price import MarketPrice
from app.services.location_service import location_service
from app.services.pricing_service import pricing_service

router = APIRouter(prefix="/api/prices", tags=["Market Prices"])


class PriceResponse(BaseModel):
    price_id: int
    crop_name: str
    region: str
    price_per_kg: float
    quality_grade: str
    market_type: str
    source_name: Optional[str]
    price_date: date
    updated_at: datetime


def _serialize_dt(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _cache_status(updated_at: datetime | None) -> tuple[str, int | None]:
    if not updated_at:
        return "from_db", None
    age_seconds = max(int((datetime.now() - updated_at).total_seconds()), 0)
    if age_seconds <= int(timedelta(minutes=60).total_seconds()):
        return "cached", age_seconds
    return "from_db", age_seconds


def _resolve_crop_name(crop_name: str | None) -> str:
    return (crop_name or "lua").strip() or "lua"


@router.get("/current")
def get_current_price(
    crop_name: str | None = Query(default=None),
    crop_id: int | None = Query(default=None),
    region: str | None = Query(default=None),
    region_key: str | None = Query(default=None),
    force_refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    resolved_region = location_service.resolve_region(db, region_key or region)

    if crop_id:
        crop = db.query(MarketPrice).filter(MarketPrice.CropID == crop_id).first()
        resolved_crop_name = _resolve_crop_name(crop.Crop.CropName if crop and getattr(crop, "Crop", None) else crop_name)
    else:
        resolved_crop_name = _resolve_crop_name(crop_name)

    data = pricing_service.get_current_price(
        db,
        resolved_crop_name,
        resolved_region,
        include_weather=False,
        force_refresh=force_refresh,
    )
    data.update(
        {
            "crop_id": crop_id,
            "region_key": location_service.region_key(resolved_region),
            "price": float(data.get("current_price") or 0),
            "unit": "VNĐ/kg",
            "source_type": data.get("source", "database"),
        }
    )
    return api_response(
        data,
        source=data.get("source", "database"),
        source_name=data.get("source_name"),
        is_mock=data.get("is_mock", False),
        is_realtime=data.get("source") == "realtime",
        cache_status=data.get("cache_status", "from_db"),
        last_updated=data.get("last_updated"),
        fetched_at=data.get("fetched_at"),
        confidence=data.get("confidence", 0.0),
    )


@router.get("")
def get_latest_prices(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Lấy danh sách giá thị trường mới nhất. Hỗ trợ phân trang: ?limit=20&offset=40"""
    results = (
        db.query(MarketPrice)
        .order_by(MarketPrice.UpdatedAt.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    try:
        from app.models.crop import CropType
        crop_map = {
            item.CropID: item.CropName
            for item in db.query(CropType).all()
        }
    except Exception:
        crop_map = {}

    return [
        PriceResponse(
            price_id=price.PriceID,
            crop_name=crop_map.get(price.CropID, "Không rõ"),
            region=price.Region,
            price_per_kg=price.PricePerKg,
            quality_grade=price.QualityGrade,
            market_type=price.MarketType,
            source_name=price.SourceName,
            price_date=price.PriceDate,
            updated_at=price.UpdatedAt,
        )
        for price in results
    ]
