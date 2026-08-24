"""
TDD: dựng context cho AI có ngân sách thời gian, không để nguồn chậm kéo cả câu trả lời.

Đo thực tế /api/chat với crawler nền ĐÃ TẮT: vẫn 8.2s. Tức việc cào nằm ngay
trong request. build_ai_context gọi 3-4 bundle tuần tự, mỗi bundle cào web
khi cache miss và mỗi lượt timeout 3.18s:

    [thitruongnongsan_news]      timeout x6
    [thitruongnongsan_price_get] timeout x3

Nông dân hỏi một câu không nên chờ hệ thống cào lại thứ crawler nền đã cào
mỗi 2 giờ (TOD0 §4). Có cache thì trả lời bằng cache; nguồn chậm thì bỏ qua,
không chặn.
"""
import time

import pytest

from app.core.database import SessionLocal
from app.services.ai_context_service import ai_context_service

TRE = 3.2          # moi nguon cham dung bang mot lan timeout that
NGAN_SACH = 4.0    # tran cho toan bo viec dung context


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


def test_nguon_cham_khong_keo_dai_qua_ngan_sach(db, monkeypatch):
    """3-4 nguồn chậm chạy song song phải xong trong ngân sách, không cộng dồn."""
    def cham(*a, **kw):
        time.sleep(TRE)
        return {"cache_status": "miss"}

    for ten in ("get_weather_bundle", "get_pricing_bundle", "get_market_bundle",
                "get_alert_notification_bundle"):
        monkeypatch.setattr(
            f"app.services.ai_context_service.agri_data_aggregator_service.{ten}",
            cham, raising=False,
        )
    monkeypatch.setattr(
        "app.services.ai_context_service.pricing_service.analyze_market", cham, raising=False
    )

    t0 = time.monotonic()
    ai_context_service.build_ai_context(db, region="Đắk Lắk", crop="ca phe",
                                        intent="full_farm_analysis")
    mat = time.monotonic() - t0

    assert mat < NGAN_SACH, (
        f"Dựng context mất {mat:.1f}s — nguồn chậm đang cộng dồn "
        f"(ngân sách {NGAN_SACH}s)"
    )


def test_van_tra_ve_du_khoa_khi_nguon_cham(db, monkeypatch):
    """Hết ngân sách vẫn phải trả context hợp lệ, không vỡ cấu trúc."""
    def cham(*a, **kw):
        time.sleep(TRE)
        return {"cache_status": "miss"}

    monkeypatch.setattr(
        "app.services.ai_context_service.agri_data_aggregator_service.get_pricing_bundle",
        cham, raising=False,
    )

    ctx = ai_context_service.build_ai_context(db, region="Đắk Lắk", crop="ca phe",
                                              intent="price_analysis")
    assert isinstance(ctx, dict) and ctx, "Context rỗng khi nguồn chậm"
