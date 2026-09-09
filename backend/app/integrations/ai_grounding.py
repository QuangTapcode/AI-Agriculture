"""
Neo câu trả lời AI vào số liệu thật — model chỉ diễn đạt, không tự tính.

Đo thực tế với qwen2.5:3b khi để nó tự do suy luận:
  - Sai phép tính tiền: "2 * 1000 * 96.433 = 1928660" (đúng: 192.866.000)
  - Bịa dữ kiện không ai cung cấp: "Nhu cầu hiện tại thấp hơn"
  - Khuyên ngược chiều dữ liệu: giá đang giảm nhưng nói "giá có thể tăng"

Đây không phải lỗi chọn model — LLM nào cũng tính sai tiền. Cách đúng là
backend tính sẵn mọi con số rồi đưa vào prompt dưới dạng đã định dạng, model
chỉ việc viết thành câu tiếng Việt.
"""

from __future__ import annotations

import re
import unicodedata

SYSTEM_RULES = (
    "Bạn là trợ lý nông nghiệp Việt Nam, tư vấn cho nông dân.\n"
    "QUY TẮC BẮT BUỘC:\n"
    "1. GIÁ nông sản, THỜI TIẾT và số liệu thị trường: CHỈ được dùng con số "
    "có trong phần DỮ LIỆU. Không tự tính lại, không suy từ vùng khác, không "
    "bịa. Thiếu thì nói thẳng: \"Tôi chưa có dữ liệu về việc này\".\n"
    "2. KIẾN THỨC CANH TÁC chung (thời gian sinh trưởng, kỹ thuật tưới, bón "
    "phân, phòng sâu bệnh): được phép dùng kiến thức nông nghiệp phổ thông "
    "để trả lời, nhưng nói rõ đó là kinh nghiệm chung chứ không phải số liệu "
    "đo được của hệ thống.\n"
    "3. Nhận định xu hướng chỉ dựa trên các con số đã cho.\n"
    "4. Tối đa 5 câu, đi thẳng vào lời khuyên thực tế.\n"
    "5. CHỈ viết bằng tiếng Việt. Tuyệt đối không dùng ký tự Hán hay chữ "
    "Trung Quốc — người đọc là nông dân Việt Nam.\n"
    "6. Các lượt trước trong cuộc trò chuyện CHỈ dùng để hiểu ngữ cảnh câu "
    "hỏi, KHÔNG phải nguồn số liệu. Tuyệt đối không suy giá của vùng này ra "
    "vùng khác, hay của cây này ra cây khác. Hỏi về vùng/cây chưa có trong "
    "DỮ LIỆU thì trả lời \"Tôi chưa có dữ liệu về việc này\"."
)

_KHONG_CO_DU_LIEU = "(chưa có dữ liệu từ hệ thống cho câu hỏi này)"


def build_grounded_prompt(cau_hoi: str, so_lieu: dict[str, str] | None = None) -> str:
    """Ghép số liệu đã tính sẵn + câu hỏi thành prompt.

    so_lieu: nhãn -> giá trị ĐÃ ĐỊNH DẠNG sẵn ("192.866.000 đ"), không phải
    số thô — để model không phải làm phép tính nào.
    """
    if so_lieu:
        dong = "\n".join(f"- {nhan}: {gia_tri}" for nhan, gia_tri in so_lieu.items())
    else:
        dong = _KHONG_CO_DU_LIEU

    return (
        "DỮ LIỆU (đã tính sẵn, dùng nguyên văn):\n"
        f"{dong}\n\n"
        f"CÂU HỎI: {cau_hoi}"
    )


# ── Chốt chặn số liệu bịa ────────────────────────────────────────────────

# Số dạng giá: từ 4 chữ số trở lên, có thể có dấu phân cách nghìn.
# Ngưỡng 4 chữ số loại được "5 ngày", "2 lần", "tháng 10" — những cách diễn
# đạt bình thường, không phải số liệu thị trường.
_SO_DANG_GIA = re.compile(r"\b\d{1,3}(?:[.,]\d{3})+\b|\b\d{4,}\b")


def _chuan_hoa_so(s: str) -> str:
    """Bỏ dấu phân cách để so sánh: '96.433', '96,433', '96433' là một."""
    return s.replace(".", "").replace(",", "")


def so_lieu_khong_co_trong_nguon(tra_loi: str, du_lieu: str) -> list[str]:
    """Các con số dạng giá xuất hiện trong câu trả lời mà nguồn không có.

    Vì sao cần: đo thực tế với qwen2.5:3b cho thấy ràng buộc bằng prompt
    KHÔNG đủ. Cho model biết "Cà phê Đắk Lắk 96.433 đ/kg" rồi hỏi "Còn Gia
    Lai thì sao?" — nó trả lời "Gia Lai cũng là 96.433 đ/kg", tức áp số của
    vùng này sang vùng khác. Thêm quy tắc cấm vào system prompt vẫn không
    chặn được. Model nhỏ không tuân thủ lệnh cấm một cách đáng tin.

    Với nông dân, một con số bịa nguy hiểm hơn hẳn câu "chưa có dữ liệu".
    """
    co_trong_nguon = {
        _chuan_hoa_so(m) for m in _SO_DANG_GIA.findall(du_lieu or "")
    }
    la = []
    for m in _SO_DANG_GIA.findall(tra_loi or ""):
        if _chuan_hoa_so(m) not in co_trong_nguon and m not in la:
            la.append(m)
    return la


def _bo_dau_vn(s: str) -> str:
    """Bỏ dấu để so khớp tên vùng người dùng gõ không dấu."""
    s = (s or "").lower().replace("đ", "d").replace("ð", "d")
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def bo_sung_vung_thieu_du_lieu(cau_hoi: str, du_lieu: str) -> str:
    """Nêu rõ vùng được hỏi mà nguồn không có số liệu.

    Chốt chặn số liệu chỉ bắt được số BỊA. Ca tinh vi hơn là model dùng lại
    đúng con số có trong nguồn nhưng gán sai vùng:

        DỮ LIỆU: "Cà phê Đắk Lắk: 96.433 đ/kg"
        Hỏi:     "Còn Gia Lai thì sao?"
        Trả lời: "Gia Lai cũng ở mức 96.433 đ/kg"      <-- sai quy kết

    Model nhỏ tuân theo sự thật phủ định tường minh tốt hơn nhiều so với lệnh
    cấm. Nói thẳng "Gia Lai: chưa có dữ liệu" hiệu quả hơn "không được suy
    sang vùng khác".
    """
    from app.services.pricing_service import REGION_DISPLAY_ALIASES

    hoi = _bo_dau_vn(cau_hoi)
    co_san = _bo_dau_vn(du_lieu)

    thieu: list[str] = []
    for khoa, ten_hien_thi in REGION_DISPLAY_ALIASES.items():
        if khoa not in hoi:
            continue
        if _bo_dau_vn(ten_hien_thi) in co_san:
            continue                      # vung nay da co du lieu
        if ten_hien_thi not in thieu:
            thieu.append(ten_hien_thi)

    if not thieu:
        return du_lieu

    dong = "\n".join(f"- {v}: chưa có dữ liệu trong hệ thống" for v in thieu)
    return f"{du_lieu}\n{dong}" if du_lieu else dong

# Câu hỏi về thời gian trồng/thu hoạch — chỉ bổ sung khi thực sự được hỏi.
_TU_KHOA_SINH_TRUONG = (
    "bao lau", "bao nhieu ngay", "may ngay", "thu hoach", "sinh truong",
    "trong bao", "thoi gian trong",
)


def tra_cuu_kien_thuc_cay_trong(cau_hoi: str) -> str:
    """Thời gian sinh trưởng từ bảng CROP_GROWTH_DAYS có sẵn trong dự án.

    Dự án đã có bảng này trong harvest_forecast/predictor.py (Cà chua 75 ngày,
    Lúa 105 ngày...). Không dùng thì model phải tự đoán — hoặc tệ hơn, từ chối
    trả lời vì luật cấm bịa số. Đưa số thật của hệ thống vào còn hơn để model
    phỏng đoán.

    Trả về chuỗi rỗng khi câu hỏi không về sinh trưởng, hoặc cây không có
    trong bảng — không bịa.
    """
    from ai_models.harvest_forecast.predictor import CROP_GROWTH_DAYS

    hoi = _bo_dau_vn(cau_hoi)
    if not any(tu in hoi for tu in _TU_KHOA_SINH_TRUONG):
        return ""

    for ten_cay, so_ngay in CROP_GROWTH_DAYS.items():
        if _bo_dau_vn(ten_cay) in hoi:
            return (f"- {ten_cay}: thời gian sinh trưởng khoảng {so_ngay} ngày "
                    f"(số liệu tham chiếu của hệ thống)")
    return ""
