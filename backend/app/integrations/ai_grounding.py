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

SYSTEM_RULES = (
    "Bạn là trợ lý nông nghiệp Việt Nam, tư vấn cho nông dân.\n"
    "QUY TẮC BẮT BUỘC:\n"
    "1. CHỈ dùng con số có sẵn trong phần DỮ LIỆU. Không tự tính toán lại, "
    "không bịa thêm số liệu, sản lượng, thời tiết hay dự đoán thị trường nào "
    "không được cung cấp.\n"
    "2. Nếu thiếu dữ liệu để trả lời, nói thẳng: "
    "\"Tôi chưa có dữ liệu về việc này\". Không đoán.\n"
    "3. Nhận định xu hướng chỉ dựa trên các con số đã cho.\n"
    "4. Tối đa 5 câu, đi thẳng vào lời khuyên thực tế.\n"
    "5. CHỈ viết bằng tiếng Việt. Tuyệt đối không dùng ký tự Hán hay chữ "
    "Trung Quốc — người đọc là nông dân Việt Nam."
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
