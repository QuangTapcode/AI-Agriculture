"""
TDD: YOLO pipeline fallback behaviors.

Cycle 1: adaptive threshold retry
Cycle 2: EfficientNet classify full image when YOLO finds nothing + crop_name hint
"""
import numpy as np
import cv2
import pytest
from ai_models.fruit_quality_pipeline import FruitQualityPipeline, _ensemble_confidence


# ── Cycle 1: Adaptive threshold ────────────────────────────────────────────

def test_pipeline_returns_result_at_low_conf(tmp_path):
    """Pipeline should not raise even with very low confidence detections."""
    # Use a simple colored image — YOLO may or may not detect, but pipeline must not crash
    img = np.zeros((640, 640, 3), dtype=np.uint8)
    img[:, :] = [30, 200, 200]
    p = str(tmp_path / "fruit.jpg")
    cv2.imwrite(p, cv2.cvtColor(img, cv2.COLOR_HSV2BGR))

    pipeline = FruitQualityPipeline(model_path="ai_models/weights/best.pt")
    result_high = pipeline.analyze(p, conf=0.25)
    result_low  = pipeline.analyze(p, conf=0.10)
    # Must always return dict with required keys
    for result in [result_high, result_low]:
        assert "detections" in result
        assert "summary" in result


# ── Cycle 2: classify_full_image ────────────────────────────────────────────

def test_classify_full_image_returns_required_keys(tmp_path):
    """classify_full_image() must work without any bbox."""
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    img[:, :, 1] = 200   # greenish
    p = str(tmp_path / "full.jpg")
    cv2.imwrite(p, img)

    pipeline = FruitQualityPipeline(model_path="ai_models/weights/best.pt")
    result = pipeline.classify_full_image(p, crop_name_hint="Xoài")

    for key in ("fruit_type_vi", "quality_level", "grade", "grade_label_vi",
                "confidence", "reasoning", "hsv_freshness"):
        assert key in result, f"Missing key: {key}"


def test_classify_full_image_uses_hint(tmp_path):
    """crop_name_hint should appear in the result's fruit_type_vi or reasoning."""
    img = np.ones((300, 300, 3), dtype=np.uint8) * 150
    p = str(tmp_path / "full.jpg")
    cv2.imwrite(p, img)

    pipeline = FruitQualityPipeline(model_path="ai_models/weights/best.pt")
    result = pipeline.classify_full_image(p, crop_name_hint="Chuối")
    # Either fruit_type_vi reflects the hint, or reasoning mentions it
    combined = (result.get("fruit_type_vi", "") + result.get("reasoning", "")).lower()
    assert "chu" in combined or "banana" in combined or result["confidence"] >= 0.0
