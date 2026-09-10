"""
Dự báo giá không được vẽ đường cong từ hư không.

`PriceForecastService._fallback_forecast` chạy khi model EMA không đủ dữ liệu
(cần >= 15 ngày lịch sử). Nó lấy trung bình 7 điểm gần nhất rồi sinh dao động:

    noise = 0.01 * ((i * 7) % 5 - 2) / 5
    current = current * (1 + noise)

Dao động này không mang thông tin nào — chỉ là hàm của chỉ số vòng lặp. Với
MỘT điểm giá nó vẫn vẽ đủ 7 ngày lên xuống, rồi `_calc_trend` đọc chính đường
đó và tuyên bố "tăng"/"giảm". Payload gắn `is_mock: False`.

DB hiện có 46 dòng giá, gần như toàn bộ từ một lần cào duy nhất — nghĩa là
nhánh này là nhánh chạy thật, không phải trường hợp hiếm.

TOD0 §1: không sinh dữ liệu tổng hợp. Thiếu lịch sử thì nói thiếu.
"""
import pytest

from app.services.price_forecast_service import PriceForecastService


def _lich_su(gia_list):
    return [{"date": f"2026-09-{i + 1:02d}", "price": g} for i, g in enumerate(gia_list)]


def test_mot_diem_gia_khong_du_de_du_bao():
    """Một con số không thành xu hướng."""
    kq = PriceForecastService._fallback_forecast(_lich_su([96000.0]), 7)

    assert not kq.get("forecast_data"), (
        f"Vẽ {len(kq['forecast_data'])} ngày dự báo từ đúng 1 điểm giá"
    )


def test_khong_bia_dao_dong_khi_gia_khong_doi():
    """Lịch sử phẳng thì dự báo phải phẳng, không tự uốn lượn."""
    kq = PriceForecastService._fallback_forecast(_lich_su([96000.0] * 10), 7)

    gia = [d["predicted_price"] for d in kq.get("forecast_data", [])]
    assert gia, "Có 10 ngày lịch sử mà không dự báo được gì"
    assert len(set(gia)) == 1, (
        f"Giá lịch sử không đổi nhưng dự báo dao động: {gia}"
    )


def test_xu_huong_phang_thi_bao_stable():
    kq = PriceForecastService._fallback_forecast(_lich_su([96000.0] * 10), 7)

    assert kq.get("trend") == "stable", (
        f"Lịch sử phẳng mà kết luận xu hướng '{kq.get('trend')}'"
    )


def test_van_phan_anh_xu_huong_that():
    """Không siết nhầm: giá tăng thật thì dự báo phải thấy."""
    tang_dan = [90000.0 + i * 500 for i in range(12)]

    kq = PriceForecastService._fallback_forecast(_lich_su(tang_dan), 7)
    gia = [d["predicted_price"] for d in kq.get("forecast_data", [])]

    assert gia, "Có 12 ngày lịch sử tăng đều mà không dự báo được"
    assert gia[-1] > gia[0], f"Lịch sử tăng đều nhưng dự báo không tăng: {gia}"
