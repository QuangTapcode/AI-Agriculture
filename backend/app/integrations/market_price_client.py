import csv
import io
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.resilience import build_timeout, resilient_request

logger = logging.getLogger(__name__)


class MarketPriceClient:
    """Fetch price records from configured external JSON/CSV/HTML feeds.

    PRICE_SOURCE_URLS_JSON accepts either a list of URLs or objects:
    [{"name": "source", "url": "https://example.com/prices.csv"}].
    """

    FIELD_ALIASES = {
        "crop_name": ("crop_name", "crop", "CropName", "name", "commodity"),
        "region": ("region", "Region", "province", "market", "location"),
        "price": ("price", "price_per_kg", "PricePerKg", "gia", "value"),
        "quality_grade": ("quality_grade", "QualityGrade", "grade"),
        "source_name": ("source_name", "SourceName", "source"),
        "source_url": ("source_url", "SourceURL", "url"),
        "price_date": ("price_date", "PriceDate", "date", "record_date"),
        "market_type": ("market_type", "MarketType", "type"),
    }
    LB_TO_KG = 0.45359237
    STOOQ_FUTURES = {
        "kc.f": {"crop_name": "ca phe", "unit": "cents_per_lb"},
        "sb.f": {"crop_name": "duong", "unit": "cents_per_lb"},
        "ct.f": {"crop_name": "bong", "unit": "cents_per_lb"},
        "zc.f": {"crop_name": "ngo", "unit": "cents_per_bushel", "bushel_lbs": 56},
        "zs.f": {"crop_name": "dau tuong", "unit": "cents_per_bushel", "bushel_lbs": 60},
        "zw.f": {"crop_name": "lua mi", "unit": "cents_per_bushel", "bushel_lbs": 60},
        "zr.f": {"crop_name": "gao", "unit": "usd_per_cwt"},
        "cc.f": {"crop_name": "ca cao", "unit": "usd_per_metric_ton"},
    }

    def fetch_all(self, source_name: str | None = None, crop_filter: str | None = None) -> list[dict]:
        records: list[dict] = []
        tasks = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            if self._should_fetch_stooq(source_name):
                tasks.append(executor.submit(self._fetch_stooq_futures, crop_filter))
            for source in self._configured_sources():
                if source_name and source["name"].lower() != source_name.lower():
                    continue
                tasks.append(executor.submit(self._fetch_source, source, crop_filter))

            for future in as_completed(tasks):
                try:
                    records.extend(future.result())
                except Exception:
                    continue

        self._save_raw_records(records, label=source_name or "all")
        return records

    def _save_raw_records(self, records: list[dict], label: str) -> None:
        """Save fetched records as JSON before clean_price_records transforms them."""
        try:
            raw_dir = Path(getattr(settings, "FIRECRAWL_RAW_STORAGE_PATH", "storage/raw_crawl"))
            today_dir = raw_dir / date.today().strftime("%Y%m%d")
            today_dir.mkdir(parents=True, exist_ok=True)
            slug = re.sub(r"[^\w]", "_", label.lower())[:40]
            path = today_dir / f"market_price_client_{slug}.json"
            path.write_text(
                json.dumps(records, default=str, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("[MarketPriceClient] Could not save raw records: %s", exc)

    def fetch_all_legacy(self, source_name: str | None = None, crop_filter: str | None = None) -> list[dict]:
        records: list[dict] = []
        if self._should_fetch_stooq(source_name):
            try:
                records.extend(self._fetch_stooq_futures(crop_filter))
            except Exception:
                pass
        for source in self._configured_sources():
            if source_name and source["name"].lower() != source_name.lower():
                continue
            try:
                records.extend(self._fetch_source(source, crop_filter))
            except Exception:
                continue
        return records

    def _should_fetch_stooq(self, source_name: str | None) -> bool:
        if not settings.ENABLE_STOOQ_PRICE_SOURCE:
            return False
        if not source_name:
            return True
        return source_name.lower() in {"stooq", "stooq futures", "commodity futures"}

    def _fetch_stooq_futures(self, crop_filter: str | None = None) -> list[dict]:
        usd_vnd = self._fetch_usd_vnd_rate()
        records: list[dict] = []
        headers = {"User-Agent": "Mozilla/5.0"}
        for symbol, meta in self.STOOQ_FUTURES.items():
            crop_name = meta["crop_name"]
            if crop_filter and not self._matches_crop_filter(crop_name, crop_filter):
                continue
            url = f"https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv"
            response = resilient_request(
                "GET",
                url,
                headers=headers,
                timeout=build_timeout(total=20, connect=5, read=10),
                retries=2,
                service_name="Stooq futures",
            )
            rows = self._parse_csv(response.text)
            if not rows:
                continue
            row = rows[0]
            close = self._parse_float(row.get("Close"))
            if close is None:
                continue
            price = self._convert_futures_quote_to_vnd_per_kg(close, meta, usd_vnd)
            if price is None:
                continue
            collected_at = self._parse_datetime(row.get("Date"), row.get("Time"))
            records.append(
                {
                    "crop_name": crop_name,
                    "region": "Global Futures",
                    "price": price,
                    "quality_grade": "grade_1",
                    "source_name": f"Stooq commodity futures ({row.get('Symbol') or symbol.upper()})",
                    "source_url": f"https://stooq.com/q/?s={symbol}",
                    "price_date": self._parse_date(row.get("Date")),
                    "market_type": "global_futures_reference",
                    "collected_at": collected_at,
                }
            )
        return records

    def _fetch_usd_vnd_rate(self) -> float:
        try:
            response = resilient_request(
                "GET",
                settings.EXCHANGE_RATE_API_URL,
                timeout=build_timeout(total=20, connect=5, read=10),
                retries=2,
                service_name="ExchangeRate",
            )
            payload = response.json()
            rate = payload.get("rates", {}).get("VND")
            if rate:
                return float(rate)
        except Exception:
            pass
        return float(settings.USD_VND_FALLBACK_RATE)

    def _fetch_source(self, source: dict, crop_filter: str | None = None) -> list[dict]:
        response = resilient_request(
            "GET",
            source["url"],
            timeout=build_timeout(total=20, connect=5, read=10),
            retries=2,
            service_name=f"PriceSource:{source['name']}",
        )
        content_type = response.headers.get("content-type", "").lower()
        text = response.text
        if "json" in content_type or source["url"].lower().endswith(".json"):
            raw_records = self._parse_json(response.json())
        elif "csv" in content_type or source["url"].lower().endswith(".csv"):
            raw_records = self._parse_csv(text)
        else:
            raw_records = self._parse_html(text, source["url"])

        normalized = []
        for raw in raw_records:
            record = self._normalize_record(raw, source)
            if not record:
                continue
            if crop_filter and not self._matches_crop_filter(record["crop_name"], crop_filter):
                continue
            normalized.append(record)
        return normalized

    @staticmethod
    def _matches_crop_filter(crop_name: str, crop_filter: str) -> bool:
        aliases = {
            "lua": {"lua", "gao", "rice", "paddy"},
            "gao": {"lua", "gao", "rice", "paddy"},
        }
        crop = crop_name.strip().lower()
        requested = crop_filter.strip().lower()
        accepted = aliases.get(requested, {requested})
        return any(token in crop for token in accepted)

    def _configured_sources(self) -> list[dict]:
        try:
            configured = json.loads(settings.PRICE_SOURCE_URLS_JSON or "[]")
        except json.JSONDecodeError:
            configured = []
        sources = []
        for index, item in enumerate(configured):
            if isinstance(item, str):
                sources.append({"name": f"price_source_{index + 1}", "url": item})
            elif isinstance(item, dict) and item.get("url"):
                sources.append({"name": item.get("name") or f"price_source_{index + 1}", "url": item["url"]})
        return sources

    @staticmethod
    def _parse_json(payload: Any) -> list[dict]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("records", "prices", "data", "items"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _parse_csv(text: str) -> list[dict]:
        reader = csv.DictReader(io.StringIO(text))
        return [row for row in reader]

    @staticmethod
    def _parse_html(text: str, url: str) -> list[dict]:
        compact = re.sub(r"<[^>]+>", " ", text)
        compact = re.sub(r"\s+", " ", compact)
        records = []
        pattern = re.compile(
            r"(?P<crop>[A-Za-zÀ-ỹ\s]{2,40})\s+(?P<price>\d{1,3}(?:[.,]\d{3})+|\d{4,6})\s*(?:VND|dong|đ)?\s*/?\s*kg",
            re.IGNORECASE,
        )
        for match in pattern.finditer(compact):
            crop_name = match.group("crop").strip(" :-,")
            if len(crop_name) < 2:
                continue
            records.append(
                {
                    "crop_name": crop_name[-40:].strip(),
                    "region": "Vietnam",
                    "price": match.group("price"),
                    "source_url": url,
                    "price_date": date.today().isoformat(),
                }
            )
        return records[:100]

    def _normalize_record(self, raw: dict, source: dict) -> dict | None:
        crop_name = self._pick(raw, "crop_name")
        region = self._pick(raw, "region") or "Vietnam"
        price = self._parse_price(self._pick(raw, "price"))
        if not crop_name or not price:
            return None
        return {
            "crop_name": str(crop_name).strip(),
            "region": str(region).strip(),
            "price": price,
            "quality_grade": self._pick(raw, "quality_grade") or "grade_1",
            "source_name": self._pick(raw, "source_name") or source["name"],
            "source_url": self._pick(raw, "source_url") or source["url"],
            "price_date": self._parse_date(self._pick(raw, "price_date")),
            "market_type": self._pick(raw, "market_type") or None,
            "collected_at": datetime.now(),
        }

    def _pick(self, raw: dict, field: str) -> Any:
        for alias in self.FIELD_ALIASES[field]:
            if raw.get(alias) not in (None, ""):
                return raw.get(alias)
        return None

    @staticmethod
    def _parse_price(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value)
        if re.search(r"\d[.,]\d{3}", text):
            digits = re.sub(r"[^\d]", "", text)
        else:
            digits = re.sub(r"[^\d.]", "", text.replace(",", ""))
        try:
            price = float(digits)
        except ValueError:
            return None
        return price if price > 0 else None

    @staticmethod
    def _parse_float(value: Any) -> float | None:
        if value in (None, "", "N/D"):
            return None
        try:
            number = float(str(value).replace(",", ""))
        except ValueError:
            return None
        return number if number > 0 else None

    @classmethod
    def _convert_futures_quote_to_vnd_per_kg(cls, close: float, meta: dict, usd_vnd: float) -> float | None:
        unit = meta.get("unit")
        if unit == "cents_per_lb":
            usd_per_kg = (close / 100) / cls.LB_TO_KG
        elif unit == "cents_per_bushel":
            bushel_lbs = float(meta.get("bushel_lbs") or 1)
            usd_per_kg = (close / 100) / (bushel_lbs * cls.LB_TO_KG)
        elif unit == "usd_per_cwt":
            usd_per_kg = close / (100 * cls.LB_TO_KG)
        elif unit == "usd_per_metric_ton":
            usd_per_kg = close / 1000
        else:
            return None
        return round(usd_per_kg * usd_vnd, 2)

    @staticmethod
    def _parse_date(value: Any) -> date:
        if isinstance(value, date):
            return value
        if not value:
            return date.today()
        text = str(value).strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return date.today()

    @staticmethod
    def _parse_datetime(date_value: Any, time_value: Any) -> datetime:
        text = f"{date_value or ''} {time_value or ''}".strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return datetime.now()


market_price_client = MarketPriceClient()
