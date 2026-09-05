import html
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

from app.core.config import settings
from app.core.real_data import external_circuit_breaker
from app.core.resilience import build_timeout, resilient_request


class RSSClient:
    def fetch_market_news(self) -> list[dict]:
        records: list[dict] = []
        urls = self._feed_urls()
        with ThreadPoolExecutor(max_workers=min(len(urls), 4) or 1) as executor:
            futures = [executor.submit(self._fetch_feed, url) for url in urls]
            for future in as_completed(futures):
                try:
                    records.extend(future.result())
                except Exception:
                    continue
        return records

    def _feed_urls(self) -> list[str]:
        try:
            urls = json.loads(settings.MARKET_NEWS_RSS_URLS_JSON or "[]")
        except json.JSONDecodeError:
            urls = []
        return [url for url in urls if isinstance(url, str) and url.startswith(("http://", "https://"))]

    def _fetch_feed(self, url: str) -> list[dict]:
        # Nguon RSS chet ma van goi lai mai thi moi luot ton tron thoi gian
        # timeout — dung kieu da do o /api/chat (3.18s moi luot). Circuit
        # breaker dung chung voi price/news client: du so lan hong thi ngung
        # goi trong mot khoang thay vi hanh nguon da chet.
        key = f"rss_feed:{self._host_name(url)}"
        external_circuit_breaker.before_call(key)
        try:
            response = resilient_request(
                "GET",
                url,
                timeout=build_timeout(total=20, connect=5, read=10),
                retries=2,
                service_name="RSS market news",
            )
        except Exception as exc:
            external_circuit_breaker.record_failure(key, exc)
            raise
        external_circuit_breaker.record_success(key)
        root = ElementTree.fromstring(response.content)
        channel_title = root.findtext("./channel/title") or self._host_name(url)
        records = []
        for item in root.findall("./channel/item")[:30]:
            title = html.unescape(item.findtext("title") or "").strip()
            link = html.unescape(item.findtext("link") or "").strip()
            description = self._clean_html(item.findtext("description") or "")
            published_at = self._parse_datetime(item.findtext("pubDate"))
            if not title or not link:
                continue
            records.append(
                {
                    "title": title,
                    "summary": description,
                    "source_name": channel_title,
                    "source_url": link,
                    "published_at": published_at,
                    "sentiment": self._sentiment(title + " " + description),
                    "is_realtime": True,
                    "fetched_at": datetime.utcnow(),
                }
            )
        return records

    @staticmethod
    def _clean_html(value: str) -> str:
        text = html.unescape(value)
        try:
            text = ElementTree.fromstring(f"<root>{text}</root>").itertext()
            return " ".join(part.strip() for part in text if part.strip())[:600]
        except ElementTree.ParseError:
            import re

            return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()[:600]

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return parsedate_to_datetime(value).replace(tzinfo=None)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _sentiment(text: str) -> str:
        lowered = text.lower()
        if any(word in lowered for word in ("tang", "tăng", "cao", "ky luc", "kỷ lục", "phuc hoi", "phục hồi")):
            return "positive"
        if any(word in lowered for word in ("giam", "giảm", "thap", "thấp", "rui ro", "rủi ro", "ap luc", "áp lực")):
            return "negative"
        return "neutral"

    @staticmethod
    def _host_name(url: str) -> str:
        return url.split("//", 1)[-1].split("/", 1)[0]


rss_client = RSSClient()
