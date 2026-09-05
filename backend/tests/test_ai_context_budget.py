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


def test_moi_nguon_dung_session_rieng(db):
    """SQLAlchemy Session KHÔNG thread-safe — dùng chung sẽ hỏng ngẫu nhiên.

    Bug thật đã gặp: 5 lambda cùng bắt `db` của request rồi chạy song song.
    Backend suy kiệt dần, login treo vô hạn (>10 phút) trong khi /health vẫn
    nhanh; restart là hết — dấu hiệu kinh điển của session/connection hỏng.
    """
    import threading
    luong_chinh = threading.get_ident()
    goi = []   # (id session, co phai luong phu khong)

    def ghi_lai(sess, *a, **kw):
        goi.append((id(sess), threading.get_ident() != luong_chinh))
        return {"cache_status": "miss"}

    import app.services.ai_context_service as mod
    goc = mod.agri_data_aggregator_service

    class Gia:
        def __getattr__(self, ten):
            return ghi_lai

    mod.agri_data_aggregator_service = Gia()
    try:
        ai_context_service.build_ai_context(
            db, region="Đắk Lắk", crop="ca phe", intent="full_farm_analysis"
        )
    finally:
        mod.agri_data_aggregator_service = goc

    assert goi, "Không nguồn nào được gọi"

    # Goi tuan tu tren luong chinh dung `db` la an toan. Chi luong phu moi cam.
    tren_luong_phu = [sid for sid, phu in goi if phu]
    assert tren_luong_phu, "Không có nguồn nào chạy song song"
    assert id(db) not in tren_luong_phu, (
        "Nguồn chạy trên luồng phụ đang dùng CHUNG session của request — "
        "Session không thread-safe, sẽ hỏng dữ liệu và cạn kết nối"
    )
    # Không kiểm tính duy nhất của id(session): CPython tái dùng địa chỉ sau
    # khi session đóng, nên hai luồng chạy nối tiếp có thể trùng id một cách
    # hợp lệ. Điều thực sự quan trọng là không đụng vào session của request.
