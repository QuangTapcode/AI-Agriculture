"""
Câu giải thích định giá phải khớp với chính số liệu của nó.

Quan sát thật, /api/pricing/suggest cho cà phê Đắk Lắk:

    "Thời tiết bất lợi (thời tiết thuận lợi (30°c, mưa 19mm)) dự kiến làm
     giảm nguồn cung, giá có thể **tăng ~3.7%** so với mức cơ sở."

Một câu vừa nói "bất lợi" vừa nói "thuận lợi". Nguyên nhân: `summary` mô tả
NGÀY PHỔ BIẾN NHẤT trong 7 ngày (dominant = optimal), còn `explanation` chỉ
nhìn DẤU của hệ số tổng hợp (+3.7% vì vài ngày mưa) rồi dán nhãn cứng
"Thời tiết bất lợi" trước khi nhét cả `summary` vào giữa ngoặc.

Người nông dân đọc câu này không biết nên tin vế nào.
"""
import re

from app.services.weather_pricing_service import calculate_weather_factor


def _ngay(condition, temp_max=30.0, rainfall=5.0):
    return {"condition": condition, "temp_max": temp_max, "rainfall": rainfall}


def test_khong_vua_bat_loi_vua_thuan_loi():
    """5 ngày đẹp + 2 ngày mưa: hệ số dương nhẹ, nhưng câu chữ phải nhất quán."""
    forecast = [_ngay("optimal")] * 5 + [_ngay("heavy_rain", rainfall=25.0)] * 2

    factor, summary, explanation = calculate_weather_factor(forecast, "Cong nghiep")

    thap = explanation.lower()
    assert not ("bất lợi" in thap and "thuận lợi" in thap), (
        f"Câu giải thích tự mâu thuẫn: {explanation}"
    )


def test_neu_da_so_ngay_dep_thi_khong_goi_la_bat_loi():
    forecast = [_ngay("optimal")] * 6 + [_ngay("rainy", rainfall=12.0)]

    _, _, explanation = calculate_weather_factor(forecast, "Cong nghiep")

    assert "bất lợi" not in explanation.lower(), (
        f"6/7 ngày thuận lợi mà vẫn gọi là bất lợi: {explanation}"
    )


def test_thoi_tiet_that_su_xau_van_phai_canh_bao():
    """Không siết nhầm: mưa cực lớn cả tuần thì đúng là bất lợi."""
    forecast = [_ngay("extreme_rain", rainfall=60.0)] * 7

    factor, _, explanation = calculate_weather_factor(forecast, "Rau cu")

    assert factor > 1.0
    # Nêu đích danh điều kiện xấu và số ngày, rõ hơn nhãn "bất lợi" chung chung.
    assert "mưa cực lớn" in explanation.lower(), explanation
    assert "7/7" in explanation, explanation


def test_khong_viet_hoa_lung_tung_giua_cau():
    """`summary.lower()` biến '30°C' thành '30°c' ngay giữa câu."""
    forecast = [_ngay("optimal")] * 5 + [_ngay("heavy_rain", rainfall=25.0)] * 2

    _, _, explanation = calculate_weather_factor(forecast, "Cong nghiep")

    assert not re.search(r"\d°c\b", explanation), (
        f"Đơn vị nhiệt độ bị viết thường: {explanation}"
    )


def test_giai_thich_neu_ro_bao_nhieu_ngay_xau():
    """Nói '2/7 ngày mưa lớn' hữu ích hơn là dán nhãn chung chung."""
    forecast = [_ngay("optimal")] * 5 + [_ngay("heavy_rain", rainfall=25.0)] * 2

    _, _, explanation = calculate_weather_factor(forecast, "Cong nghiep")

    assert "2/7" in explanation, f"Không nêu số ngày bất lợi: {explanation}"
