"""
Giữ prompt vừa cửa sổ ngữ cảnh của model local.

Vì sao cần: model chạy trên GPU 4GB nên num_ctx không thể mở rộng thoải mái —
mở tới 8192 thì 16/37 lớp rớt xuống CPU và mỗi câu trả lời mất 30–55 giây.
Nhưng prompt RAG đo thật trên corpus khuyến nông dao động 1106–4025 token, tức
là vượt mức 3072 ở đúng những câu có nhiều tài liệu nhất. Ollama không cắt hộ:
nó trả 400 và trợ lý mất cả câu trả lời.

Nguyên tắc cắt: thà đoạn trích ngắn đi còn hơn mất một nguồn. Câu trả lời
trích dẫn [TL3] trong khi [TL3] đã bị loại khỏi prompt thì trích dẫn thành vô
nghĩa — người dùng không lần được về tài liệu gốc, mà đó lại là toàn bộ lý do
hệ thống này có trích dẫn.
"""

from __future__ import annotations

import math

# Đo với qwen3 trên văn bản tiếng Việt có dấu. Ước lượng thấp hơn thực tế là
# nguy hiểm (prompt vẫn vượt ngưỡng, Ollama vẫn 400), nên con số này cố ý
# chặt hơn tỷ lệ quan sát được.
KY_TU_MOI_TOKEN = 2.6

_DAU_HIEU_CAT = " […cắt bớt cho vừa ngữ cảnh]"


def uoc_luong_token(text: str) -> int:
    """Ước lượng số token, không cần tokenizer của model.

    Nạp tokenizer thật vào backend chỉ để đếm là thêm một phụ thuộc nặng và
    một điểm hỏng nữa; ước lượng theo ký tự đủ dùng khi đã chừa biên an toàn.
    """
    return math.ceil(len(text or "") / KY_TU_MOI_TOKEN)


def cat_van_ban(text: str, so_token_toi_da: int) -> str:
    """Cắt về đúng ngân sách, ưu tiên dừng ở ranh giới từ."""
    text = text or ""
    if so_token_toi_da <= 0:
        return ""
    if uoc_luong_token(text) <= so_token_toi_da:
        return text

    gioi_han_ky_tu = max(1, int(so_token_toi_da * KY_TU_MOI_TOKEN) - len(_DAU_HIEU_CAT))
    cat = text[:gioi_han_ky_tu]
    khoang_trang = cat.rfind(" ")
    if khoang_trang > gioi_han_ky_tu * 0.6:
        cat = cat[:khoang_trang]
    return cat.rstrip() + _DAU_HIEU_CAT


def gioi_han_bang_chung(sources: list[dict] | None, so_token_toi_da: int) -> list[dict]:
    """Ép tổng đoạn trích về ngân sách mà vẫn giữ đủ mọi nguồn.

    Ngân sách chia đều cho từng nguồn thay vì cắt cụt từ cuối danh sách: mọi
    trích dẫn trong câu trả lời đều phải tra ngược được về prompt.
    """
    if not sources:
        return []
    tong = sum(uoc_luong_token(str(item.get("excerpt") or "")) for item in sources)
    if tong <= so_token_toi_da:
        return sources

    phan_moi_nguon = max(1, so_token_toi_da // len(sources))
    return [
        {**item, "excerpt": cat_van_ban(str(item.get("excerpt") or ""), phan_moi_nguon)}
        for item in sources
    ]


def ngan_sach_con_lai(*, context_tokens: int, output_tokens: int, da_dung: int,
                      du_phong: int = 192) -> int:
    """Chỗ còn lại cho phần có thể cắt, sau khi trừ phần bắt buộc.

    du_phong che sai số của ước lượng theo ký tự và phần khung chat template
    mà backend không nhìn thấy.
    """
    return max(0, context_tokens - output_tokens - da_dung - du_phong)
