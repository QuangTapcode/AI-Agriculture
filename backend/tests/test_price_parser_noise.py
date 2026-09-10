"""
Bộ bóc giá không được biến số bất kỳ trên trang thành giá nông sản.

thitruong_nongsan_price_client bóc bảng trước; hỏng thì rơi xuống
_parse_text_fallback quét regex trên toàn bộ text của trang. Regex đó cho
phép "tên mặt hàng" là chuỗi TOÀN CHỮ SỐ:

    (?P<product>[A-Za-zÀ-ỹ0-9\s\-]{3,80}) ... (?P<price>\d{4,7})

Trên trang thật, bộ đếm lượt truy cập "75373839" khớp thành
product="7537", price=3839 — và _infer_crop_name gán nó cho đúng cây đang
được hỏi. Kết quả đo thật:

    Cà phê    | Việt Nam | 3.839 đ/kg
    Lúa       | Việt Nam | 3.839 đ/kg
    Hồ tiêu   | Việt Nam | 3.839 đ/kg
    Sầu riêng | Việt Nam | 3.839 đ/kg

Tám cây cùng một con số, lưu với is_mock=False và nguồn "Thông tin thị
trường nông sản". Cà phê thật khoảng 96.000 đ/kg.

TOD0 §1: thà không có số còn hơn có số sai đứng tên cơ quan nhà nước.
"""
from datetime import datetime

import pytest
from bs4 import BeautifulSoup

from app.integrations.thitruong_nongsan_price_client import (
    thitruong_nongsan_price_client as client,
)


def _boc(html, crop="ca phe"):
    return client._parse_text_fallback(
        BeautifulSoup(html, "html.parser"),
        normalized_crop=crop,
        normalized_region="",
        fetched_at=datetime.now(),
    )


def test_bo_dem_luot_truy_cap_khong_phai_gia():
    """Con số trần trên trang không phải giá nông sản."""
    kq = _boc("<div>Lượt truy cập 75373839</div>")

    assert not kq, f"Biến bộ đếm thành {len(kq)} bản ghi giá: {[r['price'] for r in kq]}"


def test_ten_mat_hang_phai_co_chu():
    kq = _boc("<div>7537 3839</div>")

    assert not kq, "Chuỗi toàn chữ số được nhận là tên mặt hàng"


def test_khong_gan_bua_cho_cay_dang_hoi():
    """Trang nói về hồ tiêu thì không được ghi thành giá cà phê."""
    kq = _boc("<div>Hồ tiêu 145000 đ/kg</div>", crop="ca phe")

    assert all("tieu" not in r["crop_name"] or r["crop_name"] == "ho tieu" for r in kq)
    assert not any(r["crop_name"] == "ca phe" for r in kq), (
        "Gán giá hồ tiêu thành giá cà phê vì đó là cây đang được hỏi"
    )


def test_van_boc_duoc_gia_that():
    """Không siết nhầm: dòng giá đúng định dạng vẫn phải lấy được."""
    kq = _boc("<div>Cà phê nhân xô 96.400 đ/kg</div>", crop="ca phe")

    assert kq, "Bỏ sót dòng giá hợp lệ"
    assert any(abs(r["price"] - 96400) < 1 for r in kq), [r["price"] for r in kq]
