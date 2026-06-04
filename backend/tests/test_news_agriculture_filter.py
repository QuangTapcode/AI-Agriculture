"""
TDD: market news filter — chỉ lấy tin liên quan đến nông sản.

Public interface under test:
    MarketNewsService._is_agriculture_production_news(item: dict) -> bool
"""
import pytest
from app.services.market_news_service import MarketNewsService

svc = MarketNewsService()
check = svc._is_agriculture_production_news


# ── Cycle 1: Tin nông sản rõ ràng → PASS ──────────────────────────────────

def test_coffee_price_article_passes():
    assert check({"title": "Giá cà phê Robusta tăng mạnh tại Đắk Lắk", "summary": "", "source_name": ""})


def test_rice_export_article_passes():
    assert check({"title": "Xuất khẩu gạo Việt Nam đạt kỷ lục trong quý 1", "summary": "", "source_name": ""})


def test_vegetable_price_article_passes():
    assert check({"title": "Giá rau củ tăng mạnh sau mưa lớn", "summary": "", "source_name": ""})


def test_agriculture_source_passes_even_without_keyword():
    # Nguồn báo nông nghiệp → luôn pass dù title không có keyword
    assert check({"title": "Tin tức hôm nay", "summary": "", "source_name": "Nông nghiệp - VnExpress RSS"})


def test_pepper_article_passes():
    assert check({"title": "Hồ tiêu Bình Phước giảm giá tuần thứ ba", "summary": "", "source_name": ""})


def test_shrimp_aquaculture_passes():
    assert check({"title": "Người nuôi tôm vùng ĐBSCL trúng vụ", "summary": "", "source_name": ""})


# ── Cycle 2: Tin không liên quan → FAIL ───────────────────────────────────

def test_aviation_article_rejected():
    assert not check({
        "title": "Vietjet hợp tác EECO phát triển trung tâm kỹ thuật",
        "summary": "Hãng hàng không Vietjet ký kết hợp tác với EECO.",
        "source_name": "Kinh doanh - VnExpress RSS",
    })


def test_real_estate_article_rejected():
    assert not check({
        "title": "Thị trường bất động sản TP.HCM tháng 5 trầm lắng",
        "summary": "Giao dịch nhà đất giảm mạnh trong tháng qua.",
        "source_name": "Kinh doanh - VnExpress RSS",
    })


def test_banking_article_rejected():
    assert not check({
        "title": "Ngân hàng Nhà nước điều chỉnh lãi suất điều hành",
        "summary": "Quyết định giảm lãi suất được kỳ vọng hỗ trợ tăng trưởng.",
        "source_name": "Kinh doanh - VnExpress RSS",
    })


def test_stock_market_article_rejected():
    assert not check({
        "title": "VN-Index tăng hơn 10 điểm phiên chiều",
        "summary": "Cổ phiếu ngân hàng và bất động sản dẫn dắt thị trường chứng khoán.",
        "source_name": "Kinh doanh - VnExpress RSS",
    })


def test_tech_company_article_rejected():
    assert not check({
        "title": "FPT Software ký hợp đồng lớn với đối tác Nhật Bản",
        "summary": "Hợp đồng xuất khẩu phần mềm trị giá hàng triệu USD.",
        "source_name": "Kinh doanh - VnExpress RSS",
    })


# ── Cycle 4: Diacritic collision edge cases ────────────────────────────────

def test_rocket_article_rejected():
    # "tên lửa" (rocket) normalizes to "ten lua" — must NOT match "lúa" (rice)
    assert not check({
        "title": "Tiêm kích NATO phóng tên lửa hạ UAV Ukraine tại Estonia",
        "summary": "Tiêm kích F-16 phóng tên lửa phòng không.",
        "source_name": "Tin mới nhất - VnExpress RSS",
    })


def test_oil_article_rejected():
    assert not check({
        "title": "IEA cảnh báo tồn kho dầu thương mại chỉ còn vài tuần",
        "summary": "Giá dầu thô tăng do lo ngại nguồn cung thiếu hụt.",
        "source_name": "Kinh doanh - VnExpress RSS",
    })


# ── Cycle 3: Edge cases ────────────────────────────────────────────────────

def test_agricultural_export_passes():
    # "xuất khẩu" alone is too broad, but "xuất khẩu nông sản" must pass
    assert check({"title": "Xuất khẩu nông sản Việt Nam đạt 5 tỷ USD", "summary": "", "source_name": ""})


def test_generic_export_without_agri_context_rejected():
    # "xuất khẩu" alone — no agriculture context — should fail
    assert not check({
        "title": "Xuất khẩu dệt may tăng trưởng ấn tượng",
        "summary": "Kim ngạch xuất khẩu hàng dệt may đạt 2 tỷ USD.",
        "source_name": "Kinh doanh - VnExpress RSS",
    })
