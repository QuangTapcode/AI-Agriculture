"""Metadata phản hồi không được bịa độ tin cậy khi service không báo cáo."""

from app.api.response import api_response


def test_missing_confidence_stays_absent_instead_of_zero():
    payload = api_response({"region": "Dak Lak", "price": 8200})

    assert payload["confidence"] is None
    assert payload["meta"]["confidence"] is None


def test_reported_confidence_is_passed_through_unchanged():
    payload = api_response({"region": "Dak Lak"}, confidence=0.91)

    assert payload["confidence"] == 0.91
    assert payload["meta"]["confidence"] == 0.91


def test_success_response_also_leaves_missing_confidence_absent():
    from app.api.response import success_response

    payload = success_response({"region": "Dak Lak"})

    assert payload["confidence"] is None
    assert payload["meta"]["confidence"] is None
