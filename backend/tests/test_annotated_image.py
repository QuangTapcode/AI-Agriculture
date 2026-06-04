"""
TDD: annotated image generation with numbered fruit boxes.
"""
import base64
import cv2
import numpy as np
import pytest
from ai_models.fruit_quality_pipeline import draw_annotated, FruitQualityPipeline


# ── Cycle 1: draw_annotated ────────────────────────────────────────────────

def _sample_detections():
    return [
        {
            "fruit_type": "Mango",  "fruit_type_vi": "Xoài",
            "grade": "grade_1",     "grade_label_vi": "Loại 1",
            "grade_color": "#22c55e", "confidence": 0.88,
            "bbox": [50, 50, 200, 200],
        },
        {
            "fruit_type": "Mango",  "fruit_type_vi": "Xoài",
            "grade": "grade_2",     "grade_label_vi": "Loại 2",
            "grade_color": "#eab308", "confidence": 0.72,
            "bbox": [220, 50, 380, 200],
        },
    ]


def test_draw_annotated_returns_ndarray():
    img = np.ones((400, 500, 3), dtype=np.uint8) * 200
    result = draw_annotated(img, _sample_detections())
    assert isinstance(result, np.ndarray)
    assert result.shape == img.shape


def test_draw_annotated_does_not_modify_original():
    img = np.ones((400, 500, 3), dtype=np.uint8) * 200
    original = img.copy()
    draw_annotated(img, _sample_detections())
    np.testing.assert_array_equal(img, original)


def test_draw_annotated_empty_detections():
    img = np.ones((300, 300, 3), dtype=np.uint8) * 150
    result = draw_annotated(img, [])
    assert result.shape == img.shape  # returns unchanged image


# ── Cycle 2: analyze() includes annotated_b64 ─────────────────────────────

def test_analyze_returns_annotated_b64_when_detections_exist(tmp_path):
    # Create a simple green image (unlikely to detect fruit, but shouldn't crash)
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    img[:, :, 1] = 180
    p = str(tmp_path / "test.jpg")
    cv2.imwrite(p, img)

    pipeline = FruitQualityPipeline(model_path="ai_models/weights/best.pt")
    result = pipeline.analyze(p)

    # annotated_b64 must always be present (even if empty detections)
    assert "annotated_b64" in result
    # If base64 is non-empty, it must be valid base64 PNG/JPG
    if result["annotated_b64"]:
        decoded = base64.b64decode(result["annotated_b64"])
        assert len(decoded) > 100   # at least some bytes


def test_analyze_summary_contains_total(tmp_path):
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    p = str(tmp_path / "test.jpg")
    cv2.imwrite(p, img)

    pipeline = FruitQualityPipeline(model_path="ai_models/weights/best.pt")
    result = pipeline.analyze(p)
    assert "total" in result["summary"]
    assert isinstance(result["summary"]["total"], int)
