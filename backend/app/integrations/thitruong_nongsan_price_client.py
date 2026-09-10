from __future__ import annotations

import html
import json
import logging
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.core.config import settings
from app.core.real_data import external_circuit_breaker
from app.core.resilience import build_timeout, resilient_request
from app.repositories.common import normalize_text

logger = logging.getLogger(__name__)

# Module-level cache: (date_from, date_to) → (fetched_at_monotonic, html_content)
# Prevents redundant HTTP calls when dashboard/pricing service calls per crop/region.
_PAGE_CACHE: dict[tuple[date, date], tuple[float, str]] = {}
_PAGE_CACHE_TTL = 300.0  # 5 minutes


class ThiTruongNongSanPriceClient:
    def __init__(self) -> None:
        self.source_name = "Thông tin thị trường nông sản"
        self.source_url = (settings.THITRUONG_NONGSAN_PRICE_URL or "https://thitruongnongsan.gov.vn/vn/nguonwmy.aspx").strip()
        self.timeout = build_timeout(
            total=min(float(getattr(settings, "EXTERNAL_TOTAL_TIMEOUT_SECONDS", 12.0)), 12.0),
            connect=min(float(getattr(settings, "EXTERNAL_CONNECT_TIMEOUT_SECONDS", 3.0)), 3.0),
            read=min(float(getattr(settings, "EXTERNAL_READ_TIMEOUT_SECONDS", 8.0)), 8.0),
        )
        # Allow 0 retries for fail-fast behavior — forced min=1 doubles every timeout
        self.retries = min(int(getattr(settings, "EXTERNAL_RETRY_COUNT", 1)), 2)
        self.allowed_crops = (
            "ca phe",
            "lua gao",
            "lua",
            "gao",
            "rau",
            "rau qua",
            "ho tieu",
            "cao su",
            "sau rieng",
            "thanh long",
            "xoai",
            "cu",
            "cay an trai",
        )

    def fetch_prices(self, crop_name: str | None = None, region: str | None = None) -> list[dict]:
        if not getattr(settings, "ENABLE_THITRUONG_NONGSAN_PRICE", True):
            return []

        key = "thitruongnongsan_official_price"
        external_circuit_breaker.before_call(key)
        try:
            page = self._fetch_page()
            records = self._parse_prices(page, crop_name=crop_name, region=region)
            external_circuit_breaker.record_success(key)
            return records
        except Exception as exc:
            external_circuit_breaker.record_failure(key, exc)
            logger.exception("Failed to fetch official agriculture prices: %s", exc)
            return []

    def fetch_current_price(self, crop_name: str, region: str | None = None) -> dict | None:
        records = self.fetch_prices(crop_name=crop_name, region=region)
        return records[0] if records else None

    def fetch_price_history(self, crop_name: str, region: str | None = None, days: int = 30) -> list[dict]:
        records = self.fetch_prices(crop_name=crop_name, region=region)
        if not records:
            return []
        cutoff = date.today() - timedelta(days=max(days, 1))
        history: list[dict] = []

        for record in records:
            price_date = record.get("price_date")
            if isinstance(price_date, str):
                try:
                    price_date = datetime.fromisoformat(price_date).date()
                except ValueError:
                    price_date = None
            if isinstance(price_date, date) and price_date >= cutoff:
                history.append(record)
        return history

    def fetch_history(self, crop_name: str | None = None, region: str | None = None, days: int = 90) -> list[dict]:
        """Backfill price history by fetching in 30-day chunks.

        days=90  → 3 POST requests (90d, 60d, 30d windows)
        days=180 → 6 POST requests
        """
        chunk = 30
        today = date.today()
        all_records: list[dict] = []
        seen_keys: set[tuple] = set()

        for offset in range(0, days, chunk):
            date_to   = today - timedelta(days=offset)
            date_from = today - timedelta(days=offset + chunk)
            try:
                html_content = self._fetch_page_range(date_from, date_to)
                records = self._parse_prices(html_content, crop_name=crop_name, region=region)
                for r in records:
                    key = (
                        normalize_text(r.get("crop_name") or ""),
                        normalize_text(r.get("region") or ""),
                        str(r.get("price_date") or ""),
                        float(r.get("price") or 0),
                    )
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_records.append(r)
            except Exception as exc:
                logger.warning("[ThiTruong] history chunk %s→%s failed: %s", date_from, date_to, exc)

        return all_records

    def _fetch_page(self) -> str:
        """Fetch latest 30 days (default window for regular refresh)."""
        today = date.today()
        return self._fetch_page_range(today - timedelta(days=30), today)

    def _fetch_page_range(self, date_from: date, date_to: date) -> str:
        """POST ASP.NET UpdatePanel for all commodities within a date range.
        Saves raw HTML to storage/raw_crawl/ before returning.

        Results are cached for _PAGE_CACHE_TTL seconds to avoid redundant HTTP
        calls when dashboard/pricing service invokes per crop×region.
        """
        cache_key = (date_from, date_to)
        cached = _PAGE_CACHE.get(cache_key)
        if cached:
            fetched_at, html_content = cached
            if time.monotonic() - fetched_at < _PAGE_CACHE_TTL:
                logger.debug("[ThiTruong] returning cached page (%s → %s)", date_from, date_to)
                return html_content

        # Step 1: GET to obtain ASP.NET hidden fields
        get_resp = resilient_request(
            "GET",
            self.source_url,
            headers=self._headers(),
            timeout=self.timeout,
            retries=0,
            service_name="thitruongnongsan_price_get",
        )
        soup_init = BeautifulSoup(get_resp.text, "lxml")
        viewstate     = (soup_init.find("input", {"id": "__VIEWSTATE"}) or {}).get("value", "")
        eventval      = (soup_init.find("input", {"id": "__EVENTVALIDATION"}) or {}).get("value", "")
        viewstate_gen = (soup_init.find("input", {"id": "__VIEWSTATEGENERATOR"}) or {}).get("value", "")

        if not viewstate:
            return get_resp.text

        from_str = date_from.strftime("%d/%m/%Y")
        to_str   = date_to.strftime("%d/%m/%Y")

        ajax_headers = {
            **self._headers(),
            "X-MicrosoftAjax": "Delta=true",
            "X-Requested-With": "XMLHttpRequest",
        }

        combined_html = ""
        for commodity in ("Cà phê", "Lúa gạo", "Rau, quả"):
            try:
                form_data = {
                    "ctl00$ScriptManager_Sitemaster": "ctl00$maincontent$UpdatePanel2|ctl00$maincontent$Xem",
                    "__ASYNCPOST":                   "true",
                    "__VIEWSTATE":                   viewstate,
                    "__EVENTVALIDATION":             eventval,
                    "__VIEWSTATEGENERATOR":          viewstate_gen,
                    "ctl00$maincontent$tu_ngay":       from_str,
                    "ctl00$maincontent$den_ngay":       to_str,
                    "ctl00$maincontent$Ngành_hàng":     commodity,
                    "ctl00$maincontent$Theo_thời_gian": "ngay",
                    "ctl00$maincontent$Xem":            "Xem",
                }
                post_resp = resilient_request(
                    "POST",
                    self.source_url,
                    headers=ajax_headers,
                    data=form_data,
                    timeout=self.timeout,
                    retries=self.retries,
                    backoff=float(getattr(settings, "EXTERNAL_BACKOFF_SECONDS", 0.4)),
                    service_name="thitruongnongsan_price_post",
                )
                fragment = self._extract_update_panel(post_resp.text)
                raw_html = fragment if fragment else post_resp.text
                self._save_raw_html(raw_html, commodity, date_from, date_to)
                combined_html += "\n" + raw_html
            except Exception as exc:
                logger.warning("[ThiTruong] POST commodity=%s %s→%s failed: %s", commodity, from_str, to_str, exc)

        result = combined_html if combined_html else get_resp.text
        if combined_html:
            _PAGE_CACHE[cache_key] = (time.monotonic(), result)
        return result

    def _save_raw_html(self, content: str, commodity: str, date_from: date, date_to: date) -> None:
        """Save raw HTML fragment to disk before any parsing."""
        try:
            raw_dir = Path(getattr(settings, "FIRECRAWL_RAW_STORAGE_PATH", "storage/raw_crawl"))
            today_dir = raw_dir / date.today().strftime("%Y%m%d")
            today_dir.mkdir(parents=True, exist_ok=True)
            slug = commodity.replace(" ", "_").replace(",", "").lower()
            filename = f"thitruongnongsan_{slug}_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.html"
            (today_dir / filename).write_text(content, encoding="utf-8")
        except Exception as exc:
            logger.warning("[ThiTruong] Could not save raw HTML: %s", exc)

    @staticmethod
    def _extract_update_panel(response_text: str) -> str:
        """Parse ASP.NET UpdatePanel delta response to extract the HTML fragment."""
        matches = re.findall(r"\d+\|updatePanel\|[^|]+\|(.+?)(?=\d+\|[a-z]+\||$)", response_text, re.DOTALL)
        return "\n".join(matches) if matches else ""

    def _parse_prices(self, content: str, *, crop_name: str | None, region: str | None) -> list[dict]:
        soup = BeautifulSoup(content, "lxml")
        records: list[dict] = []
        normalized_crop = normalize_text(crop_name or "")
        normalized_region = normalize_text(region or "")
        fetched_at = datetime.now()

        table_candidates = soup.find_all("table")
        for table in table_candidates:
            headers = self._table_headers(table)
            if not headers:
                continue
            rows = table.find_all("tr")
            for row in rows[1:]:
                cells = [self._clean_html(cell.get_text(" ", strip=True)) for cell in row.find_all(["td", "th"])]
                if len(cells) < 2:
                    continue
                parsed = self._row_to_record(cells, headers=headers, fetched_at=fetched_at)
                if not parsed:
                    continue
                if normalized_crop and not self._crop_matches(normalized_crop, parsed["crop_name"], parsed.get("metadata", {})):
                    continue
                if normalized_region and not self._region_matches(normalized_region, parsed["region"]):
                    continue
                records.append(parsed)

        if not records:
            logger.error(
                "Parse tables yielded 0 records from %s (crop_name=%s, region=%s)",
                self.source_url,
                crop_name,
                region,
            )
            records.extend(
                self._parse_text_fallback(
                    soup,
                    normalized_crop=normalized_crop,
                    normalized_region=normalized_region,
                    fetched_at=fetched_at,
                )
            )


        deduped: list[dict] = []
        seen: set[tuple[str, str, str, float, str]] = set()
        for record in records:
            key = (
                normalize_text(record.get("crop_name") or ""),
                normalize_text(record.get("region") or ""),
                normalize_text(record.get("source_url") or ""),
                float(record.get("price") or 0),
                str(record.get("price_date") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(record)

        return deduped

    def _parse_text_fallback(
        self,
        soup: BeautifulSoup,
        *,
        normalized_crop: str,
        normalized_region: str,
        fetched_at: datetime,
    ) -> list[dict]:
        text = self._clean_html(soup.get_text(" ", strip=True))
        candidates: list[dict] = []

        # Tên mặt hàng phải bắt đầu bằng CHỮ và không chứa chữ số.
        #
        # Bản cũ cho phép [A-Za-zÀ-ỹ0-9...] nên hai hỏng cùng lúc trên trang thật:
        #   * Bộ đếm lượt truy cập "75373839" khớp thành product="7537",
        #     price=3839 — một con số trần thành giá nông sản.
        #   * "Cà phê nhân xô 96.400" bị nhóm product ăn mất chữ số 9, còn
        #     "6.400" — sai một bậc độ lớn.
        TEN = r"(?P<product>[A-Za-zÀ-ỹ][A-Za-zÀ-ỹ\s\-]{2,79})"
        GIA = r"(?P<price>\d{1,3}(?:[.,]\d{3})+|\d{4,7})"
        DON_VI = r"\s*(?:vnđ|vnd|đ|d)?(?:/kg|kg|k?g)?"
        patterns = [
            TEN + r"(?P<region>\s+[A-Za-zÀ-ỹ][A-Za-zÀ-ỹ\s\-]{1,49})?(?:\:|\-|\–|\—)?\s*" + GIA + DON_VI,
            GIA + DON_VI + r"\s*" + TEN,
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                product = self._clean_text(match.groupdict().get("product"))
                region = self._clean_text(match.groupdict().get("region")) or "Việt Nam"
                price = self._parse_price(match.groupdict().get("price"))
                if not product or price is None:
                    continue
                record = self._build_record(
                    crop_name=self._infer_crop_name(product, normalized_crop),
                    product_name=product,
                    region=region,
                    price=price,
                    source_url=self.source_url,
                    fetched_at=fetched_at,
                    metadata={"matched_text": match.group(0)[:240]},
                )
                # _infer_crop_name trả về CHÍNH cây đang được hỏi, bất kể trang
                # viết gì — nên đối chiếu với nó luôn khớp và không lọc được gì.
                # Phải soi vào tên mặt hàng thật lấy từ trang.
                if normalized_crop and not self._crop_matches(
                    normalized_crop, product, {"official_product_name": product}
                ):
                    continue
                if normalized_region and not self._region_matches(normalized_region, record["region"]):
                    continue
                candidates.append(record)

        return candidates[:20]

    def _row_to_record(self, cells: list[str], *, headers: list[str], fetched_at: datetime) -> dict | None:
        header_map = {self._normalize_header(header): idx for idx, header in enumerate(headers)}
        row_text = " | ".join(cells)

        # "Tên mặt hàng" normalizes to "ten mat hang"; also try partial keys via contains
        product = self._pick_cell(cells, header_map, (
            "ten mat hang", "san pham", "mat hang", "ten san pham", "nong san", "product", "commodity",
        )) or self._pick_cell_contains(cells, header_map, ("ten", "mat hang", "san pham"))
        # "Thị trường" on this site = region/location (e.g. Đắk Lắk), not a market type
        region = self._pick_cell(cells, header_map, (
            "thi truong", "khu vuc", "vung", "noi ban", "dia phuong", "tinh", "region", "province", "area",
        )) or self._pick_cell_contains(cells, header_map, ("thi truong",))
        price_text = self._pick_cell(cells, header_map, ("gia", "gia ban", "price", "don gia", "muc gia", "price/kg", "price per kg"))
        date_text = self._pick_cell(cells, header_map, ("ngay", "thoi gian", "date", "updated", "cap nhat", "published"))
        market_type = self._pick_cell(cells, header_map, ("loai thi truong", "market type", "loai gia"))
        unit = self._pick_cell(cells, header_map, ("don vi", "unit", "dvt")) or "VNĐ/kg"

        if not product and not price_text:
            return None

        price = self._parse_price(price_text)
        if price is None:
            price = self._price_from_row_text(row_text)
        if price is None:
            return None

        price_date = self._parse_date(date_text) or date.today()
        product_name = self._clean_text(product) or self._guess_product_from_text(row_text)
        region_name = self._clean_text(region) or "Việt Nam"
        crop_name = self._infer_crop_name(product_name, normalize_text(product_name))

        return self._build_record(
            crop_name=crop_name,
            product_name=product_name,
            region=region_name,
            price=price,
            source_url=self.source_url,
            fetched_at=fetched_at,
            price_date=price_date.isoformat() if hasattr(price_date, "isoformat") else price_date,
            unit=unit or "VNĐ/kg",
            market_type=market_type or "official_vietnam_agriculture",

            metadata={
                "row_text": row_text[:400],
                "headers": headers,
            },
        )

    def _build_record(
        self,
        *,
        crop_name: str,
        product_name: str,
        region: str,
        price: float,
        source_url: str,
        fetched_at: datetime,
        price_date: date | None = None,
        unit: str = "VNĐ/kg",
        market_type: str = "official_vietnam_agriculture",
        metadata: dict[str, Any] | None = None,
    ) -> dict:
        final_date = price_date or date.today()
        final_price_date = final_date.isoformat() if hasattr(final_date, "isoformat") else str(final_date)
        final_price_date_obj = date.fromisoformat(final_price_date) if isinstance(final_price_date, str) else final_date

        return {
            "crop_name": crop_name,
            "region": region,
            "price": round(float(price), 2),
            "unit": unit or "VNĐ/kg",
            "currency": "VND",
            "price_date": final_price_date,
            "market_type": market_type or "official_vietnam_agriculture",
            "source_name": self.source_name,
            "source_url": source_url,
            "source_type": "official_vietnam_agriculture",
            "fetched_at": fetched_at,
            "observed_at": datetime.combine(final_price_date_obj, datetime.min.time()),

            "is_realtime": True,
            "is_mock": False,
            "metadata": {
                "official_product_name": product_name,
                "source_url": source_url,
                **(metadata or {}),
            },
        }

    @staticmethod
    def _table_headers(table) -> list[str]:
        first_row = table.find("tr")
        if not first_row:
            return []
        cells = first_row.find_all(["th", "td"])
        return [ThiTruongNongSanPriceClient._clean_html(cell.get_text(" ", strip=True)) for cell in cells]

    @staticmethod
    def _pick_cell(cells: list[str], header_map: dict[str, int], keys: tuple[str, ...]) -> str | None:
        for key in keys:
            idx = header_map.get(key)
            if idx is not None and idx < len(cells):
                value = cells[idx]
                if value:
                    return value
        return None

    @staticmethod
    def _pick_cell_contains(cells: list[str], header_map: dict[str, int], keywords: tuple[str, ...]) -> str | None:
        """Fallback: find header whose normalized name CONTAINS any keyword."""
        for header, idx in header_map.items():
            if any(kw in header for kw in keywords):
                if idx < len(cells) and cells[idx]:
                    return cells[idx]
        return None

    @staticmethod
    def _normalize_header(value: str | None) -> str:
        return normalize_text(value or "").replace("-", " ").replace("_", " ").strip()

    @staticmethod
    def _clean_html(value: str | None) -> str:
        text = html.unescape(value or "")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _clean_text(value: str | None) -> str:
        if not value:
            return ""
        text = ThiTruongNongSanPriceClient._clean_html(value)
        text = re.sub(r"^[\-\:\|]+", "", text).strip()
        return text

    @staticmethod
    def _parse_price(value: Any) -> float | None:
        if value in (None, ""):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().lower()
        if not text:
            return None
        digits = re.sub(r"[^\d,\.]", "", text)
        if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", digits):
            digits = digits.replace(".", "").replace(",", "")
        else:
            digits = digits.replace(",", "")
        try:
            price = float(digits)
        except ValueError:
            return None
        return price if price > 0 else None

    @staticmethod
    def _price_from_row_text(text: str) -> float | None:
        candidates = re.findall(r"(\d{1,3}(?:[.,]\d{3})+|\d{4,7})", text)
        for candidate in candidates:
            price = ThiTruongNongSanPriceClient._parse_price(candidate)
            if price:
                return price
        return None

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        if isinstance(value, date):
            return value
        text = str(value or "").strip()
        if not text:
            return None
        text = text.replace("Ngày", "").replace("ngày", "").strip()
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
            try:
                return datetime.strptime(text[:10], fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _guess_product_from_text(text: str) -> str:
        return ThiTruongNongSanPriceClient._clean_text(text[:120]) or "Nông sản"

    @staticmethod
    def _infer_crop_name(product_name: str, normalized_crop: str) -> str:
        product = normalize_text(product_name)
        if normalized_crop:
            if "ca phe" in normalized_crop:
                return "ca phe"
            if any(token in normalized_crop for token in ("lua", "gao")):
                return "lua"
            if "ho tieu" in normalized_crop:
                return "ho tieu"
            if "cao su" in normalized_crop:
                return "cao su"
            if "sau rieng" in normalized_crop:
                return "sau rieng"
            if "thanh long" in normalized_crop:
                return "thanh long"
            if "xoai" in normalized_crop:
                return "xoai"
            if "rau" in normalized_crop:
                return "rau"
        mapping = {
            "ca phe": ("ca phe", "coffee"),
            "lua": ("lua", "gao", "rice", "paddy"),
            "ho tieu": ("ho tieu", "tieu", "pepper"),
            "cao su": ("cao su", "rubber"),
            "sau rieng": ("sau rieng", "durian"),
            "thanh long": ("thanh long", "dragon fruit"),
            "xoai": ("xoai", "mango"),
            "rau": ("rau", "cu", "qua", "vegetable", "fruit"),
            "rau qua": ("rau", "cu", "qua", "vegetable", "fruit"),
        }
        for crop, keywords in mapping.items():
            if any(keyword in product for keyword in keywords):
                return crop
        return normalized_crop or "rau"

    @staticmethod
    def _crop_matches(normalized_crop: str, crop_name: str, metadata: dict[str, Any]) -> bool:
        target = normalize_text(crop_name)
        meta_text = normalize_text(json.dumps(metadata, ensure_ascii=False))
        if not normalized_crop:
            return True
        if normalized_crop in target or target in normalized_crop:
            return True
        aliases = {
            "ca phe": ("ca phe", "coffee"),
            "lua": ("lua", "gao", "rice", "paddy"),
            "gao": ("lua", "gao", "rice", "paddy"),
            "ho tieu": ("ho tieu", "pepper", "tieu"),
            "cao su": ("cao su", "rubber"),
            "sau rieng": ("sau rieng", "durian"),
            "thanh long": ("thanh long", "dragon fruit"),
            "xoai": ("xoai", "mango"),
            "rau": ("rau", "cu", "qua", "vegetable", "fruit"),
            "rau qua": ("rau", "cu", "qua", "vegetable", "fruit"),
        }
        accepted = aliases.get(normalized_crop, (normalized_crop,))
        return any(keyword in target or keyword in meta_text for keyword in accepted)

    @staticmethod
    def _region_matches(normalized_region: str, region: str) -> bool:
        if not normalized_region:
            return True
        return normalized_region in normalize_text(region) or normalize_text(region) in normalized_region

    @staticmethod
    def _headers() -> dict[str, str]:
        return {
            "User-Agent": "Mozilla/5.0 (compatible; NongNghiepAI/1.0; +https://thitruongnongsan.gov.vn)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }


thitruong_nongsan_price_client = ThiTruongNongSanPriceClient()
