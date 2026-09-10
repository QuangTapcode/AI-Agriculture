"""
Nguồn giá chính thống: gửi đúng form thì mới có dữ liệu.

thitruongnongsan.gov.vn/vn/nguonwmy.aspx là trang TRA CỨU ASP.NET, không
phải bảng giá tĩnh. Muốn có số phải POST kèm __VIEWSTATE, ngành hàng,
khoảng ngày — VÀ bốn checkbox `hiện_các_trường` chọn cột hiển thị.

Payload hiện tại thiếu đúng bốn checkbox đó, nên trang trả về:

    <table><tr><td>Không có dữ liệu.</td></tr></table>

_parse_prices không tìm thấy bảng nào (log "Parse tables yielded 0 records")
rồi rơi xuống _parse_text_fallback quét regex trên text — nguồn gốc của các
bản ghi 3.839 đ/kg và 'Lắk 04-08-2026 9'.

Thêm bốn checkbox thì trang trả bảng 23 dòng có cấu trúc:

    Tên mặt hàng | Thị trường | Loại giá | Đơn vị tính | Loại tiền | Nguồn | Ngày | Giá
    Cà phê Robusta nhân xô | Đắk Lắk | Thương lái thu mua | Vnđ/Kg | VNĐ | CTV | 04-08-2026 | 96.433
"""
from pathlib import Path

import pytest

from app.integrations.thitruong_nongsan_price_client import (
    thitruong_nongsan_price_client as client,
)

FIXTURE = Path(__file__).parent / "fixtures" / "thitruongnongsan_ca_phe.html"


def test_payload_co_checkbox_chon_cot():
    """Thiếu checkbox thì trang trả 'Không có dữ liệu' — đã đo trên nguồn thật."""
    import inspect

    ma = inspect.getsource(client._fetch_page_range)
    assert "hiện_các_trường" in ma, (
        "Payload không tick cột hiển thị nào, nguồn sẽ trả bảng rỗng"
    )


def test_boc_duoc_bang_ket_qua_that():
    """Fixture lấy trực tiếp từ nguồn ngày 10/09/2026."""
    html = FIXTURE.read_text(encoding="utf-8")

    ban_ghi = client._parse_prices(html, crop_name="ca phe", region=None)

    assert ban_ghi, "Không bóc được dòng nào từ bảng kết quả thật"
    gia = [r["price"] for r in ban_ghi]
    assert all(80000 <= g <= 110000 for g in gia), (
        f"Giá cà phê ngoài khoảng hợp lý: {sorted(set(gia))[:6]}"
    )


def test_lay_dung_vung_va_ngay():
    html = FIXTURE.read_text(encoding="utf-8")

    ban_ghi = client._parse_prices(html, crop_name="ca phe", region=None)
    vung = {r["region"] for r in ban_ghi}

    assert "Đắk Lắk" in vung, f"Không thấy Đắk Lắk trong {vung}"
    assert all(not any(k.isdigit() for k in v) for v in vung), (
        f"Tên vùng lẫn chữ số: {vung}"
    )
    assert all(r.get("price_date") for r in ban_ghi), "Thiếu ngày của giá"


def test_bo_qua_dong_phan_trang():
    """Hai dòng cuối bảng là link phân trang '1 2 3 4 5 6 7 8'."""
    html = FIXTURE.read_text(encoding="utf-8")

    ban_ghi = client._parse_prices(html, crop_name="ca phe", region=None)

    assert all(r["region"] not in {"1", "2", "3"} for r in ban_ghi)
    assert all(r["price"] > 1000 for r in ban_ghi), (
        f"Số thứ tự trang bị nhận là giá: {[r['price'] for r in ban_ghi if r['price'] <= 1000]}"
    )


def test_noi_cua_so_khi_nguon_tre():
    """Nguồn có thể chậm hàng tuần; cửa sổ 30 ngày cứng sẽ ra rỗng.

    Đo trên nguồn thật ngày 10/09/2026 (dữ liệu mới nhất 04/08):

        cửa sổ 30 ngày ->  0 bản ghi
        cửa sổ 60 ngày -> 20 bản ghi
        cửa sổ 90 ngày -> 20 bản ghi

    Hỏi 30 ngày rồi kết luận "không có giá" là sai — giá vẫn có, chỉ nằm
    ngoài cửa sổ. Nhưng cũng không nên luôn kéo 90 ngày khi nguồn đang
    cập nhật đều, nên nới dần.
    """
    from unittest.mock import patch

    goi = []

    def ghi_lai(tu, den):
        goi.append((den - tu).days)
        # Lần đầu (cửa sổ hẹp) trả rỗng, giống nguồn thật đang trễ.
        return "" if len(goi) == 1 else FIXTURE.read_text(encoding="utf-8")

    with patch.object(type(client), "_fetch_page_range", side_effect=lambda tu, den: ghi_lai(tu, den)):
        ban_ghi = client._fetch_page()

    assert len(goi) >= 2, f"Chỉ thử một cửa sổ {goi} rồi bỏ cuộc"
    assert max(goi) >= 60, f"Cửa sổ rộng nhất mới {max(goi)} ngày, chưa đủ khi nguồn trễ"
    assert ban_ghi, "Nới cửa sổ rồi vẫn không lấy được gì"
