"""
TDD: kiến thức canh tác cũng phải có nguồn, không lấy từ trí nhớ của model.

Bản trước của file này nới luật theo hướng ngược lại: cho phép model dùng
"kiến thức nông nghiệp phổ thông" khi thiếu dữ liệu, vì trợ lý đang từ chối
cả những câu nông nghiệp cơ bản:

    "Cà chua trồng bao lâu thì thu hoạch?"  -> "Tôi chưa có dữ liệu về việc này"

Chẩn đoán lúc đó đúng — dự án đã có sẵn bảng CROP_GROWTH_DAYS ghi "Cà chua:
75 ngày" mà không ai đưa vào prompt. Nhưng cách chữa thì sai: nó mở cửa cho
model trả lời bất cứ điều gì nó "nhớ", kể cả liều lượng thuốc và phân bón,
không ai kiểm chứng được.

Cách chữa đúng là đưa số thật của hệ thống vào DỮ LIỆU (đã làm — xem
tra_cuu_kien_thuc_cay_trong) rồi đóng cửa kiến thức chung lại. Có nguồn thì
trả lời kèm nguồn; không có thì nói chưa đủ dữ liệu.
"""
from app.integrations.ai_grounding import SYSTEM_RULES, tra_cuu_kien_thuc_cay_trong


def test_quy_tac_khong_cho_phep_tra_loi_bang_kien_thuc_chung():
    rules = SYSTEM_RULES.lower()
    assert "kiến thức nông nghiệp phổ thông" not in rules, (
        "SYSTEM_RULES vẫn mở cửa cho model tự trả lời từ trí nhớ"
    )
    assert "kinh nghiệm chung" not in rules


def test_quy_tac_buoc_tra_loi_phai_dua_tren_du_lieu_duoc_cung_cap():
    rules = SYSTEM_RULES.lower()
    assert "dữ liệu" in rules
    assert "chưa đủ dữ liệu" in rules or "chưa có dữ liệu" in rules, (
        "Thiếu nguồn thì phải có câu chữ bắt model nói thẳng là chưa đủ dữ liệu"
    )


def test_quy_tac_van_cam_bia_gia_va_thoi_tiet():
    """Ranh giới cũ vẫn phải còn: giá và thời tiết bắt buộc lấy từ DỮ LIỆU."""
    rules = SYSTEM_RULES.lower()
    assert "giá" in rules and "thời tiết" in rules


def test_tra_cuu_duoc_thoi_gian_sinh_truong_tu_bang_co_san():
    """CROP_GROWTH_DAYS là số liệu CỦA HỆ THỐNG — vẫn là nguồn hợp lệ.

    Siết grounding không có nghĩa là vứt bỏ dữ liệu sẵn có của dự án. Nó chỉ
    cấm phần model tự nghĩ ra.
    """
    assert "75" in tra_cuu_kien_thuc_cay_trong("Cà chua trồng bao lâu thu hoạch?")


def test_so_lieu_tham_chieu_duoc_ghi_ro_la_cua_he_thong():
    """Người đọc phải biết con số đến từ đâu, không lẫn với model tự nói."""
    ket_qua = tra_cuu_kien_thuc_cay_trong("Cà chua trồng bao lâu thu hoạch?")
    assert "hệ thống" in ket_qua.lower()


def test_nhan_ra_ten_cay_khong_dau():
    assert "75" in tra_cuu_kien_thuc_cay_trong("ca chua bao lau thu hoach?")


def test_cay_khong_co_trong_bang_thi_tra_rong():
    """Không bịa: cây lạ thì không thêm gì vào context."""
    assert tra_cuu_kien_thuc_cay_trong("Cây thanh long ruột tím xyz?") == ""


def test_cau_hoi_khong_ve_sinh_truong_thi_tra_rong():
    """Chỉ bổ sung khi câu hỏi thực sự về thời gian trồng/thu hoạch."""
    assert tra_cuu_kien_thuc_cay_trong("Giá cà chua hôm nay?") == ""
