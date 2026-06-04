"""
TDD: post-NMS deduplication — remove overlapping boxes for same fruit.

Problem: augment=True (TTA) detects same fruit from multiple passes.
         NMS at iou=0.7 allows boxes with <70% overlap to coexist.
         Result: 10 boxes for 5 fruits.

Fix: deduplicate_detections() — greedy NMS on final detection list,
     removes boxes that overlap > threshold with a higher-confidence box.
"""
import pytest
from ai_models.fruit_quality_pipeline import deduplicate_detections, compute_iou


# ── compute_iou ────────────────────────────────────────────────────────────

def test_iou_no_overlap():
    assert compute_iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0.0

def test_iou_full_overlap():
    assert compute_iou([0, 0, 10, 10], [0, 0, 10, 10]) == pytest.approx(1.0)

def test_iou_partial_overlap():
    # boxes overlap by 5x10=50, union=150
    iou = compute_iou([0, 0, 10, 10], [5, 0, 15, 10])
    assert abs(iou - 50/150) < 0.01


# ── deduplicate_detections ─────────────────────────────────────────────────

def _det(bbox, conf, grade="grade_1"):
    return {"bbox": bbox, "confidence": conf, "grade": grade,
            "fruit_type_vi": "Xoài", "grade_label_vi": "Loại 1"}


def test_deduplicate_removes_overlapping_lower_conf():
    """Two heavily overlapping boxes → keep higher confidence only."""
    d1 = _det([10, 10, 100, 100], conf=0.88)
    d2 = _det([15, 15, 105, 105], conf=0.55)   # ~85% IoU with d1
    result = deduplicate_detections([d1, d2], iou_threshold=0.5)
    assert len(result) == 1
    assert result[0]["confidence"] == 0.88


def test_deduplicate_keeps_non_overlapping():
    """Two non-overlapping boxes → both kept."""
    d1 = _det([0, 0, 50, 50], conf=0.80)
    d2 = _det([100, 100, 150, 150], conf=0.75)
    result = deduplicate_detections([d1, d2], iou_threshold=0.5)
    assert len(result) == 2


def test_deduplicate_handles_10_for_5_fruits():
    """10 boxes: 5 TTA-duplicate pairs (IoU~0.82) → 5 after dedup at 0.65."""
    dets = []
    for i in range(5):
        x = i * 120
        # TTA duplicates: almost same position, IoU ~0.82
        dets.append(_det([x,    0, x+100, 100], conf=0.70))
        dets.append(_det([x+3,  3, x+103, 103], conf=0.55))
    result = deduplicate_detections(dets, iou_threshold=0.65)
    assert len(result) == 5


def test_deduplicate_adjacent_fruits_not_removed():
    """Adjacent fruits touching (IoU~0.35) must NOT be removed at threshold=0.65."""
    # Two mangoes side by side — overlapping edge, IoU ~0.35
    d1 = _det([0,  0, 100, 100], conf=0.80)
    d2 = _det([70, 0, 170, 100], conf=0.75)  # IoU = 30*100/(10000+10000-3000) ≈ 0.18
    result = deduplicate_detections([d1, d2], iou_threshold=0.65)
    assert len(result) == 2, "Adjacent fruits should not be removed"


def test_deduplicate_sorts_by_confidence():
    """Higher-confidence boxes should survive deduplication."""
    dets = [
        _det([0, 0, 80, 80], conf=0.50),
        _det([5, 5, 85, 85], conf=0.90),  # overlapping, higher conf
        _det([200, 0, 280, 80], conf=0.70),
    ]
    result = deduplicate_detections(dets, iou_threshold=0.5)
    assert len(result) == 2
    confs = {r["confidence"] for r in result}
    assert 0.90 in confs
    assert 0.70 in confs


def test_deduplicate_empty():
    assert deduplicate_detections([], 0.5) == []


def test_deduplicate_single():
    d = _det([0, 0, 50, 50], conf=0.80)
    assert deduplicate_detections([d], 0.5) == [d]
