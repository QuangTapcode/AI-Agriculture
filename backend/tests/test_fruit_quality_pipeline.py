"""
TDD: fruit quality pipeline — YOLO11 one-shot detection + quality classification.

Model classes: {FruitType} {QualityLevel}
  FruitType   : Apple, Banana, Mango, Orange
  QualityLevel: Fresh, Semifresh, Semirotten, Rotten
"""
import pytest
from ai_models.fruit_quality_pipeline import (
    parse_class_name,
    quality_to_grade,
    FruitQualityPipeline,
)


# ── Cycle 1: parse_class_name ──────────────────────────────────────────────

def test_parse_fresh_apple():
    assert parse_class_name("Apple Fresh") == ("Apple", "Fresh")

def test_parse_rotten_mango():
    assert parse_class_name("Mango Rotten") == ("Mango", "Rotten")

def test_parse_semirotten_banana():
    assert parse_class_name("Banana Semirotten") == ("Banana", "Semirotten")

def test_parse_semifresh_orange():
    assert parse_class_name("Orange Semifresh") == ("Orange", "Semifresh")


# ── Cycle 2: quality_to_grade ──────────────────────────────────────────────

def test_fresh_is_grade_1():
    g = quality_to_grade("Fresh")
    assert g["grade"] == "grade_1"
    assert g["label_vi"] == "Loại 1"

def test_semifresh_is_grade_2():
    g = quality_to_grade("Semifresh")
    assert g["grade"] == "grade_2"
    assert g["label_vi"] == "Loại 2"

def test_semirotten_is_grade_3():
    g = quality_to_grade("Semirotten")
    assert g["grade"] == "grade_3"
    assert g["label_vi"] == "Loại 3"

def test_rotten_is_damaged():
    g = quality_to_grade("Rotten")
    assert g["grade"] == "damaged"
    assert g["label_vi"] == "Hỏng"


# ── Cycle 3: pipeline output structure ─────────────────────────────────────

def test_pipeline_analyze_returns_required_keys(tmp_path):
    import numpy as np, cv2
    # Create a minimal white image as test input
    img = np.ones((640, 640, 3), dtype=np.uint8) * 255
    img_path = str(tmp_path / "test.jpg")
    cv2.imwrite(img_path, img)

    pipeline = FruitQualityPipeline(model_path="ai_models/weights/best.pt")
    result = pipeline.analyze(img_path)

    assert "detections" in result
    assert "summary" in result
    assert isinstance(result["detections"], list)
    # Each detection must have these keys
    for det in result["detections"]:
        assert "fruit_type" in det
        assert "fruit_type_vi" in det
        assert "quality_level" in det
        assert "grade" in det
        assert "grade_label_vi" in det
        assert "confidence" in det
        assert "bbox" in det
