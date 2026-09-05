"""
TDD: gợi ý loại quả từ người dùng phải được hiểu như nhau ở mọi nhánh.

Pipeline có 2 bảng map tên Việt riêng biệt (`_HINT_TO_FRUIT` chuẩn hoá dấu, và
một `_HINT_MAP` cục bộ liệt kê tay cả 2 dạng). Hai bảng lệch nhau là mầm lỗi:
thêm rau củ đợt 2 mà quên một bảng thì một nhánh nhận ra, nhánh kia không.
"""
import pytest

from ai_models.fruit_quality_pipeline import resolve_fruit_hint


@pytest.mark.parametrize(
    "hint, expected_en",
    [
        ("xoài", "Mango"), ("xoai", "Mango"), ("XOÀI", "Mango"), ("  Xoài  ", "Mango"),
        ("chuối", "Banana"), ("chuoi", "Banana"),
        ("táo", "Apple"), ("tao", "Apple"),
        ("cam", "Orange"), ("CAM", "Orange"),
    ],
)
def test_hint_resolves_regardless_of_diacritics_and_case(hint, expected_en):
    en, vi = resolve_fruit_hint(hint)
    assert en == expected_en
    assert vi


def test_unknown_hint_resolves_to_empty():
    assert resolve_fruit_hint("cây lạ xyz") == ("", "")


def test_empty_hint_resolves_to_empty():
    assert resolve_fruit_hint("") == ("", "")
    assert resolve_fruit_hint("   ") == ("", "")
