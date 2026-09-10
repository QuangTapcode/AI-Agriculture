"""
TDD: Bảng điều khiển đọc cache, không cào web đồng bộ.

Đo thực tế từng job của /api/dashboard/summary khi cache lạnh:

    market_news       7.04s   cào RSS
    featured_crop     6.20s   API thitruongnongsan — timeout
    weather_risk      4.73s
    regional_prices   3.13s
    price_trend       0.01s   đọc DB

Năm job đã chạy song song nên tổng bằng job chậm nhất — khoảng 7s, khớp
với "5-7s mới load xong" người dùng thấy.

Gốc rễ ở price_aggregator_service.get_best_current_price:

    # Cache miss hoặc cache expired: tự động thử crawl một lần dù force_refresh=False
    refresh_result = self.refresh_price_for_crop_region(...)

Giá trong DB đang cũ 13 ngày, vượt STALE_TTL_MINUTES["official_price"]
(1440 phút) nên mọi request đều rơi vào nhánh này và tự đi cào. Crawler
giá thì chỉ có lịch 2h sáng — mà Celery Beat trước đây không hề chạy.

TOD0 §4: dữ liệu nặng đọc từ cache, không chặn request người dùng. Thiếu
dữ liệu thì báo cache_status="miss" và để người dùng thấy ngay, còn hơn
bắt họ chờ 7 giây rồi vẫn nhận số cũ 13 ngày.
"""
import time

import httpx
import pytest

from app.core.database import SessionLocal
from app.tasks.celery_app import celery_app

NOI_BO = ("127.0.0.1", "localhost", "testserver", "db", "redis", "host.docker.internal")


@pytest.fixture
def http_ra_ngoai(monkeypatch):
    """Ghi lại mọi lượt HTTP ra Internet."""
    goi = []

    for lop in (httpx.Client, httpx.AsyncClient):
        that = lop.send

        def lam(self, request, *a, __that=that, **kw):
            host = request.url.host or ""
            if not any(n in host for n in NOI_BO):
                goi.append(str(request.url)[:70])
            return __that(self, request, *a, **kw)

        monkeypatch.setattr(lop, "send", lam)
    return goi


def test_summary_khong_cao_web_dong_bo(http_ra_ngoai):
    from app.services.dashboard_service import dashboard_service

    db = SessionLocal()
    try:
        dashboard_service.get_summary(db, region="Đắk Lắk", crop_name="ca phe")
    finally:
        db.close()

    assert not http_ra_ngoai, (
        f"Bảng điều khiển cào {len(http_ra_ngoai)} lượt web trong request: "
        f"{http_ra_ngoai[:4]}"
    )


def test_gia_het_han_van_khong_cao_trong_request(http_ra_ngoai):
    """Cache quá hạn là chuyện của crawler nền, không phải của người đang xem."""
    from app.services.price_aggregator_service import price_aggregator_service

    db = SessionLocal()
    try:
        price_aggregator_service.get_best_current_price(db, "ca phe", "Đắk Lắk")
    finally:
        db.close()

    assert not http_ra_ngoai, f"Đọc giá đã tự đi cào: {http_ra_ngoai[:3]}"


def test_force_refresh_van_duoc_cao():
    """Không siết nhầm: bấm 'làm mới' là người dùng chủ động chờ."""
    import inspect

    from app.services.price_aggregator_service import price_aggregator_service

    ma = inspect.getsource(price_aggregator_service.get_best_current_price)
    assert "force_refresh" in ma, "Mất luôn đường làm mới chủ động"


def test_co_lich_lam_moi_gia_nen():
    """Bỏ cào trong request thì phải có crawler nền bù vào, không thì rỗng mãi."""
    lich = [c for c in celery_app.conf.beat_schedule.values() if "price" in c["task"]]
    assert lich, "Không có lịch nào làm mới giá"

    # crontab (2h sáng mỗi ngày) không đủ dày; đòi hỏi lịch theo chu kỳ.
    chu_ky = [c["schedule"] for c in lich if hasattr(c["schedule"], "total_seconds")]
    assert chu_ky, "Lịch giá đang là crontab theo giờ cố định, không phải chu kỳ"
    nhanh_nhat = min(s.total_seconds() for s in chu_ky)
    # CACHE_TTL_MINUTES["official_price"] = 180 phút. Cào thưa hơn thì cache
    # luôn ở trạng thái stale/miss và trang không bao giờ có số tươi.
    assert nhanh_nhat <= 180 * 60, (
        f"Chỉ làm mới giá mỗi {nhanh_nhat / 3600:.0f} giờ — cache hết hạn sau 3 giờ"
    )


def test_summary_du_nhanh():
    """Người dùng chờ 5-7s là hỏng; đọc DB thuần phải dưới 1.5s."""
    from app.services.dashboard_service import dashboard_service

    db = SessionLocal()
    try:
        dashboard_service.get_summary(db, region="Đắk Lắk", crop_name="ca phe",
                                      force_refresh_weather=False)
        t0 = time.time()
        dashboard_service.get_summary(db, region="Cần Thơ", crop_name="lua")
        mat = time.time() - t0
    finally:
        db.close()

    assert mat < 1.5, f"Bảng điều khiển mất {mat:.1f}s"


def test_co_task_lam_moi_gia_chinh_thong():
    """Bỏ cào trong request thì phải có ai đó gọi nguồn chính thống.

    run_price_crawler cào các trang bán lẻ (bachhoaxanh, giacaphe...) rồi ghi
    qua _save_market_prices. Giá chính thống từ thitruongnongsan.gov.vn lại đi
    đường khác: price_aggregator_service.refresh_prices(). Trước đây đường đó
    chỉ được kích hoạt bởi chính request của người dùng khi cache hết hạn.

    Chặn cào trong request mà không lên lịch cho nhánh này thì giá cà phê sẽ
    đứng im ở mốc 27/08 vĩnh viễn — im lặng và khó phát hiện hơn cả chậm.
    """
    import importlib

    mod = importlib.import_module("app.tasks.crawler_tasks")
    ten_task = {c["task"] for c in celery_app.conf.beat_schedule.values()}

    assert any("official_price" in t or "refresh_prices" in t for t in ten_task), (
        f"Không có lịch gọi nguồn giá chính thống. Đang có: {sorted(ten_task)}"
    )
    assert hasattr(mod, "refresh_official_prices"), (
        "Chưa có task refresh_official_prices"
    )
