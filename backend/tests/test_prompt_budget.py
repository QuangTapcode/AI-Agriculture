"""
TDD: prompt phải vừa cửa sổ ngữ cảnh của model, đo trước khi gửi.

Đo thật trên corpus khuyến nông với GTX 1650 4GB: prompt RAG dao động
1106–4025 token. Mức num_ctx 3072 làm Ollama trả 400 ("request exceeds the
available context size") đúng ở những câu cần tài liệu nhất — trợ lý hỏng
lặng lẽ ở chỗ nó tồn tại để phục vụ. Nâng num_ctx lên cho vừa thì 16/37 lớp
rớt xuống CPU và mỗi câu mất 30–55 giây.

Lối ra không phải chọn một trong hai, mà là không gửi đi prompt dài hơn chỗ
đã có. Cắt thì mất bớt chữ; không cắt thì mất cả câu trả lời.
"""
import pytest

from app.services.prompt_budget import (
    cat_van_ban,
    gioi_han_bang_chung,
    uoc_luong_token,
)


def test_uoc_luong_token_tang_theo_do_dai():
    assert uoc_luong_token("") == 0
    assert uoc_luong_token("Chăm sóc lúa") < uoc_luong_token("Chăm sóc lúa sau mưa bão kéo dài")


def test_cat_van_ban_giu_duoi_ngan_sach():
    van_ban = "Tiêu úng nhanh cho ruộng lúa. " * 200

    ket_qua = cat_van_ban(van_ban, 100)

    assert uoc_luong_token(ket_qua) <= 100
    assert len(ket_qua) < len(van_ban)


def test_cat_van_ban_danh_dau_cho_bi_cat():
    """Người đọc log phải phân biệt được "tài liệu chỉ có vậy" với "đã bị cắt"."""
    ket_qua = cat_van_ban("Tiêu úng nhanh cho ruộng lúa. " * 200, 50)

    assert "…" in ket_qua or "[cắt" in ket_qua


def test_van_ban_ngan_hon_ngan_sach_thi_giu_nguyen():
    assert cat_van_ban("Tiêu úng nhanh.", 100) == "Tiêu úng nhanh."


def test_cat_bang_chung_giu_du_moi_trich_dan():
    """Cắt ngắn đoạn trích thì được, bỏ hẳn một nguồn thì không.

    Bỏ nguồn đi là làm hỏng chính thứ đang đo: câu trả lời trích dẫn [TL3]
    trong khi [TL3] không còn trong prompt thì trích dẫn thành vô nghĩa, và
    người dùng không lần được về tài liệu gốc.
    """
    sources = [
        {"citation": f"TL{i}", "name": f"tai-lieu-{i}.txt",
         "excerpt": "Tiêu úng nhanh cho ruộng lúa. " * 100}
        for i in range(1, 6)
    ]

    ket_qua = gioi_han_bang_chung(sources, 300)

    assert len(ket_qua) == 5
    assert [item["citation"] for item in ket_qua] == ["TL1", "TL2", "TL3", "TL4", "TL5"]
    assert uoc_luong_token(" ".join(item["excerpt"] for item in ket_qua)) <= 300


def test_cat_bang_chung_khong_lam_gi_khi_da_vua():
    sources = [{"citation": "TL1", "excerpt": "Tiêu úng nhanh."}]

    assert gioi_han_bang_chung(sources, 500) == sources


def test_khong_co_nguon_thi_tra_ve_rong():
    assert gioi_han_bang_chung([], 100) == []
    assert gioi_han_bang_chung(None, 100) == []


@pytest.mark.parametrize("ngan_sach", [1, 5, 20])
def test_ngan_sach_qua_nho_van_khong_vo(ngan_sach):
    """Ngân sách bé tí là cấu hình sai, nhưng không được ném lỗi giữa lượt hỏi."""
    sources = [{"citation": "TL1", "excerpt": "Tiêu úng nhanh cho ruộng lúa. " * 50}]

    ket_qua = gioi_han_bang_chung(sources, ngan_sach)

    assert len(ket_qua) == 1
    assert isinstance(ket_qua[0]["excerpt"], str)


def test_prompt_lap_rap_khong_vuot_cua_so_ngu_canh():
    """Kiểm ở chỗ prompt thật sự được lắp, không chỉ ở hàm cắt.

    Hàm cắt đúng mà không ai gọi thì Ollama vẫn trả 400. Test này dựng đúng
    ca tệ nhất đo được: 6 đoạn tài liệu dài cộng context backend phình to.
    """
    from app.api.ai_chat import AIChatMessageRequest, _build_gemini_prompt
    from app.core.config import settings
    from app.services.prompt_budget import uoc_luong_token

    context = {
        "intent": "cultivation_advice",
        "crop_name": "lúa",
        "region": "Đồng Tháp",
        "rag": {"status": "ready", "sources": [
            {"citation": f"TL{i}", "name": f"tai-lieu-{i}.txt", "page": i,
             "source_name": "Khuyến nông Quốc gia",
             "excerpt": "Tiêu úng nhanh cho ruộng lúa sau mưa bão kéo dài. " * 60}
            for i in range(1, 7)
        ]},
        "pricing": {"avg_price": 9600, "ghi_chu": "chi tiết dài " * 300},
        "weather_forecast": [{"ngay": f"2026-09-{n:02d}", "mo_ta": "mưa rào " * 40}
                             for n in range(1, 8)],
    }
    request = AIChatMessageRequest(message="Ruộng lúa bị úng ngập thì xử lý thế nào?")

    system_instruction, prompt = _build_gemini_prompt(request, context)

    tran = settings.AI_CONTEXT_TOKENS - settings.AI_MAX_OUTPUT_TOKENS
    assert uoc_luong_token(system_instruction + prompt) <= tran

    # Cắt ngắn thì được, đánh rơi nguồn thì không.
    for i in range(1, 7):
        assert f"[TL{i}]" in prompt, f"Mất nguồn TL{i} khỏi prompt"
