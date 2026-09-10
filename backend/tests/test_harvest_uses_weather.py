"""
Dự báo thu hoạch phải dùng thời tiết thật, không chỉ cộng ngày.

harvest_service.forecast_harvest có đúng một dòng quyết định tất cả:

    weather_for_predictor = None          # dòng 127

Gán cứng None và không bao giờ được gán lại. Nên HarvestPredictor._weather_adjustment
nhận dict rỗng, trả (0, []), total_days = base_days, và kết quả đúng bằng

    ngày trồng + số ngày sinh trưởng tra bảng

Toàn bộ phần điều chỉnh theo nhiệt độ/mưa/độ ẩm trong predictor là code chết,
kể cả khi WeatherData đã có số liệu thật cho vùng đó.

Hai điều nữa cần đúng khi nối dây:

  * Ngưỡng phải xét thời tiết của CẢ VỤ chứ không phải một ngày. Predictor
    hiện nhận một snapshot; đưa trung bình 7 ngày vào còn hơn đưa None, nhưng
    phải nói rõ dự báo dựa trên bao nhiêu ngày dữ liệu.
  * Không có dữ liệu thời tiết thì phải hạ độ tin cậy, không im lặng.
"""
from datetime import date, datetime, timedelta

import pytest

from ai_models.harvest_forecast.predictor import HarvestPredictor


def test_predictor_thuc_su_doi_ngay_theo_thoi_tiet():
    """Chốt hành vi predictor trước: nắng nóng phải lùi ngày thu hoạch."""
    p = HarvestPredictor()
    ngay_trong = datetime(2026, 3, 1)

    khong_thoi_tiet = p.predict("Cà chua", ngay_trong, "Lâm Đồng", growth_duration_days=75)
    nang_nong = p.predict("Cà chua", ngay_trong, "Lâm Đồng", growth_duration_days=75,
                          weather_data={"temperature": 39.0, "rainfall": 0.0, "humidity": 40.0})

    assert nang_nong["growth_days"] > khong_thoi_tiet["growth_days"]


def test_service_truyen_thoi_tiet_that_vao_predictor(monkeypatch):
    """Dòng weather_for_predictor = None phải biến mất."""
    # app.services xuat ra INSTANCE cung ten, phai lay dung MODULE
    import importlib
    mod = importlib.import_module("app.services.harvest_service")

    da_nhan = {}
    that = HarvestPredictor.predict

    def ghi_lai(self, *a, **kw):
        da_nhan.update(kw)
        return that(self, *a, **kw)

    monkeypatch.setattr(HarvestPredictor, "predict", ghi_lai)
    monkeypatch.setattr(
        mod.harvest_service, "_thoi_tiet_cho_du_bao",
        lambda db, region: {"temperature": 38.5, "rainfall": 2.0, "humidity": 88.0, "so_ngay": 7},
    )

    from app.schemas.harvest_schema import HarvestForecastRequest

    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        mod.harvest_service.forecast_harvest(
            db,
            HarvestForecastRequest(crop_name="ca chua", region="Lâm Đồng",
                                   planting_date=date(2026, 3, 1)),
        )
    finally:
        db.close()

    assert da_nhan.get("weather_data"), (
        "Predictor vẫn nhận weather_data=None — dự báo chỉ là ngày trồng + số ngày"
    )


def test_ket_qua_neu_ro_dua_tren_bao_nhieu_ngay_thoi_tiet():
    """Nông dân cần biết con số dựa trên gì."""
    from app.services.harvest_service import harvest_service
    from app.schemas.harvest_schema import HarvestForecastRequest

    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        kq = harvest_service.forecast_harvest(
            db,
            HarvestForecastRequest(crop_name="ca chua", region="Lâm Đồng",
                                   planting_date=date(2026, 3, 1)),
        )
    finally:
        db.close()

    assert "weather_days_used" in kq, "Không nói rõ dùng bao nhiêu ngày thời tiết"


def test_khong_co_thoi_tiet_thi_ha_do_tin_cay():
    p = HarvestPredictor()
    ngay_trong = datetime(2026, 3, 1)

    co = p.predict("Cà chua", ngay_trong, "Lâm Đồng", growth_duration_days=75,
                   weather_data={"temperature": 28.0, "rainfall": 5.0, "humidity": 75.0})
    khong = p.predict("Cà chua", ngay_trong, "Lâm Đồng", growth_duration_days=75)

    assert khong["confidence"] < co["confidence"]
