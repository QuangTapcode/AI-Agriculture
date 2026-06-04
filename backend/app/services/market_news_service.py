from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
import threading
import unicodedata
import logging


from app.core.config import settings
from app.core.database import SessionLocal
from app.core.real_data import OFFICIAL_AGRI_SOURCE_NAME, OFFICIAL_NEWS_URL, cache_status_for, realtime_error
from app.core.redis_client import redis_client
from app.integrations.thitruong_nongsan_news_client import thitruong_nongsan_news_client
from app.integrations.tavily_news_client import tavily_news_client
from app.integrations.rss_client import rss_client

from app.repositories.ingestion_repository import finish_ingestion_log, start_ingestion_log
from app.repositories.market_news_repository import list_market_news, upsert_market_news
from app.services.pricing_service import pricing_service

logger = logging.getLogger(__name__)


def _norm_dedupe_text(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def _market_news_dedupe_key(title: str | None, source_url: str | None) -> str:
    # requirement: dedupe by source_url/title
    return f"{_norm_dedupe_text(source_url)}|{_norm_dedupe_text(title)}"


class MarketNewsService:
    LATEST_CACHE_PREFIX = "market_news:latest:agriculture"
    LATEST_WINDOW_DAYS = 30  # 30 days — covers VNExpress nong-nghiep feature articles (updated weekly)
    AGRICULTURE_NEWS_KEYWORDS = (
        # Ngành nông nghiệp chung
        "nông nghiệp",
        "nông sản",
        "sản xuất nông nghiệp",
        "trồng trọt",
        "canh tác",
        "cây trồng",
        "mùa vụ",
        "gieo trồng",
        "thu hoạch",
        "đồng ruộng",
        "nhà vườn",
        "nông dân",
        "hợp tác xã",
        # Cây lương thực — dùng multi-word để tránh "lúa"→"lua" collision với "tên lửa"→"ten lua"
        "gạo",
        "lúa gạo",
        "giá gạo",
        "giá lúa",
        "cây lúa",
        "hạt lúa",
        "trồng lúa",
        "thu hoạch lúa",
        # Rau củ
        "rau màu",
        "rau củ",
        "rau quả",
        "cà phê",
        "hồ tiêu",
        "sầu riêng",
        "thanh long",
        "xoài",
        "cà chua",
        "dưa chuột",
        "dưa hấu",
        "bưởi",
        "vải thiều",
        "nhãn lồng",
        # Vật tư nông nghiệp
        "phân bón",
        "sâu bệnh",
        "dịch bệnh cây",
        "thuốc bảo vệ thực vật",
        "thủy lợi",
        "hạn hán",
        "mưa bão nông",
        # Thị trường nông sản (cụm từ cụ thể, tránh match "xuất khẩu" đơn lẻ)
        "xuất khẩu nông sản",
        "xuất khẩu gạo",
        "xuất khẩu cà phê",
        "xuất khẩu trái cây",
        "xuất khẩu thủy sản",
        "giá nông sản",
        "thị trường nông sản",
        "giá cả nông sản",
        # Chăn nuôi và thủy sản
        "chăn nuôi",
        "thủy sản",
        "nuôi trồng",
        "trái cây",
        "cây ăn quả",
        "gia cầm",
        "gia súc",
        "con tôm",
        "nuôi tôm",
        "mía đường",
        "cây mía",
        "cây sắn",       # tránh "san" match "bất động sản"
        "cây chè",       # tránh "che" match các từ khác
        "hạt điều",      # tránh "dieu" match "điều hành", "điều chỉnh"
        "cao su",
        "cây dừa",
        "nông thôn",
        "nông lâm",
        "nông lâm nghiệp",
    )

    def refresh_news(self) -> dict:
        db = SessionLocal()
        log = start_ingestion_log(db, "refresh_market_news", OFFICIAL_AGRI_SOURCE_NAME)
        try:
            official_records = (
                thitruong_nongsan_news_client.fetch_latest_news(limit=40)
                if settings.ENABLE_MARKET_NEWS
                else []
            )

            # RSS feeds (VNExpress, etc.) — không cần API key, luôn khả dụng
            rss_records: list[dict] = []
            try:
                rss_records = rss_client.fetch_market_news()
            except Exception as exc:
                logger.warning("[MarketNewsService] RSS failed: %s", exc)

            # Tavily chỉ là nguồn bổ sung (không thay nguồn chính).
            tavily_records: list[dict] = []
            try:
                if getattr(settings, "TAVILY_ENABLED", True):
                    tavily_records = tavily_news_client.search_agriculture_news(limit=20)
            except Exception as exc:
                logger.warning("[MarketNewsService] Tavily failed: %s", exc)
                tavily_records = []

            fetched_records = list(official_records or []) + list(rss_records or []) + list(tavily_records or [])

            official_records = self._filter_relevant_news((official_records or []), since=self._recent_since())
            # RSS uses softer filter (no keyword check) — sources are already agriculture-focused
            rss_records = self._filter_rss_news((rss_records or []), since=self._recent_since())
            tavily_records = self._filter_relevant_news((tavily_records or []), since=self._recent_since())

            records = self._merge_dedupe_news(official_records + rss_records, tavily_records)

            result = upsert_market_news(db, records)
            self._clear_latest_cache()
            finish_ingestion_log(
                db,
                log,
                status="success",
                records_fetched=(len(official_records) + len(rss_records) + len(tavily_records)),
                records_saved=result["records_saved"] + result["records_updated"],
            )
            return {
                "status": "success",
                "records_fetched": len(fetched_records),
                "records_filtered": len(records),
                "source": "realtime_api" if fetched_records else "cache",
                "source_name": OFFICIAL_AGRI_SOURCE_NAME,
                "source_url": OFFICIAL_NEWS_URL,
                "is_mock": False,
                "fetched_at": datetime.utcnow().isoformat(),
                **result,
            }
        except Exception as exc:
            finish_ingestion_log(db, log, status="failed", error_message=str(exc))
            return {"status": "failed", "error": str(exc), "records_fetched": 0, "records_saved": 0, "is_mock": False}
        finally:
            db.close()

    def get_latest(self, db, limit: int = 20, crop_name: str | None = None, region: str | None = None) -> dict:
        since = self._recent_since()
        cache_key = (
            f"{self.LATEST_CACHE_PREFIX}:{limit}:{self.LATEST_WINDOW_DAYS}d"
            if not crop_name and not region
            else None
        )
        cached = redis_client.get(cache_key) if cache_key else None
        if cached:
            return {**cached, "cache_status": "fresh_cache"}

        fetch_limit = max(limit * 5, 20)
        rows = self._filter_relevant_news(
            list_market_news(db, limit=fetch_limit, crop_name=crop_name, region=region, since=since),
            since=since,
        )

        # If realtime miss: try a live refresh once, then fall back to general news.
        if not rows:
            try:
                self.refresh_news()
                db.expire_all()
                rows = self._filter_relevant_news(
                    list_market_news(db, limit=fetch_limit, crop_name=crop_name, region=region, since=since),
                    since=since,
                )
            except Exception as exc:
                logger.warning("[MarketNewsService] inline refresh failed: %s", exc)

        # If crop/region filtered news is still empty, fall back to general agriculture news
        if not rows and (crop_name or region):
            rows = self._filter_relevant_news(
                list_market_news(db, limit=fetch_limit, since=since),
                since=since,
            )

        if not rows:
            if cached:
                return {**cached, "cache_status": "fresh_cache"}
            payload = realtime_error(
                code="MARKET_NEWS_CACHE_MISS",
                message="Market news cache miss. Background refresh has not fetched fresh real data yet.",
                source_name=OFFICIAL_AGRI_SOURCE_NAME,
                source_url=OFFICIAL_NEWS_URL,
            )
            payload["news"] = []
            return payload


        newest_fetched = rows[0].FetchedAt or rows[0].CreatedAt or datetime.utcnow()
        cache_status = cache_status_for(newest_fetched, "market_news")
        if cache_status == "miss":
            # FetchedAt is old but news items are still within publication window — show them with a warning,
            # and trigger a background refresh so future requests get fresh data.
            try:
                self.refresh_news()
                db.expire_all()
                fresh_rows = self._filter_relevant_news(
                    list_market_news(db, limit=fetch_limit, crop_name=crop_name, region=region, since=since),
                    since=since,
                )
                if fresh_rows:
                    rows = fresh_rows
                    newest_fetched = rows[0].FetchedAt or rows[0].CreatedAt or datetime.utcnow()
                    cache_status = cache_status_for(newest_fetched, "market_news")
            except Exception as exc:
                logger.warning("[MarketNewsService] expired-cache refresh failed: %s", exc)
            # Fall back to general news if crop/region filtered fresh rows are empty
            if cache_status == "miss" and (crop_name or region):
                try:
                    general_rows = self._filter_relevant_news(
                        list_market_news(db, limit=fetch_limit, since=since),
                        since=since,
                    )
                    if general_rows:
                        rows = general_rows
                        newest_fetched = rows[0].FetchedAt or rows[0].CreatedAt or datetime.utcnow()
                        cache_status = cache_status_for(newest_fetched, "market_news")
                except Exception:
                    pass
            # If still miss, show stale data rather than an error
            if cache_status == "miss":
                cache_status = "stale_cache"
        response = {
            "news": self._dedupe_and_order_news([self._to_dict(row) for row in rows[:limit]]),
            "source": "cache",
            "source_name": rows[0].SourceName if rows and rows[0].SourceName else OFFICIAL_AGRI_SOURCE_NAME,
            "source_url": OFFICIAL_NEWS_URL,
            "is_realtime": False,
            "is_mock": False,
            "window_days": self.LATEST_WINDOW_DAYS,
            "cache_status": cache_status,
            "fetched_at": newest_fetched,
            "last_updated": newest_fetched,
            "data_age_minutes": int((datetime.utcnow() - newest_fetched).total_seconds() // 60) if newest_fetched else None,
            "warning": "Đang hiển thị tin tức đã lưu. Đang cập nhật tin mới." if cache_status == "stale_cache" else None,
            "metadata": {
                "source_type": "cache",
                "source_name": rows[0].SourceName if rows and rows[0].SourceName else OFFICIAL_AGRI_SOURCE_NAME,
                "source_url": OFFICIAL_NEWS_URL,
                "fetched_at": newest_fetched.isoformat() if hasattr(newest_fetched, "isoformat") else newest_fetched,
                "cache_status": cache_status,
                "is_mock": False,
            },
        }
        if cache_key:
            redis_client.set(cache_key, response, expire=int(settings.NEWS_CACHE_TTL_MINUTES or 120) * 60)
        return response

    @staticmethod
    def _realtime_only() -> bool:
        return bool(settings.USE_REALTIME_ONLY) and not bool(settings.ALLOW_MOCK_DATA or settings.ALLOW_SAMPLE_DATA)

    # _fallback_news removed (no mock data allowed)

    def _filter_agriculture_news(self, items):
        return [item for item in (items or []) if self._is_agriculture_production_news(item)]

    def _filter_rss_news(self, items, since: datetime):
        """Filter RSS records at ingest: only drop corrupt or too-old articles.
        Keyword check is skipped because we use agriculture-focused RSS sources."""
        return [
            item
            for item in (items or [])
            if self._is_recent_news(item, since)
            and not self._has_text_corruption(item)
        ]

    def _filter_relevant_news(self, items, since: datetime):
        return [
            item
            for item in (items or [])
            if self._is_recent_news(item, since)
            and self._is_agriculture_production_news(item)
            and not self._has_text_corruption(item)
        ]

    def _merge_dedupe_news(self, official_records: list[dict], tavily_records: list[dict]) -> list[dict]:
        """Gộp + loại trùng theo source_url/title. Tin official luôn ưu tiên hiển thị trước."""
        merged: list[dict] = []
        seen: set[str] = set()

        def _push(item: dict):
            key = _market_news_dedupe_key(item.get("title"), item.get("source_url") or item.get("url"))
            if key in seen:
                return
            seen.add(key)
            merged.append(item)

        for it in (official_records or []):
            _push(it)
        for it in (tavily_records or []):
            _push(it)
        return merged

    def _dedupe_and_order_news(self, items: list[dict]) -> list[dict]:
        """Trong dữ liệu cache/DB, loại trùng theo source_url/title và đảm bảo official ở trước Tavily."""
        seen: set[str] = set()
        official: list[dict] = []
        others: list[dict] = []
        for it in (items or []):
            title = it.get("title")
            source_url = it.get("source_url")
            key = _market_news_dedupe_key(title, source_url)
            if key in seen:
                continue
            seen.add(key)
            src_url = (source_url or "").lower()
            if OFFICIAL_NEWS_URL.lower() in src_url or "thitruongnongsan.gov.vn" in src_url:
                official.append(it)
            else:
                others.append(it)
        return official + others



    def _has_text_corruption(self, item) -> bool:
        text = " ".join(
            str(self._get_value(item, field) or "")
            for field in (
                "title",
                "summary",
                "source_name",
                "Title",
                "Summary",
                "SourceName",
            )
        )
        if "\ufffd" in text:
            return True
        return bool(re.search(r"[A-Za-zÀ-ỹ]\?[A-Za-zÀ-ỹ]", text) or text.count("?") >= 3)

    def _is_recent_news(self, item, since: datetime) -> bool:
        published_at = self._get_value(item, "published_at") or self._get_value(item, "PublishedAt")
        if isinstance(published_at, str):
            try:
                published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            except ValueError:
                return False
        if not isinstance(published_at, datetime):
            return False
        if published_at.tzinfo:
            published_at = published_at.astimezone(timezone.utc).replace(tzinfo=None)
        return published_at >= since

    def _is_agriculture_production_news(self, item) -> bool:
        haystack = self._normalize_text(" ".join(
            str(self._get_value(item, field) or "")
            for field in (
                "title",
                "summary",
                "source_name",
                "Title",
                "Summary",
                "SourceName",
            )
        ))
        return any(self._keyword_matches(self._normalize_text(keyword), haystack) for keyword in self.AGRICULTURE_NEWS_KEYWORDS)

    @staticmethod
    def _keyword_matches(norm_keyword: str, haystack: str) -> bool:
        """Match keyword in haystack.

        Single-word keywords use word-boundary check to avoid diacritic-strip
        collisions (e.g. "lúa"→"lua" matching "lửa"→"lua" in "tên lửa").
        Multi-word keywords use plain substring match (spaces already act as boundaries).
        """
        if " " not in norm_keyword:
            # Pad haystack so boundary check works at string edges
            return (" " + norm_keyword + " ") in (" " + haystack + " ")
        return norm_keyword in haystack

    @staticmethod
    def _normalize_text(value: str) -> str:
        normalized = unicodedata.normalize("NFD", value.lower()).replace("đ", "d")
        return "".join(char for char in normalized if unicodedata.category(char) != "Mn")

    @staticmethod
    def _get_value(item, field: str):
        if isinstance(item, dict):
            return item.get(field)
        return getattr(item, field, None)

    def _clear_latest_cache(self) -> None:
        redis_client.delete("market_news:latest")
        redis_client.delete(self.LATEST_CACHE_PREFIX)
        for limit in (4, 6, 20):
            redis_client.delete(f"{self.LATEST_CACHE_PREFIX}:{limit}")
            redis_client.delete(f"{self.LATEST_CACHE_PREFIX}:{limit}:{self.LATEST_WINDOW_DAYS}d")

    def _recent_since(self) -> datetime:
        return datetime.utcnow() - timedelta(days=self.LATEST_WINDOW_DAYS)

    @staticmethod
    def _repair_mojibake(value: str | None) -> str | None:
        """
        Fix common Vietnamese mojibake from bad RSS encodings, e.g.:
        - Ã¢â€žÂ¢, Ã©, Â, â€™, Ã¼ ...
        by trying latin1->utf-8 decode when the string looks corrupted.
        """
        if value is None:
            return None

        if not isinstance(value, str) or not value:
            return value

        looks_mojibake = any(token in value for token in ["Ã", "Â", "â€™", "â€œ", "â€", "â€“", "â€ž"])
        if not looks_mojibake:
            return value

        try:
            # Undo the typical "wrongly decoded as latin1 then interpreted as utf-8" pattern.
            return value.encode("latin1", errors="ignore").decode("utf-8", errors="replace")
        except Exception:
            return value

    @staticmethod
    def _to_dict(row) -> dict:
        crop_tags = MarketNewsService._as_list(row.CropTags)
        region_tags = MarketNewsService._as_list(row.RegionTags) or ([row.Region] if row.Region else [])
        impact_score = row.ImpactScore if row.ImpactScore is not None else 0.5
        return {
            "news_id": row.NewsID,
            "title": MarketNewsService._repair_mojibake(row.Title),
            "summary": MarketNewsService._repair_mojibake(row.Summary),
            "content": MarketNewsService._repair_mojibake(row.Content),
            "url": row.URL or row.SourceURL,
            "source_name": MarketNewsService._repair_mojibake(row.SourceName),
            "source_url": row.SourceURL,
            "published_at": row.PublishedAt.isoformat() if row.PublishedAt else None,
            "fetched_at": (row.FetchedAt or row.CreatedAt or datetime.utcnow()).isoformat(),
            "region": row.Region,
            "crop_tags": crop_tags,
            "region_tags": region_tags,
            "affected_crops": crop_tags,
            "affected_regions": region_tags,
            "sentiment": row.Sentiment,
            "impact": row.Sentiment or "neutral",
            "impact_level": row.ImpactLevel or MarketNewsService._impact_level(impact_score),
            "impact_score": impact_score,
            "price_effect": "likely_increase" if row.Sentiment == "positive" else "likely_decrease" if row.Sentiment == "negative" else "stable",
            "source": "cache",
            "updated_at": row.PublishedAt.isoformat() if row.PublishedAt else None,
            "confidence": 0.76 if row.IsRealtime else 0.7,
            "is_realtime": False,
            "is_mock": False,
            "cache_status": cache_status_for(row.FetchedAt or row.CreatedAt, "market_news"),
        }

    @staticmethod
    def _as_list(value) -> list:
        if isinstance(value, list):
            return value
        if isinstance(value, str) and value.strip():
            return [part.strip() for part in value.strip("[]").replace('"', "").split(",") if part.strip()]
        return []

    def get_market_news(self, db, crop: str | None = None, region: str | None = None, limit: int = 10) -> dict:
        return self.get_latest(db, limit=limit, crop_name=crop, region=region)

    def analyze_news_impact(self, news_item: dict) -> dict:
        text = f"{news_item.get('title', '')} {news_item.get('summary', '')}".lower()
        positive_words = ("tang", "xuat khau", "don hang", "duoc gia", "co hoi")
        negative_words = ("giam", "dich", "bao", "han", "thua", "rui ro")
        score = sum(word in text for word in positive_words) - sum(word in text for word in negative_words)
        impact = "positive" if score > 0 else "negative" if score < 0 else "neutral"
        return {
            "impact": impact,
            "impact_score": 0.68 if impact != "neutral" else 0.5,
            "price_effect": "likely_increase" if impact == "positive" else "likely_decrease" if impact == "negative" else "stable",
            "source": "ai_generated",
            "source_name": "News impact rule engine",
            "confidence": 0.58,
            "updated_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _impact_level(score: float) -> str:
        if score >= 0.75:
            return "high"
        if score >= 0.55:
            return "medium"
        return "low"

    def get_market_trends(self, db, crop: str | None = None, region: str | None = None) -> dict:
        """
        Trả phân tích xu hướng dựa trên dữ liệu thật từ DB.
        Không được phép "lộ" mock từ pricing_service qua is_mock/source="mock".
        """
        selected_crop = crop or "lua"
        selected_region = region or "Ha Noi"

        pricing = pricing_service.get_ai_price_recommendation(db, selected_crop, selected_region)

        # Cưỡng ép anti-mock: market news public luôn trả is_mock=false và không cho source="mock"
        return {
            "crop": selected_crop,
            "crop_name": selected_crop,
            "region": selected_region,
            "trend": pricing.get("trend", "stable"),
            "confidence": pricing.get("confidence", 0.0),
            "evidence": pricing.get("reasons", []),
            "forecast": pricing.get("forecast", []),
            "recommendation": pricing.get("recommendation"),
            "source": "ai_generated",
            "source_name": "Market trend engine",
            "is_mock": False,
            "cache_status": pricing.get("cache_status", "computed"),
            "updated_at": datetime.utcnow().isoformat(),
        }

    def get_market_opportunities(self, db, crop: str | None = None, region: str | None = None) -> dict:
        trend = self.get_market_trends(db, crop=crop, region=region)
        return {
            "opportunities": [
                {
                    "title": "Cơ hội bán theo từng đợt",
                    "crop": trend["crop"],
                    "region": trend["region"],
                    "reason": trend.get("recommendation"),
                    "confidence": trend.get("confidence", 0.0),
                    "source": trend.get("source"),
                    "source_name": trend.get("source_name"),
                    "updated_at": trend.get("updated_at"),
                }
            ],
            "source": trend.get("source"),
            "source_name": "Phân tích thị trường AI",
            "is_mock": trend.get("is_mock", False),
            "confidence": trend.get("confidence", 0.0),
            "updated_at": trend.get("updated_at"),
        }

    def get_market_risks(self, db, crop: str | None = None, region: str | None = None) -> dict:
        trend = self.get_market_trends(db, crop=crop, region=region)
        risk = "high" if trend.get("trend") == "decreasing" else "medium" if trend.get("is_mock") else "low"
        return {
            "risks": [
                {
                    "title": "Biến động giá",
                    "severity": risk,
                    "crop": trend["crop"],
                    "region": trend["region"],
                    "recommendation": "Nên tạo cảnh báo giá và tránh bán hết hàng cùng một lúc.",
                    "source": trend.get("source"),
                    "source_name": "Bộ phân tích rủi ro thị trường",
                    "updated_at": trend.get("updated_at"),
                }
            ],
            "source": trend.get("source"),
            "source_name": "Bộ phân tích rủi ro thị trường",
            "is_mock": trend.get("is_mock", False),
            "confidence": trend.get("confidence", 0.0),
            "updated_at": trend.get("updated_at"),
        }


market_news_service = MarketNewsService()
