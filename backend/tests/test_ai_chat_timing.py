from app.api.ai_chat import _success_payload


def test_success_payload_exposes_stage_timings_without_request_id():
    payload = _success_payload(
        reply="Có nguồn.",
        intent="general_question",
        crop=None,
        region=None,
        model_name="test-model",
        provider="local",
        context={"_timings": {
            "request_id": "private-id",
            "started": 0.0,
            "retrieval_ms": 12.5,
            "generation_ms": 34.5,
        }},
    )

    timings = payload["data"]["timings"]
    assert timings["retrieval_ms"] == 12.5
    assert timings["generation_ms"] == 34.5
    assert timings["total_ms"] >= 0
    assert "request_id" not in timings
