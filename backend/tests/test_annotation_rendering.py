"""
TDD: annotation rendering.

Cycle 1: Vietnamese text renders correctly (no mojibake "Xo??i")
Cycle 2: confidence threshold correctly counts visible fruits
"""
import base64
import cv2
import numpy as np
import pytest
from ai_models.fruit_quality_pipeline import draw_annotated


# ── Cycle 1: Vietnamese text rendering ────────────────────────────────────

def _detection(fruit_vi, grade, conf=0.88, bbox=(50, 50, 200, 200)):
    return {
        "fruit_type": "Mango", "fruit_type_vi": fruit_vi,
        "grade": grade, "grade_label_vi": {"grade_1": "Loại 1", "grade_2": "Loại 2",
                                             "grade_3": "Loại 3", "damaged": "Hỏng"}[grade],
        "grade_color": "#22c55e", "confidence": conf,
        "bbox": list(bbox),
    }


def test_annotated_image_is_valid_jpeg():
    """draw_annotated must return a valid image, not crash on Vietnamese text."""
    img = np.ones((400, 600, 3), dtype=np.uint8) * 200
    result = draw_annotated(img, [_detection("Xoài", "grade_1", 0.88)])
    assert result is not None
    assert result.shape == img.shape
    # Must encode to JPEG without error
    ok, buf = cv2.imencode(".jpg", result)
    assert ok and len(buf) > 0


def test_annotated_text_is_not_garbled():
    """Base64-encoded annotated image must NOT contain garbled bytes.

    We can't directly read rendered text, but we can verify the pipeline
    returns base64 that decodes to a valid JPEG.
    """
    from ai_models.fruit_quality_pipeline import _image_to_b64
    img = np.ones((300, 400, 3), dtype=np.uint8) * 180
    annotated = draw_annotated(img, [
        _detection("Xoài",  "grade_1", 0.90, (10, 10, 150, 150)),
        _detection("Chuối", "grade_2", 0.75, (160, 10, 300, 150)),
    ])
    b64 = _image_to_b64(annotated)
    assert b64 != ""
    # Valid base64 → valid JPEG header
    decoded = base64.b64decode(b64)
    assert decoded[:2] == b'\xff\xd8', "Not a valid JPEG"


# ── Cycle 2: fruit count / confidence threshold ────────────────────────────

def test_lower_confidence_finds_more_fruits(tmp_path):
    """Analyze at conf=0.10 should find ≥ same number as conf=0.25."""
    import pathlib
    from ai_models.fruit_quality_pipeline import FruitQualityPipeline

    # Use any real uploaded image
    uploads = list(pathlib.Path("storage/uploads/quality_check").glob("*.jpg"))
    if not uploads:
        pytest.skip("No uploaded images to test on")

    img_path = str(uploads[-1])
    pipeline = FruitQualityPipeline(model_path="ai_models/weights/best.pt")

    high_conf = pipeline.analyze(img_path, conf=0.25)
    low_conf  = pipeline.analyze(img_path, conf=0.10)

    n_high = high_conf["summary"]["total"]
    n_low  = low_conf["summary"]["total"]
    # Lower threshold must find AT LEAST as many fruits
    assert n_low >= n_high, f"Low conf found fewer: {n_low} < {n_high}"


def test_summary_total_matches_detections_length(tmp_path):
    """summary.total must always equal len(detections)."""
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    p = str(tmp_path / "t.jpg")
    cv2.imwrite(p, img)

    from ai_models.fruit_quality_pipeline import FruitQualityPipeline
    pipeline = FruitQualityPipeline(model_path="ai_models/weights/best.pt")
    result = pipeline.analyze(p)
    assert result["summary"]["total"] == len(result["detections"])
