"""
TDD: quality enhancer — HSV analysis + confidence calibration + reasoning.

These run without a trained model (pure functions + OpenCV).
"""
import numpy as np
import pytest
from ai_models.quality_enhancer import (
    HSVAnalyzer,
    calibrate_confidence,
    generate_reasoning,
)


# ── Cycle 1: HSV color analysis ────────────────────────────────────────────

def _yellow_banana():
    """Synthetic bright yellow image — healthy banana."""
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:, :] = [30, 230, 220]   # HSV: yellow, high sat, high val → convert to BGR
    import cv2
    return cv2.cvtColor(img, cv2.COLOR_HSV2BGR)

def _brown_rotten():
    """Synthetic rotten fruit — dark, desaturated, many dark spots."""
    import cv2
    # Base: dark brown (H=18, S=70, V=45) — below V<50 threshold → high defect_ratio
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:, :] = [18, 70, 45]    # HSV: dark brown, low sat, very dark
    return cv2.cvtColor(img, cv2.COLOR_HSV2BGR)


def test_hsv_fresh_fruit_has_high_freshness():
    result = HSVAnalyzer().analyze(_yellow_banana())
    assert "freshness_score" in result
    assert result["freshness_score"] >= 0.6, f"Expected >= 0.6, got {result['freshness_score']}"


def test_hsv_rotten_fruit_has_low_freshness():
    result = HSVAnalyzer().analyze(_brown_rotten())
    assert result["freshness_score"] < 0.6, f"Expected < 0.6, got {result['freshness_score']}"


def test_hsv_returns_required_keys():
    result = HSVAnalyzer().analyze(_yellow_banana())
    for key in ("freshness_score", "dominant_hue", "saturation_level",
                "brightness_level", "defect_ratio", "color_uniformity"):
        assert key in result, f"Missing key: {key}"


def test_hsv_score_bounded_0_to_1():
    for img in [_yellow_banana(), _brown_rotten()]:
        r = HSVAnalyzer().analyze(img)
        assert 0.0 <= r["freshness_score"] <= 1.0


# ── Cycle 2: Confidence calibration ────────────────────────────────────────

def test_high_yolo_high_hsv_gives_high_confidence():
    conf = calibrate_confidence(yolo_conf=0.92, hsv_score=0.85, n_detections=1)
    assert conf >= 0.8


def test_low_yolo_low_hsv_gives_low_confidence():
    conf = calibrate_confidence(yolo_conf=0.30, hsv_score=0.25, n_detections=3)
    assert conf <= 0.5


def test_confidence_bounded():
    for yolo, hsv, n in [(0.0, 0.0, 0), (1.0, 1.0, 1), (0.5, 0.5, 2)]:
        c = calibrate_confidence(yolo, hsv, n)
        assert 0.0 <= c <= 1.0


# ── Cycle 3: Reasoning generation ──────────────────────────────────────────

def test_reasoning_grade1_contains_positive_words():
    text = generate_reasoning(
        fruit_type_vi="Chuối",
        grade="grade_1",
        hsv_result={"dominant_hue": "vàng tươi", "freshness_score": 0.90,
                    "saturation_level": "cao", "brightness_level": "bình thường",
                    "defect_ratio": 0.02, "color_uniformity": 0.85},
        confidence=0.93,
    )
    assert isinstance(text, str) and len(text) > 20
    # Should mention quality and fruit
    assert any(w in text.lower() for w in ["chất lượng", "tươi", "tốt", "loại 1", "chuoi", "chuối"])


def test_reasoning_damaged_contains_warning():
    text = generate_reasoning(
        fruit_type_vi="Táo",
        grade="damaged",
        hsv_result={"dominant_hue": "nâu đen", "freshness_score": 0.15,
                    "saturation_level": "thấp", "brightness_level": "tối",
                    "defect_ratio": 0.60, "color_uniformity": 0.20},
        confidence=0.88,
    )
    assert any(w in text.lower() for w in ["hỏng", "hư", "loại bỏ", "không", "xấu"])


def test_reasoning_returns_string():
    text = generate_reasoning("Xoài", "grade_2",
        {"dominant_hue": "vàng", "freshness_score": 0.55,
         "saturation_level": "trung bình", "brightness_level": "bình thường",
         "defect_ratio": 0.15, "color_uniformity": 0.60}, 0.70)
    assert isinstance(text, str)
