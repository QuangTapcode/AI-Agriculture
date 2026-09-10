"""
Validate and clean raw price records from crawlers before DB write.

Public interface:
    clean_price_records(records)              -> (clean: list[dict], rejected: list[dict])
    save_quarantine(rejected, source)         -> None  (append to JSONL file)
    warn_count_mismatch(source, n_clean, res) -> None  (log warning if saved << clean)
    normalize_region(name)                    -> str
    normalize_crop(name)                      -> str
"""
from __future__ import annotations

import json
import logging
import unicodedata
from datetime import date, datetime
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---- price bounds --------------------------------------------------------
_PRICE_MIN = 200.0
_PRICE_MAX = 10_000_000.0

# ---- canonical region names ----------------------------------------------
_REGION_ALIASES: dict[str, str] = {
    "tp hcm": "TP.HCM", "ho chi minh": "TP.HCM", "tp.hcm": "TP.HCM",
    "tphcm": "TP.HCM", "hcm": "TP.HCM", "sai gon": "TP.HCM", "saigon": "TP.HCM",
    "thanh pho ho chi minh": "TP.HCM",
    "ha noi": "Hà Nội", "hanoi": "Hà Nội", "hn": "Hà Nội", "ha noi": "Hà Nội",
    "can tho": "Cần Thơ", "cantho": "Cần Thơ",
    "da nang": "Đà Nẵng", "danang": "Đà Nẵng",
    "lam dong": "Lâm Đồng", "lamdong": "Lâm Đồng", "da lat": "Lâm Đồng",
    "hai phong": "Hải Phòng", "haiphong": "Hải Phòng",
    "dak lak": "Đắk Lắk", "dac lac": "Đắk Lắk",
    "dak nong": "Đắk Nông",
    "gia lai": "Gia Lai",
    "kon tum": "Kon Tum",
    "binh phuoc": "Bình Phước",
    "dong nai": "Đồng Nai",
    "binh duong": "Bình Dương",
    "tay ninh": "Tây Ninh",
    "tien giang": "Tiền Giang",
    "dong thap": "Đồng Tháp",
    "an giang": "An Giang",
    "kien giang": "Kiên Giang",
    "long an": "Long An",
    "binh thuan": "Bình Thuận",
    "vinh long": "Vĩnh Long",
    "soc trang": "Sóc Trăng",
    "hau giang": "Hậu Giang",
    "ben tre": "Bến Tre",
    "tra vinh": "Trà Vinh",
    "hai duong": "Hải Dương",
    "hung yen": "Hưng Yên",
    "bac giang": "Bắc Giang",
    "nghe an": "Nghệ An",
    "binh dinh": "Bình Định",
    "khanh hoa": "Khánh Hòa",
    "quang ngai": "Quảng Ngãi",
    "son la": "Sơn La",
    "ha giang": "Hà Giang",
}

# ---- canonical crop names ------------------------------------------------
# Mirrors _CROP_ALIAS in crawler_tasks.py — source of truth for normalization.
# Key: stripped+lowercased variant.  Value: canonical Vietnamese name in DB.
_CROP_ALIASES: dict[str, str] = {
    # Sầu riêng
    "sầu riêng": "Sầu riêng", "sau rieng": "Sầu riêng", "durian": "Sầu riêng",
    "musang king": "Sầu riêng", "ri6": "Sầu riêng", "monthong": "Sầu riêng",
    # Xoài
    "xoài": "Xoài", "xoai": "Xoài", "mango": "Xoài",
    # Thanh long
    "thanh long": "Thanh long", "dragon fruit": "Thanh long",
    # Chuối
    "chuối": "Chuối", "chuoi": "Chuối", "banana": "Chuối",
    # Dứa
    "dứa": "Dứa", "dua": "Dứa", "khóm": "Dứa", "pineapple": "Dứa",
    # Dưa hấu
    "dưa hấu": "Dưa hấu", "dua hau": "Dưa hấu", "watermelon": "Dưa hấu",
    # Bơ
    "bơ": "Bơ", "avocado": "Bơ",
    # Mít
    "mít": "Mít", "mit": "Mít", "jackfruit": "Mít",
    # Nhãn
    "nhãn": "Nhãn", "nhan": "Nhãn", "longan": "Nhãn",
    # Vải
    "vải": "Vải", "vai": "Vải", "lychee": "Vải", "litchi": "Vải",
    # Cam
    "cam": "Cam", "orange": "Cam",
    # Bưởi
    "bưởi": "Bưởi", "buoi": "Bưởi", "pomelo": "Bưởi",
    # Cà chua
    "cà chua": "Cà chua", "ca chua": "Cà chua", "tomato": "Cà chua",
    # Rau muống
    "rau muống": "Rau muống", "rau muong": "Rau muống",
    # Rau cải
    "rau cải": "Rau cải", "cải xanh": "Rau cải", "cải ngọt": "Rau cải",
    # Cải bắp
    "cải bắp": "Cải bắp", "bắp cải": "Cải bắp", "cabbage": "Cải bắp",
    # Hành lá
    "hành lá": "Hành lá", "hanh la": "Hành lá", "spring onion": "Hành lá",
    # Hành tây
    "hành tây": "Hành tây", "hanh tay": "Hành tây", "onion": "Hành tây",
    # Tỏi
    "tỏi": "Tỏi", "toi": "Tỏi", "garlic": "Tỏi",
    # Gừng
    "gừng": "Gừng", "gung": "Gừng", "ginger": "Gừng",
    # Cà rốt
    "cà rốt": "Cà rốt", "ca rot": "Cà rốt", "carrot": "Cà rốt",
    # Khoai tây
    "khoai tây": "Khoai tây", "khoai tay": "Khoai tây", "potato": "Khoai tây",
    # Khoai lang
    "khoai lang": "Khoai lang", "sweet potato": "Khoai lang",
    # Ớt
    "ớt": "Ớt", "ot": "Ớt", "chili": "Ớt",
    # Bí đỏ
    "bí đỏ": "Bí đỏ", "bi do": "Bí đỏ", "pumpkin": "Bí đỏ", "bí ngô": "Bí đỏ",
    # Lúa / Gạo
    "lúa": "Lúa", "lua": "Lúa", "thóc": "Lúa", "gạo": "Lúa",
    "lúa jasmine": "Lúa", "lúa ir50404": "Lúa",
    "ir 50404": "Lúa", "ir50404": "Lúa", "jasmine": "Lúa",
    "om 18": "Lúa", "om18": "Lúa", "clc 4900": "Lúa",
    # Ngô
    "ngô": "Ngô", "ngo": "Ngô", "bắp": "Ngô", "corn": "Ngô",
    # Cà phê
    "cà phê": "Cà phê", "ca phe": "Cà phê", "coffee": "Cà phê",
    "cafe": "Cà phê", "café": "Cà phê",
    "cà phê robusta": "Cà phê", "ca phe robusta": "Cà phê",
    "cà phê arabica": "Cà phê", "robusta": "Cà phê", "arabica": "Cà phê",
    # Hồ tiêu
    "hồ tiêu": "Hồ tiêu", "ho tieu": "Hồ tiêu", "tiêu": "Hồ tiêu",
    "pepper": "Hồ tiêu",
    # Điều
    "điều": "Điều", "dieu": "Điều", "cashew": "Điều", "hạt điều": "Điều",
    # Mía
    "mía": "Mía", "mia": "Mía", "sugarcane": "Mía",
    # Cao su
    "cao su": "Cao su", "rubber": "Cao su",
    # Chè
    "chè": "Chè", "che": "Chè", "tea": "Chè",
}

# Pre-built accent-stripped lookup for O(1) exact match and fast substring scan
_CROP_ALIAS_NORM: dict[str, str] = {}   # filled after _strip_accents is defined

# UTF-8 corruption markers found in Vietnamese RSS / scraped sources
_MOJIBAKE_MARKERS = ("Ã", "â€", "Â", "â€™", "â€œ")


def _strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower()).replace("đ", "d")
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# Build after _strip_accents is defined: accent-stripped alias → canonical
_CROP_ALIAS_NORM = {_strip_accents(k): v for k, v in _CROP_ALIASES.items()}


def normalize_region(name: str | None) -> str:
    """Map crawler region variants to canonical region string."""
    if not name:
        return "Toàn quốc"
    key = _strip_accents(name.strip())
    return _REGION_ALIASES.get(key, name.strip())


def normalize_crop(name: str | None) -> str:
    """Map crop name variants to canonical Vietnamese name.

    Comparison is accent-insensitive: "thoc" matches "thóc", "lua" matches "lúa".

    Strategy:
    1. Exact match on accent-stripped form
    2. Substring match on accent-stripped form (aliases >= 4 chars only, avoids false positives)
    3. Return original if no match found
    """
    if not name:
        return ""
    key = _strip_accents(name.strip())
    if key in _CROP_ALIAS_NORM:
        return _CROP_ALIAS_NORM[key]
    for alias_norm, canonical in _CROP_ALIAS_NORM.items():
        if len(alias_norm) >= 4 and (alias_norm in key or key in alias_norm):
            return canonical
    return name.strip()


def normalize_crop_strict(name: str | None) -> str | None:
    """Like normalize_crop but returns None when no alias match is found.

    Used by crawler_tasks where unknown crops should be filtered out rather
    than passed through with the original name.
    """
    if not name:
        return None
    key = _strip_accents(name.strip())
    if key in _CROP_ALIAS_NORM:
        return _CROP_ALIAS_NORM[key]
    for alias_norm, canonical in _CROP_ALIAS_NORM.items():
        if len(alias_norm) >= 4 and (alias_norm in key or key in alias_norm):
            return canonical
    return None


def _is_text_corrupt(text: str) -> bool:
    """Return True if text contains UTF-8 replacement chars or common mojibake."""
    if "�" in text:
        return True
    if any(marker in text for marker in _MOJIBAKE_MARKERS):
        return True
    return False


def _parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value if not isinstance(value, datetime) else value.date()
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(value[:10], fmt).date()
            except ValueError:
                continue
    return None


def _co_chu_so(text: str | None) -> bool:
    return any(ky_tu.isdigit() for ky_tu in (text or ""))


def _reject(record: dict, reason: str) -> dict:
    return {**record, "_reject_reason": reason}


def clean_price_records(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Validate and normalise raw crawled price dicts.

    Returns (clean_records, rejected_records).
    Each rejected dict has an added '_reject_reason' key.
    """
    clean: list[dict] = []
    rejected: list[dict] = []
    seen: set[tuple] = set()

    for raw in (records or []):
        record = dict(raw)

        # --- required fields --------------------------------------------
        crop_name = str(record.get("crop_name") or "").strip()
        if not crop_name:
            rejected.append(_reject(record, "missing crop_name"))
            continue

        # --- UTF-8 corruption check ------------------------------------
        region_raw = str(record.get("region") or "")
        if _is_text_corrupt(crop_name) or _is_text_corrupt(region_raw):
            rejected.append(_reject(record, "text_corruption"))
            continue

        # Địa danh không bao giờ chứa chữ số. Có chữ số nghĩa là regex bóc text
        # đã nuốt nhầm — trong DB thật có 'Lắk 04-08-2026 9' với giá 6.433 vì
        # nhóm region ăn cả ngày tháng lẫn chữ số đầu của "96.433". Giá 6.433
        # vẫn nằm trong khoảng hợp lệ nên các chốt khác không bắt được; tên
        # vùng mới là chỗ lộ ra cả dòng đã hỏng.
        if _co_chu_so(region_raw):
            rejected.append(_reject(record, f"region chứa chữ số: {region_raw!r}"))
            continue

        # --- crop name normalization -----------------------------------
        canonical_crop = normalize_crop(crop_name)
        record["crop_name"] = canonical_crop

        # --- price validation ------------------------------------------
        try:
            price = float(record.get("price") or 0)
        except (TypeError, ValueError):
            rejected.append(_reject(record, f"non-numeric price: {record.get('price')!r}"))
            continue

        # Auto-scale: some sources use nghìn đồng/kg (e.g. "65" = 65,000 VND/kg)
        if 1.0 <= price < _PRICE_MIN and price * 1000.0 <= _PRICE_MAX:
            price = price * 1000.0
        if price < _PRICE_MIN:
            rejected.append(_reject(record, f"price {price} < min {_PRICE_MIN}"))
            continue
        if price > _PRICE_MAX:
            rejected.append(_reject(record, f"price {price} > max {_PRICE_MAX}"))
            continue

        # --- date -------------------------------------------------------
        price_date = _parse_date(record.get("price_date"))
        if price_date is None:
            price_date = date.today()
        if price_date > date.today():
            rejected.append(_reject(record, f"future price_date {price_date}"))
            continue

        # --- region normalization ---------------------------------------
        record["region"] = normalize_region(record.get("region"))
        record["price"] = round(price, 2)
        record["price_date"] = price_date

        # --- within-batch dedup (keyed on normalized crop name) --------
        key = (
            canonical_crop.lower(),
            record["region"].lower(),
            price_date,
            str(record.get("quality_grade", "")).lower(),
            str(record.get("market_type", "")).lower(),
        )
        if key in seen:
            rejected.append(_reject(record, "duplicate in batch"))
            continue
        seen.add(key)

        clean.append(record)

    if rejected:
        logger.warning(
            "[DataQuality] %d/%d records rejected. Reasons: %s",
            len(rejected),
            len(records),
            {r["_reject_reason"] for r in rejected},
        )

    return clean, rejected


# ---- Quarantine store ----------------------------------------------------

_QUARANTINE_BASE = Path("storage/raw_crawl/quarantine")

def save_quarantine(rejected: list[dict], source: str) -> None:
    """Append rejected records to a JSONL file for review.

    File: storage/raw_crawl/quarantine/YYYYMMDD.jsonl
    Each line: {"ts": ..., "source": ..., "reason": ..., <record fields>}
    """
    if not rejected:
        return
    try:
        _QUARANTINE_BASE.mkdir(parents=True, exist_ok=True)
        path = _QUARANTINE_BASE / f"{date.today().strftime('%Y%m%d')}.jsonl"
        ts = datetime.utcnow().isoformat()
        with path.open("a", encoding="utf-8") as fh:
            for r in rejected:
                entry = {
                    "ts": ts,
                    "source": source,
                    "reason": r.get("_reject_reason", "unknown"),
                    "crop_name": r.get("crop_name"),
                    "region": r.get("region"),
                    "price": r.get("price"),
                    "price_date": str(r.get("price_date", "")),
                }
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning("[DataQuality] Could not write quarantine log: %s", exc)


# ---- Count reconciliation ------------------------------------------------

def warn_count_mismatch(source: str, n_clean: int, upsert_result: dict) -> None:
    """Log a warning when bulk_upsert saves significantly fewer records than expected.

    Catches silent data loss inside bulk_upsert (crop not found, DB errors, etc.)
    """
    if n_clean == 0:
        return
    saved   = upsert_result.get("records_saved", 0) or 0
    updated = upsert_result.get("records_updated", 0) or 0
    errors  = upsert_result.get("errors") or []
    ratio   = (saved + updated) / n_clean

    if errors:
        logger.warning(
            "[DataQuality] %s: %d upsert error(s): %s",
            source, len(errors), errors[:3],
        )
    if ratio < settings.PRICE_SAVE_RATIO_WARN_THRESHOLD:
        logger.warning(
            "[DataQuality] %s: only %d/%d records saved (%.0f%%) — possible crop/region mismatch",
            source, saved + updated, n_clean, ratio * 100,
        )
