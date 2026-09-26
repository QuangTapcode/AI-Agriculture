from app.api.ai_chat import _cultivation_no_source_reply


def test_missing_cultivation_evidence_keeps_requested_crop_in_guidance():
    reply = _cultivation_no_source_reply("nho", "Đà Nẵng")

    assert "nho" in reply
    assert "Robusta" not in reply


def _system_prompt():
    from app.api.ai_chat import AIChatMessageRequest, _build_gemini_prompt

    request = AIChatMessageRequest(message="Cà chua bị đốm lá xử lý thế nào?")
    system_instruction, _ = _build_gemini_prompt(request, {"intent": "quality_analysis"})
    return system_instruction.lower()


def test_khong_cho_phep_thay_nguon_bang_huong_dan_tong_quat():
    """Cổng grounding chặn ca KHÔNG CÓ NGUỒN NÀO. Ca còn lại tinh vi hơn:

    có tài liệu về cà chua nhưng không nói gì về đốm lá, model vẫn được gọi.
    Lúc đó quy tắc "chỉ đưa hướng dẫn tổng quát" chính là chỗ kiến thức không
    nguồn chui vào — dưới dạng lời khuyên nghe rất hợp lý.
    """
    rules = _system_prompt()

    assert "hướng dẫn tổng quát" not in rules
    assert "chưa đủ dữ liệu" in rules


def test_van_yeu_cau_trich_dan_khi_dung_tai_lieu():
    assert "[tl1]" in _system_prompt()
