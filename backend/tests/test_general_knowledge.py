"""
TDD: phân biệt SỐ LIỆU THỊ TRƯỜNG với KIẾN THỨC CANH TÁC.

SYSTEM_RULES ban đầu viết để chặn bịa giá — nơi bịa thật sự nguy hiểm. Nhưng
nó áp nhầm sang mọi câu hỏi, khiến trợ lý nông nghiệp từ chối chính câu hỏi
nông nghiệp cơ bản. Đo thực tế với qwen2.5:3b:

    "Cà chua trồng bao lâu thì thu hoạch?"  -> "Tôi chưa có dữ liệu về việc này"
    "Một hecta lúa cần bao nhiêu lít nước?" -> "Tôi chưa có dữ liệu về việc này"

Trớ trêu: dự án đã có sẵn bảng CROP_GROWTH_DAYS ghi "Cà chua: 75 ngày".

Ranh giới đúng:
  - Giá / thời tiết cụ thể  -> BẮT BUỘC từ DỮ LIỆU (bịa = nông dân mất tiền)
  - Kiến thức canh tác chung -> được dùng hiểu biết chung, nhưng không giả vờ
    đó là số liệu hệ thống
"""
from app.integrations.ai_grounding import SYSTEM_RULES, tra_cuu_kien_thuc_cay_trong


def test_quy_tac_cho_phep_kien_thuc_canh_tac():
    rules = SYSTEM_RULES.lower()
    assert "kiến thức" in rules or "kinh nghiệm" in rules, (
        "SYSTEM_RULES chưa cho phép dùng kiến thức canh tác phổ thông"
    )


def test_quy_tac_van_cam_bia_gia_va_thoi_tiet():
    """Nới cho kiến thức chung KHÔNG được nới cho số liệu thị trường."""
    rules = SYSTEM_RULES.lower()
    assert "giá" in rules and "thời tiết" in rules, (
        "Mất ranh giới: phải nêu rõ giá/thời tiết bắt buộc lấy từ DỮ LIỆU"
    )


def test_tra_cuu_duoc_thoi_gian_sinh_truong_tu_bang_co_san():
    """CROP_GROWTH_DAYS đã có trong dự án — dùng nó thay vì để model đoán."""
    assert "75" in tra_cuu_kien_thuc_cay_trong("Cà chua trồng bao lâu thu hoạch?")


def test_nhan_ra_ten_cay_khong_dau():
    assert "75" in tra_cuu_kien_thuc_cay_trong("ca chua bao lau thu hoach?")


def test_cay_khong_co_trong_bang_thi_tra_rong():
    """Không bịa: cây lạ thì không thêm gì vào context."""
    assert tra_cuu_kien_thuc_cay_trong("Cây thanh long ruột tím xyz?") == ""


def test_cau_hoi_khong_ve_sinh_truong_thi_tra_rong():
    """Chỉ bổ sung khi câu hỏi thực sự về thời gian trồng/thu hoạch."""
    assert tra_cuu_kien_thuc_cay_trong("Giá cà chua hôm nay?") == ""
