from app.api.ai_chat import _cultivation_no_source_reply


def test_missing_cultivation_evidence_keeps_requested_crop_in_guidance():
    reply = _cultivation_no_source_reply("nho", "Đà Nẵng")

    assert "nho" in reply
    assert "Robusta" not in reply
