"""
Tuổi của giá phải tính từ NGÀY GIÁ, không phải lúc ta gọi API.

Đo thật sau khi sửa được nguồn chính thống:

    official_price   = 96.433 đ/kg
    PriceDate        = 2026-08-04     (37 ngày trước)
    FetchedAt        = 2026-09-10     (vừa gọi xong)
    cache_status     = fresh_cache
    data_age_minutes = 0

Nguồn thitruongnongsan.gov.vn cập nhật không đều — lần gần nhất là 04/08.
Ta gọi lại mỗi 3 tiếng và lần nào cũng nhận đúng con số cũ đó, rồi đóng dấu
"vừa cập nhật".

Đây đúng là lỗi đã sửa cho thời tiết, nay lặp lại ở giá. Với thời tiết thì
hiển thị sai; với giá thì nông dân quyết định bán dựa trên mặt bằng của
tháng trước.
"""
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.crop import CropType
from app.models.price import MarketPrice
from app.services.price_aggregator_service import price_aggregator_service


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add(CropType(CropID=3, CropName="Cà phê"))
    s.commit()
    yield s
    s.close()


def _gia(db, *, ngay_gia, fetched):
    db.add(MarketPrice(CropID=3, Region="Đắk Lắk", PricePerKg=96433.0,
                       PriceDate=ngay_gia, ObservedAt=datetime.combine(ngay_gia, datetime.min.time()),
                       FetchedAt=fetched, UpdatedAt=fetched,
                       SourceName="Thông tin thị trường nông sản",
                       SourceURL="https://thitruongnongsan.gov.vn/vn/nguonwmy.aspx",
                       IsMock=False))
    db.commit()


def test_gia_cu_mot_thang_khong_duoc_goi_la_fresh(db):
    """Vừa gọi API xong không làm con số 37 ngày tuổi mới lại."""
    _gia(db, ngay_gia=date.today() - timedelta(days=37), fetched=datetime.now())

    kq = price_aggregator_service.get_best_current_price(db, "ca phe", "Đắk Lắk")

    assert kq.get("cache_status") != "fresh_cache", (
        f"Giá ghi nhận 37 ngày trước được đóng dấu {kq.get('cache_status')}"
    )


def test_tuoi_phan_anh_ngay_gia(db):
    _gia(db, ngay_gia=date.today() - timedelta(days=37), fetched=datetime.now())

    kq = price_aggregator_service.get_best_current_price(db, "ca phe", "Đắk Lắk")

    tuoi = kq.get("data_age_minutes")
    assert tuoi is not None and tuoi >= 30 * 24 * 60, (
        f"Báo tuổi {tuoi} phút cho giá của 37 ngày trước"
    )


def test_gia_moi_van_la_fresh(db):
    """Không siết nhầm: giá hôm nay vẫn phải là fresh."""
    _gia(db, ngay_gia=date.today(), fetched=datetime.now())

    kq = price_aggregator_service.get_best_current_price(db, "ca phe", "Đắk Lắk")

    assert kq.get("cache_status") == "fresh_cache", kq.get("cache_status")
