import base64
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.services.private_browser_search_service import PrivateBrowserSearchService
from app.services.source_discovery_service import SourceDiscoveryService


def test_private_browser_search_uses_a_fresh_context_and_closes_it(monkeypatch):
    closed = {"context": False, "browser": False, "runtime": False}
    routing = {"allowed": 0, "blocked": 0}
    destination = "https://extension.umn.edu/grapes/growing-grapes"
    encoded = base64.urlsafe_b64encode(destination.encode()).decode().rstrip("=")
    redirect = "https://www.bing.com/ck/a?" + urlencode({"u": f"a1{encoded}"})

    class FakePage:
        url = "https://www.bing.com/search?q=grape"

        def goto(self, url, **_kwargs):
            self.url = url

        def route(self, _pattern, handler):
            class FakeRoute:
                def __init__(self, url):
                    self.request = type("Request", (), {"url": url})()

                def continue_(self):
                    routing["allowed"] += 1

                def abort(self):
                    routing["blocked"] += 1

            handler(FakeRoute("https://www.bing.com/search?q=grape"))
            handler(FakeRoute("https://khuyennong.gov.vn/article"))

        def content(self):
            return f'''<li class="b_algo"><h2>
              <a href="{redirect}">University grape guide</a>
            </h2><div class="b_caption"><p>Agricultural extension guidance</p></div></li>'''

    class FakeContext:
        def new_page(self):
            return FakePage()

        def close(self):
            closed["context"] = True

    class FakeBrowser:
        def new_context(self, **kwargs):
            assert "storage_state" not in kwargs
            return FakeContext()

        def close(self):
            closed["browser"] = True

    class FakeChromium:
        def launch(self, **kwargs):
            assert kwargs["headless"] is True
            return FakeBrowser()

    class FakeRuntime:
        chromium = FakeChromium()

        def __exit__(self, *_args):
            closed["runtime"] = True

    class FakeManager:
        def __enter__(self):
            return FakeRuntime()

        def __exit__(self, *_args):
            closed["runtime"] = True

    service = PrivateBrowserSearchService()
    monkeypatch.setattr(service, "_playwright_manager", lambda: FakeManager())

    results = service.search("grape growing guide", max_results=4)

    assert results == [{
        "title": "University grape guide",
        "url": destination,
        "snippet": "Agricultural extension guidance",
    }]
    assert closed == {"context": True, "browser": True, "runtime": True}
    assert routing == {"allowed": 1, "blocked": 1}


def test_browser_search_discards_social_and_private_network_results(monkeypatch):
    class FakePage:
        url = "https://www.bing.com/search?q=crops"

        def goto(self, url, **_kwargs):
            self.url = url

        def route(self, _pattern, _handler):
            pass

        def content(self):
            return '''<li class="b_algo"><h2><a href="https://www.facebook.com/groups/agriculture">Facebook</a></h2></li>
              <li class="b_algo"><h2><a href="http://127.0.0.1/admin">Private</a></h2></li>
              <li class="b_algo"><h2><a href="https://khuyennong.gov.vn/crops">Khuyến nông</a></h2></li>'''

    class FakeContext:
        def new_page(self):
            return FakePage()

        def close(self):
            pass

    class FakeBrowser:
        def new_context(self, **_kwargs):
            return FakeContext()

        def close(self):
            pass

    class FakeManager:
        def __enter__(self):
            return type("Runtime", (), {"chromium": type("Chromium", (), {
                "launch": lambda _self, **_kwargs: FakeBrowser()
            })()})()

        def __exit__(self, *_args):
            pass

    service = PrivateBrowserSearchService()
    monkeypatch.setattr(service, "_playwright_manager", lambda: FakeManager())

    results = service.search("nông nghiệp", max_results=10)

    assert [result["url"] for result in results] == ["https://khuyennong.gov.vn/crops"]


def test_query_discovery_falls_back_to_private_browser_for_official_crop_results(monkeypatch):
    service = SourceDiscoveryService()
    seed = {
        "name": "Configured registry",
        "url": "https://seed.gov.vn/library",
        "allowed_domain": "seed.gov.vn",
        "include_patterns": ["/guide-"],
    }
    monkeypatch.setattr(service.ingestion, "fetch", lambda url, _domain: httpx.Response(
        200,
        text="<html><body>No matching documents.</body></html>",
        headers={"content-type": "text/html"},
        request=httpx.Request("GET", url),
    ))
    searched = []
    monkeypatch.setattr(
        "app.services.source_discovery_service.private_browser_search_service.search",
        lambda query, **kwargs: searched.append((query, kwargs)) or [
            {"title": "Hướng dẫn trồng nho", "url": "https://khuyennong.ninhthuan.gov.vn/nho",
             "snippet": "Tài liệu kỹ thuật trồng nho tại Ninh Thuận."},
            {"title": "Generic guide", "url": "https://example.com/nho", "snippet": "Nho."},
            {"title": "Facebook grape group", "url": "https://facebook.com/groups/nho", "snippet": "Nho."},
        ],
    )

    candidates = service.discover_for_query(
        ["nho", "ky thuat", "ninh thuan"],
        sources=[seed], crop="nho", region="Ninh Thuận", max_candidates=3,
    )

    assert len(searched) == 1
    assert "nho" in searched[0][0]
    assert "Ninh Thuận" in searched[0][0]
    assert "cây" not in searched[0][0]
    assert len(candidates) == 1
    assert candidates[0]["url"] == "https://khuyennong.ninhthuan.gov.vn/nho"
    assert candidates[0]["source"]["allowed_domain"] == "khuyennong.ninhthuan.gov.vn"
    assert candidates[0]["source"]["crop"] == "nho"


def test_crop_query_searches_new_official_sources_even_when_registry_quota_is_full(monkeypatch):
    """A crop query must not stop at the legacy registry quota."""
    service = SourceDiscoveryService()
    seed = {
        "name": "Configured registry",
        "url": "https://seed.gov.vn/library",
        "allowed_domain": "seed.gov.vn",
        "include_patterns": ["/guide-"],
    }
    html = """<html><body>
      <a href="/guide-nho-1">Kỹ thuật trồng nho 1</a>
      <a href="/guide-nho-2">Kỹ thuật trồng nho 2</a>
      <a href="/guide-nho-3">Kỹ thuật trồng nho 3</a>
    </body></html>"""
    monkeypatch.setattr(service.ingestion, "fetch", lambda url, _domain: httpx.Response(
        200,
        text=html,
        headers={"content-type": "text/html"},
        request=httpx.Request("GET", url),
    ))
    monkeypatch.setattr(
        service.ingestion,
        "discover",
        lambda _seed, scan_limit: [
            "https://seed.gov.vn/guide-nho-1",
            "https://seed.gov.vn/guide-nho-2",
            "https://seed.gov.vn/guide-nho-3",
        ],
    )
    searched = []
    monkeypatch.setattr(
        "app.services.source_discovery_service.private_browser_search_service.search",
        lambda query, **kwargs: searched.append((query, kwargs)) or [
            {
                "title": "Hướng dẫn trồng nho ngón tay",
                "url": "https://khuyen-nong.ninhthuan.gov.vn/nho-ngon-tay",
                "snippet": "Tài liệu kỹ thuật trồng nho ngón tay tại Ninh Thuận.",
            },
        ],
    )

    candidates = service.discover_for_query(
        ["nho", "nho ngón tay", "kỹ thuật", "Ninh Thuận"],
        sources=[seed],
        crop="nho",
        region="Ninh Thuận",
        max_candidates=3,
    )

    assert searched, "crop-scoped discovery must search beyond the configured registry"
    assert any(item.get("source_is_new") for item in candidates)
    assert any(item["domain"] == "khuyen-nong.ninhthuan.gov.vn" for item in candidates)


def test_browser_search_failure_is_reported_as_a_job_warning(monkeypatch):
    service = SourceDiscoveryService()
    seed = {
        "name": "Configured registry",
        "url": "https://seed.gov.vn/library",
        "allowed_domain": "seed.gov.vn",
        "include_patterns": ["/guide-"],
    }
    monkeypatch.setattr(service.ingestion, "fetch", lambda url, _domain: httpx.Response(
        200,
        text="<html><body>No matching documents.</body></html>",
        headers={"content-type": "text/html"},
        request=httpx.Request("GET", url),
    ))
    monkeypatch.setattr(
        "app.services.source_discovery_service.private_browser_search_service.search",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("browser unavailable")),
    )
    monkeypatch.setattr(service, "_topic_source_hints", lambda _crop: [])
    warnings = []

    assert service.discover_for_query(["nho", "canh tac"], sources=[seed], crop="nho", warnings=warnings) == []
    assert warnings == ["Không dùng được trình duyệt tìm kiếm; kiểm tra Playwright, Chromium và kết nối mạng."]


def test_crop_query_uses_verified_topic_hint_when_browser_has_no_result(monkeypatch):
    service = SourceDiscoveryService()
    seed = {
        "name": "Configured registry",
        "url": "https://seed.gov.vn/library",
        "allowed_domain": "seed.gov.vn",
        "include_patterns": ["/guide-"],
    }
    monkeypatch.setattr(service.ingestion, "fetch", lambda url, _domain: httpx.Response(
        200,
        text="<html><body>No matching documents.</body></html>",
        headers={"content-type": "text/html"},
        request=httpx.Request("GET", url),
    ))
    monkeypatch.setattr(
        "app.services.source_discovery_service.private_browser_search_service.search",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(service, "_topic_source_hints", lambda _crop: [{
        "name": "Hướng dẫn kỹ thuật trồng nho",
        "url": "https://grape-extension.gov.vn/guide-nho",
        "allowed_domain": "grape-extension.gov.vn",
        "crop": "Nho",
        "region": "Việt Nam",
    }])

    candidates = service.discover_for_query(
        ["nho", "kỹ thuật"], sources=[seed], crop="nho", max_candidates=3,
    )

    assert len(candidates) == 1
    assert candidates[0]["source_is_new"] is True
    assert candidates[0]["source"]["allowed_domain"] == "grape-extension.gov.vn"


def test_common_crop_queries_use_official_topic_fallbacks_when_browser_has_no_result(monkeypatch):
    service = SourceDiscoveryService()
    monkeypatch.setattr(service.ingestion, "fetch", lambda url, _domain: httpx.Response(
        200,
        text="<html><body>No matching documents.</body></html>",
        headers={"content-type": "text/html"},
        request=httpx.Request("GET", url),
    ))
    monkeypatch.setattr(
        "app.services.source_discovery_service.private_browser_search_service.search",
        lambda *_args, **_kwargs: [],
    )

    for crop in ("cam", "dua hau", "xoai"):
        candidates = service.discover_for_query(
            [crop, "ky thuat"], sources=[], crop=crop, max_candidates=1,
        )
        assert candidates, f"expected an official fallback for {crop}"
        assert candidates[0]["is_official_domain"] is True
        assert candidates[0]["source"]["allowed_domain"].endswith(".gov.vn") or candidates[0]["source"]["allowed_domain"].endswith(".edu.vn")


def test_common_crop_fallbacks_remain_available_when_browser_search_is_disabled(monkeypatch):
    service = SourceDiscoveryService()
    monkeypatch.setattr(settings, "KNOWLEDGE_BROWSER_SEARCH_ENABLED", False)
    candidates = service.discover_for_query(
        ["xoai", "ky thuat"], sources=[], crop="xoai", max_candidates=1,
    )

    assert candidates
    assert candidates[0]["is_official_domain"] is True


def test_missing_answer_searches_browser_before_configured_registries(monkeypatch):
    service = SourceDiscoveryService()
    seed = {
        "name": "Configured registry",
        "url": "https://seed.gov.vn/library",
        "allowed_domain": "seed.gov.vn",
        "include_patterns": ["/guide-"],
    }
    order = []

    monkeypatch.setattr(service.ingestion, "fetch", lambda url, _domain: (
        order.append("registry") or httpx.Response(
            200,
            text="<html><body>No matching documents.</body></html>",
            headers={"content-type": "text/html"},
            request=httpx.Request("GET", url),
        )
    ))
    monkeypatch.setattr(
        "app.services.source_discovery_service.private_browser_search_service.search",
        lambda *_args, **_kwargs: order.append("browser") or [],
    )

    service.discover_for_query(["canh tac"], sources=[seed], max_candidates=1)

    assert order and order[0] == "browser"


def test_browser_candidates_are_prioritized_before_registry_candidates(monkeypatch):
    service = SourceDiscoveryService()
    seed = {
        "name": "Configured registry",
        "url": "https://seed.gov.vn/library",
        "allowed_domain": "seed.gov.vn",
        "include_patterns": ["/guide-"],
    }
    html = '<html><body><a href="/guide-cam">Kỹ thuật trồng cam</a></body></html>'
    monkeypatch.setattr(service.ingestion, "fetch", lambda url, _domain: httpx.Response(
        200,
        text=html,
        headers={"content-type": "text/html"},
        request=httpx.Request("GET", url),
    ))
    monkeypatch.setattr(
        service.ingestion,
        "discover",
        lambda _seed, scan_limit: ["https://seed.gov.vn/guide-cam"],
    )
    monkeypatch.setattr(
        "app.services.source_discovery_service.private_browser_search_service.search",
        lambda *_args, **_kwargs: [{
            "title": "Hướng dẫn kỹ thuật trồng cam",
            "url": "https://new-agri.gov.vn/guide-cam",
            "snippet": "Quy trình kỹ thuật trồng cam.",
        }],
    )

    candidates = service.discover_for_query(
        ["cam", "ky thuat"], sources=[seed], crop="cam", max_candidates=2,
    )

    assert [item["domain"] for item in candidates] == ["new-agri.gov.vn", "seed.gov.vn"]
