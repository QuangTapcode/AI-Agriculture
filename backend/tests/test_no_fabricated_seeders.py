"""
TDD: không script nào được bịa dữ liệu rồi gắn nhãn nguồn chính thống.

seed_prices.py nhét giá cứng vào MarketPrices kèm:
    SOURCE_NAME = "Thông tin thị trường nông sản"
    SOURCE_URL  = "https://thitruongnongsan.gov.vn/vn/nguonwmy.aspx"

Nguy hiểm hơn mock thường: người đọc không thể phân biệt với giá thật do
crawler lấy về, vì nó mang đúng nhãn nguồn chính phủ. Vi phạm TOD0 §1.

Seed danh mục cây trồng (CropTypes) thì hợp lệ — đó là dữ liệu tham chiếu,
không phải số liệu thị trường.
"""
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
BANG_THI_TRUONG = ("MarketPrice", "PriceHistory", "MarketNews", "WeatherData")
NHAN_NGUON_THAT = ("thitruongnongsan.gov.vn", "Thông tin thị trường nông sản",
                   "Open-Meteo")


def _file_python_goc():
    """Script ở gốc backend/ — bỏ qua app/, tests/, venv/."""
    return [p for p in BACKEND.glob("*.py")]


def test_khong_script_nao_bia_du_lieu_thi_truong():
    pham_loi = []
    for p in _file_python_goc():
        text = p.read_text(encoding="utf-8", errors="ignore")
        ghi_bang_thi_truong = any(b in text for b in BANG_THI_TRUONG)
        gan_nhan_nguon = any(n in text for n in NHAN_NGUON_THAT)
        if ghi_bang_thi_truong and gan_nhan_nguon and "INSERT" not in text.upper():
            # co ghi bang thi truong + gan nhan nguon that
            if "add(" in text or "bulk_save" in text:
                pham_loi.append(p.name)

    assert not pham_loi, (
        f"Script bịa dữ liệu thị trường gắn nhãn nguồn thật: {pham_loi}"
    )


def test_seed_prices_da_bi_xoa():
    assert not (BACKEND / "seed_prices.py").exists(), (
        "seed_prices.py vẫn còn — nó nhét giá cứng mạo danh thitruongnongsan.gov.vn"
    )
