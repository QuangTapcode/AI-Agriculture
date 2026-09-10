"""
Lớp bọc phản hồi không được tính lại tuổi dữ liệu.

api_response nhận dict của service rồi tự tính:

    fetched_at = fetched_at or last_updated or datetime.now()
    data_age_minutes = (datetime.now() - fetched_at) tính ra phút

Nghĩa là nó đo LÚC TA GỌI API, ghi đè con số mà service đã tính từ lúc dữ
liệu được ghi nhận. Kết quả mâu thuẫn ngay trong một phản hồi:

    cache_status     = miss     (giá ghi nhận 04/08, đã 37 ngày)
    data_age_minutes = 2        (vừa fetch xong 2 phút trước)

Người đọc không biết tin vế nào. Service đã biết tuổi thật thì lớp bọc phải
giữ nguyên.
"""
from datetime import datetime, timedelta

from app.api.response import api_response


def test_giu_tuoi_do_service_tinh():
    bay_gio = datetime.now()
    du_lieu = {
        "current_price": 96433.0,
        "cache_status": "miss",
        "data_age_minutes": 37 * 24 * 60,
        "fetched_at": bay_gio,
        "last_updated": bay_gio,
    }

    kq = api_response(du_lieu)

    assert kq["data_age_minutes"] == 37 * 24 * 60, (
        f"Lớp bọc tính lại thành {kq['data_age_minutes']} phút, "
        f"xoá mất tuổi thật service đã tính"
    )


def test_van_tu_tinh_khi_service_khong_cho_biet():
    """Không siết nhầm: service không tính thì lớp bọc vẫn phải tính."""
    kq = api_response({"x": 1, "fetched_at": datetime.now() - timedelta(minutes=45)})

    assert 40 <= kq["data_age_minutes"] <= 50, kq["data_age_minutes"]


def test_khong_mau_thuan_giua_cache_status_va_tuoi():
    bay_gio = datetime.now()
    kq = api_response({
        "cache_status": "miss",
        "data_age_minutes": 50000,
        "fetched_at": bay_gio,
    })

    assert kq["cache_status"] == "miss"
    assert kq["data_age_minutes"] > 1440, (
        "Báo miss nhưng tuổi dưới một ngày — hai con số nói ngược nhau"
    )
