"""
TDD: crop diagnostics and ensemble balance.

Cycle 1: save_debug_crops() saves each YOLO crop to disk
Cycle 2: class_distribution() reveals Rotten vs Fresh bias
Cycle 3: ensemble trusts CNN > YOLO for quality (fixes Hỏng bias)
"""
import cv2
import numpy as np
import pathlib
import pytest
from ai_models.fruit_quality_pipeline import save_debug_crops, FruitQualityPipeline


# ── Cycle 1: save_debug_crops ──────────────────────────────────────────────

def _detections_with_bboxes():
    return [
        {"fruit_type_vi": "Xoài", "grade_label_vi": "Loại 1",
         "confidence": 0.88, "bbox": [10, 10, 120, 120]},
        {"fruit_type_vi": "Xoài", "grade_label_vi": "Hỏng",
         "confidence": 0.64, "bbox": [130, 10, 240, 120]},
    ]


def test_save_debug_crops_creates_files(tmp_path):
    img = np.ones((200, 300, 3), dtype=np.uint8) * 150
    out_dir = tmp_path / "crops"
    save_debug_crops(img, _detections_with_bboxes(), out_dir=str(out_dir))
    files = list(out_dir.glob("*.jpg"))
    assert len(files) == 2, f"Expected 2 crop files, got {len(files)}"


def test_save_debug_crops_filenames_contain_index_and_grade(tmp_path):
    img = np.ones((200, 300, 3), dtype=np.uint8) * 180
    out_dir = tmp_path / "crops"
    save_debug_crops(img, _detections_with_bboxes(), out_dir=str(out_dir))
    names = [f.name for f in out_dir.glob("*.jpg")]
    assert any("1" in n for n in names)
    assert any("2" in n for n in names)


def test_save_debug_crops_empty_does_not_crash(tmp_path):
    img = np.ones((200, 200, 3), dtype=np.uint8) * 100
    out_dir = tmp_path / "empty"
    save_debug_crops(img, [], out_dir=str(out_dir))
    assert len(list(out_dir.glob("*.jpg"))) == 0


# ── Cycle 2: class_distribution reveals bias ─────────────────────────────

def test_class_distribution_counts_grades():
    from ai_models.fruit_quality_pipeline import grade_distribution
    detections = [
        {"grade": "grade_1"}, {"grade": "grade_1"},
        {"grade": "damaged"}, {"grade": "damaged"}, {"grade": "damaged"},
        {"grade": "grade_2"},
    ]
    dist = grade_distribution(detections)
    assert dist["grade_1"] == 2
    assert dist["damaged"] == 3
    assert dist["grade_2"] == 1
    assert dist["grade_3"] == 0


def test_class_distribution_detects_rotten_bias():
    from ai_models.fruit_quality_pipeline import grade_distribution, is_rotten_biased
    detections = [{"grade": "damaged"}] * 4 + [{"grade": "grade_1"}]
    dist = grade_distribution(detections)
    # 4/5 = 80% damaged → biased
    assert is_rotten_biased(dist), "Should detect Rotten bias when damaged > 60%"


def test_class_distribution_no_bias_when_balanced():
    from ai_models.fruit_quality_pipeline import grade_distribution, is_rotten_biased
    detections = [{"grade": "grade_1"}] * 3 + [{"grade": "damaged"}] * 2
    dist = grade_distribution(detections)
    assert not is_rotten_biased(dist)


# ── Cycle 3: ensemble trusts CNN > YOLO ──────────────────────────────────

def test_ensemble_prefers_cnn_when_disagreement():
    """When YOLO says Rotten but CNN says Fresh with high confidence → use CNN."""
    from ai_models.fruit_quality_pipeline import ensemble_quality_v2
    # YOLO: Rotten (low conf), CNN: Fresh (high conf) → should be Fresh
    result = ensemble_quality_v2(
        yolo_quality="Rotten",  yolo_conf=0.45,
        eff_quality="Fresh",    eff_conf=0.78,
    )
    assert result == "Fresh", f"Should trust CNN, got {result}"


def test_ensemble_uses_yolo_when_cnn_uncertain():
    """When CNN uncertain and YOLO confident → use YOLO."""
    from ai_models.fruit_quality_pipeline import ensemble_quality_v2
    result = ensemble_quality_v2(
        yolo_quality="Fresh",  yolo_conf=0.82,
        eff_quality="Rotten",  eff_conf=0.30,   # CNN uncertain
    )
    assert result == "Fresh", f"CNN uncertain → use YOLO, got {result}"


def test_ensemble_both_agree():
    from ai_models.fruit_quality_pipeline import ensemble_quality_v2
    result = ensemble_quality_v2("Fresh", 0.70, "Fresh", 0.65)
    assert result == "Fresh"
