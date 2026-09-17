"""Ephemeral browser search used to expand discovery after RAG has no answer."""

import ipaddress
import logging
import base64
from urllib.parse import parse_qs, quote_plus, urldefrag, urlparse

from bs4 import BeautifulSoup

from app.core.config import settings

logger = logging.getLogger(__name__)


class PrivateBrowserSearchService:
    """Search with a fresh headless Chromium context, never a user's browser profile."""

    _search_hosts = {"bing.com", "www.bing.com"}
    _blocked_domains = {"facebook.com", "youtube.com", "tiktok.com"}
    _blocked_extensions = {".jpg", ".jpeg", ".png", ".gif", ".svg", ".zip", ".mp4", ".css", ".js"}

    @staticmethod
    def _playwright_manager():
        from playwright.sync_api import sync_playwright

        return sync_playwright()

    @classmethod
    def _destination_url(cls, href: str) -> str | None:
        parsed = urlparse(href)
        host = (parsed.hostname or "").lower().rstrip(".")
        if host in cls._search_hosts and parsed.path.startswith("/ck/a"):
            encoded = parse_qs(parsed.query).get("u", [""])[0]
            if encoded.startswith("a1"):
                try:
                    padding = "=" * (-len(encoded[2:]) % 4)
                    href = base64.urlsafe_b64decode(encoded[2:] + padding).decode("utf-8")
                except (ValueError, UnicodeDecodeError):
                    return None
            parsed = urlparse(href)
            host = (parsed.hostname or "").lower().rstrip(".")

        if parsed.scheme not in {"http", "https"} or not host:
            return None
        if host in cls._search_hosts or host == "localhost" or host.endswith(".localhost"):
            return None
        if any(host == domain or host.endswith("." + domain) for domain in cls._blocked_domains):
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            pass
        if parsed.path.lower().endswith(tuple(cls._blocked_extensions)):
            return None
        return urldefrag(href)[0]

    def search(self, query: str, *, max_results: int | None = None) -> list[dict]:
        """Return safe public search results without visiting result destinations.

        A new browser process and in-memory context are created for every search.
        The application does not load, persist, or reuse cookies or browser data.
        """
        if not settings.KNOWLEDGE_BROWSER_SEARCH_ENABLED:
            return []
        query = " ".join(str(query or "").split())[:500]
        if not query:
            return []
        limit = max(1, min(int(max_results or settings.KNOWLEDGE_BROWSER_SEARCH_MAX_RESULTS), 20))
        timeout = max(1000, int(settings.KNOWLEDGE_BROWSER_SEARCH_TIMEOUT_SECONDS * 1000))
        search_url = "https://www.bing.com/search?q=" + quote_plus(query)
        try:
            with self._playwright_manager() as runtime:
                browser = runtime.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                context = None
                try:
                    context = browser.new_context(
                        locale="vi-VN",
                        accept_downloads=False,
                        service_workers="block",
                        java_script_enabled=False,
                    )
                    page = context.new_page()

                    def allow_only_search_page(route):
                        target = urlparse(route.request.url)
                        target_host = (target.hostname or "").lower()
                        if target.scheme in {"http", "https"} and target_host in self._search_hosts:
                            route.continue_()
                        else:
                            route.abort()

                    page.route("**/*", allow_only_search_page)
                    page.goto(search_url, wait_until="domcontentloaded", timeout=timeout)
                    final_host = (urlparse(page.url).hostname or "").lower()
                    if final_host not in self._search_hosts:
                        raise RuntimeError("Search provider redirected away from its search page.")
                    soup = BeautifulSoup(page.content(), "lxml")
                    results = []
                    seen = set()
                    anchors = soup.select("li.b_algo h2 a")
                    if not anchors and any(term in soup.get_text(" ", strip=True).lower()
                                           for term in ("captcha", "verify you are human", "unusual traffic")):
                        raise RuntimeError("Search provider returned an automated-traffic challenge.")
                    for anchor in anchors:
                        url = self._destination_url(anchor.get("href", ""))
                        if not url or url in seen:
                            continue
                        seen.add(url)
                        result_root = anchor.find_parent("li", class_="b_algo")
                        snippet_node = result_root.select_one(".b_caption p, p") if result_root else None
                        results.append({
                            "title": anchor.get_text(" ", strip=True)[:300],
                            "url": url,
                            "snippet": snippet_node.get_text(" ", strip=True)[:1200] if snippet_node else "",
                        })
                        if len(results) >= limit:
                            break
                    return results
                finally:
                    if context is not None:
                        try:
                            context.close()
                        except Exception:
                            logger.debug("Could not close private browser context", exc_info=True)
                    try:
                        browser.close()
                    except Exception:
                        logger.debug("Could not close private browser", exc_info=True)
        except Exception:
            logger.exception("Isolated browser search failed")
            raise


private_browser_search_service = PrivateBrowserSearchService()
