"""
Tên vùng chứa ngày tháng là dấu hiệu bóc tách hỏng, không phải địa danh.

Trong DB thật có 5 bản ghi như thế, đều từ thitruongnongsan.gov.vn:

    Hồ tiêu | 'Lắk 04-08-2026 9' |  6.433 đ/kg
    Hồ tiêu | 'Lắk 22-06-2026 8' |  9.233 đ/kg

Regex bóc text để nhóm `region` nuốt cả ngày tháng lẫn chữ số đầu của giá:
"Đắk Lắk 04-08-2026 96.433" bị cắt thành region="Lắk 04-08-2026 9" và
price="6.433". Hồ tiêu thật khoảng 137.000 đ/kg — sai hơn 20 lần.

clean_price_records đã chặn giá ngoài khoảng [_PRICE_MIN, _PRICE_MAX] và
text hỏng, nhưng 6.433 vẫn nằm trong khoảng hợp lệ nên lọt. Tên vùng mới
là chỗ lộ ra rằng cả dòng đã hỏng.
"""
from datetime import date

from app.services.data_quality_service import clean_price_records


def _ban_ghi(region, price=6433.0, crop="ho tieu"):
    return {
        "crop_name": crop, "region": region, "price": price,
        "price_date": date.today().isoformat(),
        "source_name": "Thông tin thị trường nông sản",
        "source_url": "https://thitruongnongsan.gov.vn/vn/nguonwmy.aspx",
    }


def test_loai_ten_vung_nuot_ngay_thang():
    sach, bo = clean_price_records([_ban_ghi("Lắk 04-08-2026 9")])

    assert not sach, "Nhận tên vùng 'Lắk 04-08-2026 9' là địa danh hợp lệ"
    assert bo, "Bị loại nhưng không ghi vào danh sách từ chối"


def test_loai_ten_vung_co_chu_so():
    sach, _ = clean_price_records([_ban_ghi("Gia Lai 8")])

    assert not sach


def test_giu_ten_vung_binh_thuong():
    """Không siết nhầm: địa danh thật phải qua được."""
    sach, bo = clean_price_records([_ban_ghi("Gia Lai", price=137000.0)])

    assert sach, f"Loại nhầm địa danh hợp lệ: {bo}"


def test_giu_ten_vung_co_dau_va_nhieu_tu():
    sach, bo = clean_price_records([_ban_ghi("Bà Rịa - Vũng Tàu", price=137000.0)])

    assert sach, f"Loại nhầm: {bo}"
