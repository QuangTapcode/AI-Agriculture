from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import desc
from sqlalchemy.orm import Session

import logging

from app.core.config import settings
from app.core.real_data import (
    OFFICIAL_AGRI_SOURCE_NAME,
    OFFICIAL_PRICE_URL,
    age_minutes,
    cache_status_for,
    external_circuit_breaker,
    is_real_cache_record,
    realtime_error,
)
from app.core.redis_client import redis_client
from app.core.resilience import build_timeout, resilient_request
from app.integrations.thitruong_nongsan_price_client import thitruong_nongsan_price_client
from app.integrations.firecrawl_price_client import firecrawl_price_client
from app.models.crop import Crop
from app.models.price import MarketPrice
from app.repositories.common import ensure_crop, normalize_text
from app.repositories.ingestion_repository import finish_ingestion_log, start_ingestion_log
from app.repositories.price_repository import bulk_upsert_market_prices
from app.services.data_quality_service import clean_price_records, save_quarantine, warn_count_mismatch

logger = logging.getLogger(__name__)

# Tỷ giá USD → VND xấp xỉ (cập nhật định kỳ nếu cần)
_USD_VND_APPROX = 25_500.0
_JPY_VND_APPROX = 170.0

_GLOBAL_COMMODITIES = [
    {
        "symbol": "KC=F",
        "crop_name": "Cà phê Arabica",
        "source_label": "ICE Futures (CBOT)",
        "unit": "cents/lb",
        # cents/lb → USD/lb → VND/lb → VND/kg
        "to_vnd_kg": lambda p: round(p * 0.01 * _USD_VND_APPROX / 0.453592, -2),
    },
    {
        "symbol": "ZR=F",
        "crop_name": "Gạo thô (CBOT)",
        "source_label": "CBOT Rough Rice",
        "unit": "USD/cwt",
        # USD/cwt → VND/cwt → VND/kg  (1 cwt = 45.36 kg)
        "to_vnd_kg": lambda p: round(p * _USD_VND_APPROX / 45.36, -2),
    },
    {
        "symbol": "ZC=F",
        "crop_name": "Ngô",
        "source_label": "CBOT Corn Futures",
        "unit": "cents/bu",
        # cents/bu → USD/bu → VND/bu → VND/kg  (1 bushel corn ≈ 25.4 kg)
        "to_vnd_kg": lambda p: round(p * 0.01 * _USD_VND_APPROX / 25.4, -2),
    },
    {
        "symbol": "SB=F",
        "crop_name": "Đường thô",
        "source_label": "ICE Sugar #11",
        "unit": "cents/lb",
        "to_vnd_kg": lambda p: round(p * 0.01 * _USD_VND_APPROX / 0.453592, -2),
    },
]


class PriceAggregatorService:
    """Official agriculture-price gateway.

    The DB is treated strictly as cache for records fetched from the official
    source. Rows without source URL/name/fetched_at or rows marked mock are not
    considered valid public data.
    """

    def refresh_price_for_crop_region(self, db: Session, crop_name: str, region: str | None = None) -> dict:
        selected_crop = self._clean_crop(crop_name)
        selected_region = self._clean_region(region)
        try:
            # Fetch ALL regions for the crop — no region filter here.
            # Saving all-region data ensures _latest_db_price finds a fresh fallback
            # even when the requested region (e.g. "Ha Noi") has no government price.
            if settings.FIRECRAWL_ENABLED and settings.FIRECRAWL_API_KEY:
                raw = firecrawl_price_client.fetch_prices(selected_crop, region=None)
                source_key = "firecrawl_price"
            else:
                raw = thitruong_nongsan_price_client.fetch_prices(selected_crop, region=None)
                source_key = "thitruongnongsan_price"
            records, rejected = clean_price_records(raw)
            save_quarantine(rejected, source=source_key)
            result = bulk_upsert_market_prices(db, records)
            warn_count_mismatch(source_key, len(records), result)
            return {
                "status": "success" if records else "empty",
                "records_fetched": len(raw),
                "records_saved": result.get("records_saved", 0),
                "records_updated": result.get("records_updated", 0),
                "errors": list(result.get("errors") or []),
                "sources": [OFFICIAL_AGRI_SOURCE_NAME] if records else [],
                "source_name": OFFICIAL_AGRI_SOURCE_NAME,
                "source_url": OFFICIAL_PRICE_URL,
                "fetched_at": datetime.now(),
                "is_mock": False,
            }
        except Exception as exc:
            is_timeout = "timeout" in str(exc).lower() or "timed out" in str(exc).lower()
            if is_timeout:
                logger.warning(
                    "[PriceAggregator] timeout fetching %s/%s — serving DB cache",
                    crop_name, region,
                )
            return {
                "status": "stale_cache" if is_timeout else "failed",
                "records_fetched": 0,
                "records_saved": 0,
                "records_updated": 0,
                "errors": [str(exc)],
                "source_name": OFFICIAL_AGRI_SOURCE_NAME,
                "source_url": OFFICIAL_PRICE_URL,
                "is_mock": False,
                "warning": "Dữ liệu giá đang chậm (timeout). Hiển thị giá đã lưu." if is_timeout else None,
            }

    def get_best_current_price(
        self,
        db: Session,
        crop_name: str,
        region: str | None = None,
        force_refresh: bool = False,
    ) -> dict:
        selected_crop = self._clean_crop(crop_name)
        selected_region = self._clean_region(region)
        cached_row = self._latest_db_price(db, selected_crop, selected_region)

        if cached_row and not force_refresh:
            status = cache_status_for(cached_row.FetchedAt, "official_price")
            if status in {"fresh_cache", "stale_cache"}:
                warning = (
                    "Dữ liệu realtime chậm, đang hiển thị cache thật gần nhất."
                    if status == "stale_cache"
                    else None
                )
                return self._row_to_current_response(
                    db,
                    cached_row,
                    crop_name=selected_crop,
                    region=selected_region,
                    cache_status=status,
                    refresh_result=None,
                    warning=warning,
                )



        # Cào lại là việc của crawler nền, không phải của người đang xem trang.
        # Trước đây nhánh này chạy cả khi force_refresh=False: giá trong DB cũ
        # hơn STALE_TTL (24h) nên MỌI request đều rơi vào đây và tự đi cào —
        # một lần mở Bảng điều khiển sinh 13 lượt HTTP ra thitruongnongsan.gov.vn
        # và mất 8.3 giây. TOD0 §4: cache không được chặn request.
        if not force_refresh:
            if cached_row:
                status = cache_status_for(cached_row.FetchedAt, "official_price")
                return self._row_to_current_response(
                    db,
                    cached_row,
                    crop_name=selected_crop,
                    region=selected_region,
                    cache_status=status,
                    refresh_result=None,
                    warning=self._canh_bao_cache(status),
                )
            return self._no_realtime_price_response(
                crop_name=selected_crop,
                region=selected_region,
                refresh_result=None,
            )

        refresh_result = self.refresh_price_for_crop_region(db, selected_crop, selected_region)

        db.expire_all()
        live_row = self._latest_db_price(db, selected_crop, selected_region)
        if refresh_result.get("status") == "success" and live_row:
            return self._row_to_current_response(
                db,
                live_row,
                crop_name=selected_crop,
                region=selected_region,
                cache_status="live",
                refresh_result=refresh_result,
            )

        if cached_row:
            status = cache_status_for(cached_row.FetchedAt, "official_price")
            return self._row_to_current_response(
                db,
                cached_row,
                crop_name=selected_crop,
                region=selected_region,
                # Trước đây "miss" bị hạ cấp thành "stale_cache" ngay tại đây,
                # nên giá cũ 13 ngày vẫn được trình bày như giá dùng được.
                cache_status=status,
                refresh_result=refresh_result,
                warning=self._canh_bao_cache(status),
            )

        return self._no_realtime_price_response(
            crop_name=selected_crop,
            region=selected_region,
            refresh_result=refresh_result,
        )

    @staticmethod
    def _canh_bao_cache(status: str) -> str | None:
        if status == "stale_cache":
            return "Dữ liệu realtime chậm, đang hiển thị cache thật gần nhất."
        if status == "miss":
            return "Giá đã quá hạn theo dõi, chưa có số liệu mới từ nguồn."
        return None

    def get_global_reference_price(self, db: Session, crop_name: str) -> dict | None:
        refs = self.latest_global_references(db, limit=10)
        target = normalize_text(crop_name)
        for item in refs:
            if target in normalize_text(item.get("crop_name", "")):
                return item
        return None

    def latest_global_references(
        self, db: Session, limit: int = 8, cho_phep_cao: bool = False
    ) -> list[dict]:
        """Giá hàng hoá thế giới. Mặc định chỉ đọc Redis.

        Ba lượt gọi Yahoo Finance chạy ngay trong request mỗi khi Redis hết hạn
        (TTL 1 giờ) — người mở Bảng điều khiển đúng lúc đó phải trả tiền mạng
        thay cho crawler.
        """
        cache_key = "global_commodity_prices:v2"
        cached = redis_client.get(cache_key)
        if cached and isinstance(cached, list):
            return cached[:limit]
        if not cho_phep_cao:
            return []

        prices = self._fetch_yahoo_commodity_prices()
        if prices:
            redis_client.set(cache_key, prices, expire=3600)
        return prices[:limit]

    def _fetch_yahoo_commodity_prices(self) -> list[dict]:
        results = []
        now = datetime.now()
        timeout = build_timeout(total=8, connect=3, read=6)
        for item in _GLOBAL_COMMODITIES:
            symbol = item["symbol"]
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                response = resilient_request(
                    "GET",
                    url,
                    params={"interval": "1d", "range": "5d"},
                    headers={"User-Agent": "Mozilla/5.0 (compatible; AgriAI/1.0)"},
                    timeout=timeout,
                    retries=1,
                    service_name=f"yahoo_finance_{symbol}",
                )
                data = response.json()
                result_list = (data.get("chart") or {}).get("result") or []
                if not result_list:
                    continue
                quote_data = (result_list[0].get("indicators") or {}).get("quote") or [{}]
                closes = [c for c in (quote_data[0].get("close") or []) if c is not None]
                if not closes:
                    continue
                raw_price = closes[-1]
                price_vnd = item["to_vnd_kg"](raw_price)
                if price_vnd and price_vnd > 0:
                    results.append({
                        "crop_name": item["crop_name"],
                        "price": price_vnd,
                        "currency": "VND",
                        "unit": "kg",
                        "raw_price": round(raw_price, 4),
                        "raw_unit": item["unit"],
                        "source_name": item["source_label"],
                        "source_url": f"https://finance.yahoo.com/quote/{symbol}",
                        "fetched_at": now,
                        "is_mock": False,
                        "is_realtime": True,
                    })
            except Exception as exc:
                logger.warning("[GlobalPrice] Failed to fetch %s: %s", symbol, exc)
        return results

    def get_price_sources_status(self, db: Session) -> dict:
        valid_count = (
            db.query(MarketPrice)
            .filter(
                MarketPrice.IsMock == False,  # noqa: E712
                MarketPrice.SourceURL.isnot(None),
                MarketPrice.SourceName.isnot(None),
                MarketPrice.FetchedAt.isnot(None),
            )
            .count()
        )
        return {
            "sources": [
                {
                    "source_name": OFFICIAL_AGRI_SOURCE_NAME,
                    "source_type": "official_agriculture_price",
                    "enabled": True,
                    "configured": True,
                    "role": "Nguon chinh cho gia nong san Viet Nam",
                    "status": external_circuit_breaker.status("thitruongnongsan_price"),
                },
                {
                    "source_name": "MarketPrices DB",
                    "source_type": "database_cache",
                    "enabled": True,
                    "configured": True,
                    "role": "Cache du lieu that da crawl/API",
                    "records": valid_count,
                },
            ],
            "cache_ttl_minutes": 180,
            "checked_at": datetime.now(),
        }

    def refresh_prices(
        self,
        db: Session,
        *,
        crop_name: str | None = None,
        source_name: str | None = None,
    ) -> dict:
        selected_crop = self._clean_crop(crop_name or "lua")
        log = start_ingestion_log(db, "refresh_market_prices", source_name or OFFICIAL_AGRI_SOURCE_NAME)
        try:
            result = self.refresh_price_for_crop_region(db, selected_crop, None)
            finish_ingestion_log(
                db,
                log,
                status="success" if result.get("status") in {"success", "empty"} else "failed",
                records_fetched=int(result.get("records_fetched") or 0),
                records_saved=int(result.get("records_saved") or 0) + int(result.get("records_updated") or 0),
                error_message="; ".join(result.get("errors") or []) or None,
            )
            return result
        except Exception as exc:
            finish_ingestion_log(db, log, status="failed", error_message=str(exc))
            return {"status": "failed", "error": str(exc), "records_fetched": 0, "records_saved": 0, "is_mock": False}

    def cache_status(self, updated_at: datetime | None) -> str:
        return cache_status_for(updated_at, "official_price")

    def is_stale(self, updated_at: datetime | None) -> bool:
        return self.cache_status(updated_at) == "stale_cache"

    def exchange_rate(self, live: bool = False) -> dict:
        now = datetime.now()
        return {
            "_api_error": True,
            "error_code": "EXCHANGE_RATE_DISABLED",
            "error_message": "Nguon ty gia khong duoc dung trong luong gia nong san Viet Nam.",
            "source_name": "Disabled",
            "source_url": None,
            "is_realtime": False,
            "is_mock": False,
            "cache_status": "miss",
            "fetched_at": now,
            "last_updated": now,
        }

    def _latest_db_price(self, db: Session, crop_name: str, region: str | None) -> MarketPrice | None:
        try:
            crop = ensure_crop(db, crop_name)
            rows = (
                db.query(MarketPrice)
                .filter(MarketPrice.CropID == crop.CropID)
                .order_by(desc(MarketPrice.PriceDate), desc(MarketPrice.FetchedAt), desc(MarketPrice.UpdatedAt))
                .limit(200)
                .all()
            )
            target_region = normalize_text(region or "")
            fallback_row = None
            for row in rows:
                if not self._is_valid_price_cache(row):
                    continue
                if (row.SourceType or "") in {"global_commodity", "global_futures_reference", "global_reference"}:
                    continue
                if not target_region:
                    if fallback_row is None:
                        fallback_row = row
                    continue
                if normalize_text(row.Region) == target_region:
                    return row
            return fallback_row
        except Exception:
            db.rollback()
            return None

    @staticmethod
    def _is_valid_price_cache(row: MarketPrice) -> bool:
        return is_real_cache_record(
            source_url=row.SourceURL,
            source_name=row.SourceName,
            fetched_at=row.FetchedAt,
            is_mock=row.IsMock,
        )

    def _row_to_current_response(
        self,
        db: Session,
        row: MarketPrice,
        *,
        crop_name: str,
        region: str,
        cache_status: str,
        refresh_result: dict | None,
        warning: str | None = None,
    ) -> dict:
        current_price = float(row.PricePerKg or 0)
        response_region = region or row.Region or ""
        previous = self._previous_price(db, crop_name, response_region, row.PriceID)
        price_change = round(current_price - previous, 2) if previous else 0.0
        price_change_percent = round(price_change / previous * 100, 2) if previous else 0.0
        fetched_at = row.FetchedAt or row.UpdatedAt or datetime.now()
        is_live = cache_status == "live"
        local_price = {
            "price": round(current_price, 2),
            "unit": self._display_unit(row),
            "currency": "VND",
            "source_name": row.SourceName,
            "source_type": row.SourceType or "official_agriculture_price",
            "source_url": row.SourceURL,
            "is_mock": False,
            "cache_status": cache_status,
        }
        payload = {
            "crop_name": crop_name.strip(),
            "crop": crop_name.strip(),
            "region": response_region,
            "current_price": round(current_price, 2),
            "market_price": round(current_price, 2),
            "price": round(current_price, 2),
            "unit": self._display_unit(row),
            "currency": "VND",
            "price_change": price_change,
            "price_change_percent": price_change_percent,
            "trend": self._trend_from_change(price_change_percent),
            "local_price": local_price,
            "global_reference": None,
            "source": "realtime_api" if is_live else "cache",
            "source_type": row.SourceType or "official_agriculture_price",
            "source_name": row.SourceName,
            "source_url": row.SourceURL,
            "fetched_at": fetched_at,
            "observed_at": row.ObservedAt or datetime.combine(row.PriceDate or date.today(), datetime.min.time()),
            "last_updated": fetched_at,
            "price_date": row.PriceDate,
            "confidence_score": float(row.ConfidenceScore or 0.86),
            "confidence": float(row.ConfidenceScore or 0.86),
            "is_mock": False,
            "is_realtime": is_live,
            "cache_status": cache_status,
            "data_age_minutes": age_minutes(fetched_at),
            "refresh_result": refresh_result,
        }
        if warning:
            payload["warning"] = warning
            payload["message"] = warning
        return payload

    @staticmethod
    def _no_realtime_price_response(
        *,
        crop_name: str,
        region: str | None,
        refresh_result: dict | None,
    ) -> dict:
        payload = realtime_error(
            code="REALTIME_PRICE_FAILED",
            message="Không thể tải giá nông sản thực tế từ nguồn thị trường nông sản Việt Nam.",
            source_name=OFFICIAL_AGRI_SOURCE_NAME,
            source_url=OFFICIAL_PRICE_URL,
            detail="; ".join(refresh_result.get("errors") or []) if refresh_result else None,
        )
        payload.update({"crop_name": crop_name.strip(), "region": region or "", "price": None, "refresh_result": refresh_result})
        return payload

    def _previous_price(self, db: Session, crop_name: str, region: str | None, exclude_price_id: int) -> float | None:
        try:
            crop = ensure_crop(db, crop_name)
            rows = (
                db.query(MarketPrice)
                .filter(MarketPrice.CropID == crop.CropID, MarketPrice.PriceID != exclude_price_id)
                .order_by(desc(MarketPrice.PriceDate), desc(MarketPrice.FetchedAt), desc(MarketPrice.UpdatedAt))
                .limit(30)
                .all()
            )
            target_region = normalize_text(region)
            for row in rows:
                if not self._is_valid_price_cache(row):
                    continue
                if normalize_text(row.Region) == target_region:
                    return float(row.PricePerKg)
            return None
        except Exception:
            db.rollback()
            return None

    @staticmethod
    def _clean_crop(crop_name: str | None) -> str:
        return normalize_text(crop_name or "lua") or "lua"

    @staticmethod
    def _clean_region(region: str | None) -> str | None:
        if region is None:
            return None
        cleaned = " ".join(region.strip().split())
        return cleaned or None

    @staticmethod
    def _display_unit(row: MarketPrice) -> str:
        return "VND/kg"

    @staticmethod
    def _trend_from_change(change_percent: float) -> str:
        if change_percent > 1:
            return "up"
        if change_percent < -1:
            return "down"
        return "stable"


price_aggregator_service = PriceAggregatorService()
