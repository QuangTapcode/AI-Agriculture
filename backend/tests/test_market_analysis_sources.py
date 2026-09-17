from app.services.market_analysis_service import MarketAnalysisService


def test_market_analysis_sources_include_provenance_and_update_time():
    sources = MarketAnalysisService()._build_sources(
        current={"source_name": "MarketPrices DB", "source_url": "https://example.org/price", "fetched_at": "2026-09-14T07:00:00"},
        news_bundle={"source_name": "Khuyến nông Quốc gia", "source_url": "https://example.org/news", "fetched_at": "2026-09-14T06:00:00"},
        retail_bundle={"source_name": "Retail DB", "source_url": "https://example.org/retail", "fetched_at": "2026-09-14T05:00:00"},
        weather={"source_name": "Open-Meteo", "source_url": "https://example.org/weather", "fetched_at": "2026-09-14T04:00:00"},
    )

    assert len(sources) == 4
    assert all(item["source_url"] and item["fetched_at"] for item in sources)


def test_market_analysis_without_price_is_explicitly_unavailable():
    output = MarketAnalysisService._format_output({"crop_name": "Cà phê", "official_market_price": None})

    assert output["current_price"] is None
    assert output["cache_status"] == "miss"
    assert output["source_name"] is None
    assert output["warning"]
