"""
TDD: fruit type override when user provides crop_name hint.

Root cause: YOLO confuses orange-colored mangoes with oranges
because the training dataset has color/shape overlap.

Fix: trust user's crop selection for FRUIT TYPE,
     trust YOLO/EfficientNet for QUALITY LEVEL (Fresh/Rotten).

"Người dùng biết họ đang chụp quả gì — AI biết chất lượng."
"""
import pytest
from ai_models.fruit_quality_pipeline import override_fruit_type


# ── Cycle 1: override_fruit_type ──────────────────────────────────────────

def test_override_replaces_wrong_fruit_type():
    """User said 'xoai', YOLO said 'Orange' → should become 'Xoài'."""
    detections = [
        {
            "fruit_type": "Orange", "fruit_type_vi": "Cam",
            "quality_level": "Fresh", "grade": "grade_1",
            "confidence": 0.72,
        }
    ]
    result = override_fruit_type(detections, crop_name_hint="xoai")
    assert result[0]["fruit_type"] == "Mango"
    assert result[0]["fruit_type_vi"] == "Xoài"
    # Quality level must NOT change
    assert result[0]["quality_level"] == "Fresh"
    assert result[0]["grade"] == "grade_1"


def test_override_keeps_correct_fruit_type():
    """User said 'chuoi', YOLO said 'Banana' → no change needed."""
    detections = [
        {
            "fruit_type": "Banana", "fruit_type_vi": "Chuối",
            "quality_level": "Semifresh", "grade": "grade_2",
            "confidence": 0.91,
        }
    ]
    result = override_fruit_type(detections, crop_name_hint="chuoi")
    assert result[0]["fruit_type"] == "Banana"
    assert result[0]["fruit_type_vi"] == "Chuối"
    assert result[0]["quality_level"] == "Semifresh"


def test_override_handles_empty_hint():
    """No hint → detections unchanged."""
    detections = [{"fruit_type": "Apple", "fruit_type_vi": "Táo", "grade": "grade_1"}]
    result = override_fruit_type(detections, crop_name_hint="")
    assert result[0]["fruit_type"] == "Apple"


def test_override_handles_empty_detections():
    assert override_fruit_type([], "xoai") == []


def test_override_multiple_detections():
    """All detections get the same fruit type correction."""
    detections = [
        {"fruit_type": "Orange", "fruit_type_vi": "Cam", "quality_level": "Fresh",    "grade": "grade_1"},
        {"fruit_type": "Orange", "fruit_type_vi": "Cam", "quality_level": "Semirotten","grade": "grade_3"},
    ]
    result = override_fruit_type(detections, crop_name_hint="xoai")
    assert all(r["fruit_type"] == "Mango" for r in result)
    assert all(r["fruit_type_vi"] == "Xoài" for r in result)
    # Quality preserved per detection
    assert result[0]["quality_level"] == "Fresh"
    assert result[1]["quality_level"] == "Semirotten"


# ── Cycle 2: verify quality label stays correct ───────────────────────────

def test_reasoning_updated_after_override():
    """After override, reasoning should reference the correct fruit."""
    from ai_models.quality_enhancer import generate_reasoning
    # Simulate override result
    text = generate_reasoning("Xoài", "grade_1",
        {"dominant_hue": "cam", "freshness_score": 0.85,
         "saturation_level": "cao", "brightness_level": "sáng",
         "defect_ratio": 0.02, "color_uniformity": 0.90}, 0.72)
    # Reasoning should mention Xoài, not Cam
    assert "xoài" in text.lower() or "xoa" in text.lower()
