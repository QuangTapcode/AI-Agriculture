"""
Scrape agricultural price pages via Firecrawl API with form Actions.

Pipeline per commodity:
  1. POST /v1/scrape with actions (fill date range, select commodity, submit)
  2. Save raw JSON to FIRECRAWL_RAW_STORAGE_PATH/{YYYYMMDD}/{commodity}.json
  3. Parse markdown table → list[dict]
  4. Caller runs through clean_price_records() before DB write

Enabled only when FIRECRAWL_API_KEY is set and FIRECRAWL_ENABLED=true.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

from app.core.config import settings
from app.repositories.common import normalize_text

logger = logging.getLogger(__name__)

# Selectors discovered from HTML inspection of nguonwmy.aspx
_FORM_URL = "https://thitruongnongsan.gov.vn/vn/nguonwmy.aspx"
_SEL_FROM  = "#ctl00_maincontent_tu_ngay"
_SEL_TO    = "#ctl00_maincontent_den_ngay"
_SEL_NGANH = "#ctl00_maincontent_Ngành_hàng"
_SEL_XEM   = "#ctl00_maincontent_Xem"

# Commodities to scrape in each refresh
_COMMODITIES = ["Cà phê", "Lúa gạo", "Rau, quả"]

# Minimal region normalization — mirrors data_quality_service._REGION_ALIASES
# Kept here to avoid a services→integrations circular import.
_REGION_ALIASES: dict[str, str] = {
    "tp hcm": "TP.HCM", "ho chi minh": "TP.HCM", "tphcm": "TP.HCM", "hcm": "TP.HCM",
    "ha noi": "Hà Nội", "hanoi": "Hà Nội", "hn": "Hà Nội",
    "can tho": "Cần Thơ", "da nang": "Đà Nẵng", "lam dong": "Lâm Đồng",
    "hai phong": "Hải Phòng",
}


def _normalize_region(name: str | None) -> str:
    if not name:
        return "Toàn quốc"
    key = unicodedata.normalize("NFD", name.strip().lower()).replace("đ", "d")
    key = "".join(c for c in key if unicodedata.category(c) != "Mn")
    return _REGION_ALIASES.get(key, name.strip())


class FirecrawlPriceClient:

    SOURCE_NAME = "Firecrawl/thitruongnongsan"

    # ------------------------------------------------------------------ #
    # Public interface                                                      #
    # ------------------------------------------------------------------ #

    def fetch_prices(
        self,
        crop_name: str | None = None,
        region: str | None = None,
    ) -> list[dict]:
        """Scrape all commodities, return combined price records.

        Returns [] when FIRECRAWL_ENABLED is false or API key is missing.
        """
        if not settings.FIRECRAWL_ENABLED or not settings.FIRECRAWL_API_KEY:
            return []

        all_records: list[dict] = []
        for commodity in _COMMODITIES:
            raw = self._scrape_with_actions(commodity)
            if not raw:
                continue
            slug = commodity.replace(" ", "_").replace(",", "")
            self._save_raw(raw, source=slug)
            markdown = (raw.get("data") or {}).get("markdown") or ""
            records = self._parse_markdown(markdown, commodity=commodity)
            all_records.extend(records)
            logger.info("[Firecrawl] %s → %d records", commodity, len(records))

        if crop_name:
            norm = normalize_text(crop_name)
            all_records = [r for r in all_records if norm in normalize_text(r.get("crop_name", ""))]
        if region:
            norm = normalize_text(region)
            all_records = [r for r in all_records if norm in normalize_text(r.get("region", ""))]

        return all_records

    # ------------------------------------------------------------------ #
    # Step 2 — Extract: Firecrawl with form actions                        #
    # ------------------------------------------------------------------ #

    def _scrape_with_actions(self, commodity: str) -> dict | None:
        today = date.today()
        from_date = (today - timedelta(days=30)).strftime("%d/%m/%Y")
        to_date = today.strftime("%d/%m/%Y")

        actions = [
            {"type": "wait", "milliseconds": 1500},
            {"type": "write", "selector": _SEL_FROM, "text": from_date},
            {"type": "write", "selector": _SEL_TO,   "text": to_date},
            {"type": "select", "selector": _SEL_NGANH, "value": commodity},
            {"type": "wait", "milliseconds": 500},
            {"type": "click", "selector": _SEL_XEM},
            {"type": "wait", "milliseconds": 3000},
        ]

        endpoint = f"{settings.FIRECRAWL_BASE_URL}/v1/scrape"
        try:
            response = httpx.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {settings.FIRECRAWL_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "url": _FORM_URL,
                    "formats": ["markdown"],
                    "onlyMainContent": True,
                    "actions": actions,
                },
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
            response.raise_for_status()
            data = response.json()
            if not data.get("success"):
                logger.error("[Firecrawl] API returned success=false for %s: %s", commodity, data)
                return None
            return data
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                logger.warning("[Firecrawl] Rate limited (429) for commodity=%s", commodity)
            else:
                logger.error("[Firecrawl] HTTP %s for commodity=%s", exc.response.status_code, commodity)
            return None
        except Exception as exc:
            logger.error("[Firecrawl] scrape failed for commodity=%s: %s", commodity, exc)
            return None

    def _save_raw(self, data: dict, source: str) -> None:
        """Persist full Firecrawl response before any transformation."""
        today = date.today().strftime("%Y%m%d")
        base = Path(settings.FIRECRAWL_RAW_STORAGE_PATH)
        target_dir = base / today
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{source}.json"
        try:
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info("[Firecrawl] Raw saved → %s", path)
        except Exception as exc:
            logger.warning("[Firecrawl] Could not save raw JSON: %s", exc)

    # ------------------------------------------------------------------ #
    # Step 3 — Parse markdown → price records                              #
    # ------------------------------------------------------------------ #

    def _parse_markdown(self, markdown: str, commodity: str) -> list[dict]:
        records: list[dict] = []
        fetched_at = datetime.utcnow()
        today = date.today()

        # Strategy 1: GFM table rows
        for block in self._split_tables(markdown):
            records.extend(self._parse_table_block(block, commodity, today, fetched_at))

        # Strategy 2: inline "Crop: price" patterns (fallback)
        if not records:
            inline_re = re.compile(
                r"([A-Za-zÀ-ỹ][A-Za-zÀ-ỹ0-9\s\-]{2,50}?)"
                r"\s*[:\-–]\s*(\d[\d.,]{2,})"
                r"\s*(?:vnđ|vnd|đồng|đ)?\s*(?:/kg|kg)?",
                re.IGNORECASE,
            )
            for match in inline_re.finditer(markdown):
                crop = match.group(1).strip()
                price = _parse_number(match.group(2))
                if not crop or price is None:
                    continue
                records.append(self._build(crop, "Việt Nam", price, today, fetched_at))

        return records

    @staticmethod
    def _split_tables(markdown: str) -> list[str]:
        blocks, current = [], []
        for line in markdown.splitlines():
            if line.strip().startswith("|"):
                current.append(line)
            else:
                if current:
                    blocks.append("\n".join(current))
                    current = []
        if current:
            blocks.append("\n".join(current))
        return blocks

    def _parse_table_block(
        self,
        block: str,
        commodity: str,
        price_date: date,
        fetched_at: datetime,
    ) -> list[dict]:
        lines = [l for l in block.splitlines() if l.strip().startswith("|")]
        if len(lines) < 2:
            return []

        headers = [c.strip().lower() for c in lines[0].split("|") if c.strip()]
        crop_col   = _find_col(headers, ("tên", "hàng hóa", "nông sản", "sản phẩm", "loại", "mặt hàng"))
        price_col  = _find_col(headers, ("giá", "đơn giá", "price", "giá bán"))
        region_col = _find_col(headers, ("vùng", "tỉnh", "địa phương", "khu vực", "nơi", "thị trường"))
        date_col   = _find_col(headers, ("ngày", "thời gian", "date"))

        if crop_col is None or price_col is None:
            return []

        records: list[dict] = []
        for line in lines[2:]:
            cells = [c.strip() for c in line.split("|") if c.strip() != ""]
            if len(cells) <= max(crop_col, price_col):
                continue
            crop   = cells[crop_col]
            price  = _parse_number(cells[price_col])
            region = cells[region_col] if region_col is not None and region_col < len(cells) else "Việt Nam"
            row_date = price_date
            if date_col is not None and date_col < len(cells):
                parsed = _parse_date(cells[date_col])
                if parsed:
                    row_date = parsed
            if not crop or price is None:
                continue
            records.append(self._build(crop, region, price, row_date, fetched_at))
        return records

    def _build(
        self,
        crop_name: str,
        region: str,
        price: float,
        price_date: date,
        fetched_at: datetime,
    ) -> dict:
        return {
            "crop_name": crop_name,
            "region": _normalize_region(region),
            "price": price,
            "price_date": price_date,
            "quality_grade": "grade_1",
            "market_type": "Ban le",
            "source_name": self.SOURCE_NAME,
            "source_url": _FORM_URL,
            "is_realtime": True,
            "is_mock": False,
            "fetched_at": fetched_at,
        }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_number(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(text).replace(",", ""))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _parse_date(text: str) -> date | None:
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text.strip()[:10], fmt).date()
        except ValueError:
            continue
    return None


def _find_col(headers: list[str], keywords: tuple[str, ...]) -> int | None:
    for i, h in enumerate(headers):
        if any(kw in h for kw in keywords):
            return i
    return None


firecrawl_price_client = FirecrawlPriceClient()
