"""
TDD: dashboard không bỏ trống card chính khi vùng có dữ liệu cây khác.

featured-crop mặc định crop_name="lua" bất kể người dùng ở đâu. Nông dân
Đắk Lắk (vùng cà phê) mở dashboard là thấy lỗi ngay card chính, dù DB đang
có giá Cà phê/Đắk Lắk hẳn hoi (96.433 đ/kg).

Hành vi mong muốn: thiếu dữ liệu cây được hỏi thì hiển thị cây khác CÓ dữ
liệu ở vùng đó, và nói rõ đã thay — không im lặng đánh tráo.
"""
from unittest.mock import patch

import pytest

from datetime import date

from app.core.database import SessionLocal
from app.models.crop import CropType
from app.models.price import MarketPrice
from app.services.dashboard_service import dashboard_service


@pytest.fixture
def db():
    """Session kèm một dòng giá cà phê thật — nguồn để chọn cây thay thế."""
    s = SessionLocal()
    crop = s.query(CropType).filter(CropType.CropName == "ca phe").first()
    if not crop:
        crop = CropType(CropName="ca phe", Category="Cong nghiep")
        s.add(crop)
        s.commit()

    # Xoá sạch giá hôm nay trước khi seed để test chạy lại được nhiều lần
    s.query(MarketPrice).filter(MarketPrice.PriceDate == date.today()).delete()
    s.commit()
    s.add(MarketPrice(
        CropID=crop.CropID, Region="Đắk Lắk", PricePerKg=96433.0,
        QualityGrade="Loai 1", MarketType="Ban le", PriceDate=date.today(),
    ))
    s.commit()
    yield s
    s.query(MarketPrice).filter(MarketPrice.PriceDate == date.today()).delete()
    s.commit()
    s.close()


def _gia_that(crop, region):
    return {
        "crop_name": crop, "region": region, "current_price": 96433.0,
        "cache_status": "fresh_cache", "is_mock": False,
        "source_name": "Thông tin thị trường nông sản",
        "last_updated": "2026-08-22T05:00:00",
    }


def _khong_co_gia():
    return {
        "_api_error": True, "error_code": "REALTIME_PRICE_FAILED",
        "cache_status": "miss", "is_mock": False,
    }


def test_thay_bang_cay_co_du_lieu_trong_vung(db):
    """Lúa không có giá ở Đắk Lắk, nhưng cà phê có => hiện cà phê."""
    def gia_theo_cay(_db, crop, region, *a, **kw):
        # Lúa không có giá ở vùng này; bất kỳ cây nào khác thì có.
        return _khong_co_gia() if crop == "lua" else _gia_that(crop, region)

    with patch("app.services.dashboard_service.pricing_service.get_current_price",
               side_effect=gia_theo_cay):
        result = dashboard_service.get_featured_crop(db, crop_name="lua", region="Đắk Lắk")

    assert not result.get("_api_error"), "Vẫn báo lỗi dù vùng có dữ liệu cây khác"
    assert result.get("price"), "Không có giá"
    assert result.get("name") != "lua", "Không đổi sang cây khác"


def test_noi_ro_da_thay_cay_khac(db):
    """Đánh tráo im lặng còn tệ hơn báo lỗi — phải cho biết đã thay."""
    def gia_theo_cay(_db, crop, region, *a, **kw):
        # Lúa không có giá ở vùng này; bất kỳ cây nào khác thì có.
        return _khong_co_gia() if crop == "lua" else _gia_that(crop, region)

    with patch("app.services.dashboard_service.pricing_service.get_current_price",
               side_effect=gia_theo_cay):
        result = dashboard_service.get_featured_crop(db, crop_name="lua", region="Đắk Lắk")

    assert result.get("substituted_for") == "lua", (
        f"Không đánh dấu đã thay cây: {result.get('substituted_for')!r}"
    )


def test_van_bao_loi_khi_ca_vung_khong_co_du_lieu(db):
    """Không cây nào có dữ liệu => báo miss, tuyệt đối không bịa."""
    with patch("app.services.dashboard_service.pricing_service.get_current_price",
               return_value=_khong_co_gia()):
        result = dashboard_service.get_featured_crop(db, crop_name="lua", region="Sao Hoa")

    assert result.get("_api_error") is True
    assert result.get("price") is None


def test_chi_chon_cay_co_gia_dung_vung_do(db):
    """Cây thay thế phải có giá Ở VÙNG ĐÓ, không phải vùng bất kỳ.

    Truy vấn thiếu điều kiện region sẽ lấy cây mới nhất toàn quốc rồi hỏi giá
    ở vùng người dùng — cây đó không có giá ở đây nên vẫn hỏng, chỉ tốn thêm
    một lượt gọi.
    """
    crop = db.query(CropType).filter(CropType.CropName == "ca phe").first()
    # Giá mới hơn nhưng ở vùng KHÁC — không được chọn cho Đắk Lắk
    khac = db.query(CropType).filter(CropType.CropName != "ca phe").first()
    if khac:
        db.add(MarketPrice(
            CropID=khac.CropID, Region="An Giang", PricePerKg=7000.0,
            QualityGrade="Loai 1", MarketType="Ban buon", PriceDate=date.today(),
        ))
        db.commit()

    chon = dashboard_service._crop_with_recent_price(db, "Đắk Lắk", exclude="lua")
    assert chon == "ca phe", (
        f"Chọn nhầm cây không có giá ở Đắk Lắk: {chon!r}"
    )
