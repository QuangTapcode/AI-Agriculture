"""
TDD: tiled detection — slice image into overlapping tiles,
detect in each, merge back to original coordinates.

Fixes: fruits in shadow/occluded at bottom not detected in full image.
"""
import cv2
import numpy as np
import pytest
from ai_models.fruit_quality_pipeline import tile_detect, merge_tile_detections


# ── tile_detect ────────────────────────────────────────────────────────────

def test_tile_detect_returns_list(tmp_path):
    """tile_detect must return a list of raw detection dicts."""
    img = np.ones((640, 640, 3), dtype=np.uint8) * 200
    p = str(tmp_path / "t.jpg")
    cv2.imwrite(p, img)

    from ai_models.fruit_quality_pipeline import FruitQualityPipeline
    pipeline = FruitQualityPipeline(model_path="ai_models/weights/best.pt")
    result = tile_detect(pipeline, p, tile_size=320, overlap=0.2, conf=0.15)
    assert isinstance(result, list)


def test_tile_detect_coords_in_original_space(tmp_path):
    """All returned bboxes must be within [0, img_w] and [0, img_h]."""
    img = np.ones((480, 640, 3), dtype=np.uint8) * 150
    p = str(tmp_path / "t.jpg")
    cv2.imwrite(p, img)

    from ai_models.fruit_quality_pipeline import FruitQualityPipeline
    pipeline = FruitQualityPipeline(model_path="ai_models/weights/best.pt")
    result = tile_detect(pipeline, p, tile_size=320, overlap=0.2, conf=0.15)
    for det in result:
        x1, y1, x2, y2 = det["bbox"]
        assert 0 <= x1 < 640 and 0 <= x2 <= 640
        assert 0 <= y1 < 480 and 0 <= y2 <= 480


# ── merge_tile_detections ──────────────────────────────────────────────────

def test_merge_deduplicates_cross_tile_duplicates():
    """Same fruit appearing in 2 adjacent tiles → merged to 1 box."""
    # Fruit at position [150,50,250,150] appears in both tile0 and tile1
    dets = [
        {"bbox": [150, 50, 250, 150], "confidence": 0.88, "grade": "grade_1",
         "fruit_type": "Mango", "fruit_type_vi": "Xoài",
         "quality_level": "Fresh", "grade_label_vi": "Loại 1",
         "grade_color": "#22c55e", "yolo_confidence": 0.88,
         "efficientnet_confidence": 0.0, "efficientnet_top3": [],
         "hsv_freshness": 0.7, "hsv_color": "vàng", "hsv_defect_ratio": 0.02,
         "color_uniformity": 0.8, "price_range": (25000, 40000),
         "recommendation": "", "reasoning": ""},
        {"bbox": [152, 52, 252, 152], "confidence": 0.72, "grade": "grade_1",
         "fruit_type": "Mango", "fruit_type_vi": "Xoài",
         "quality_level": "Fresh", "grade_label_vi": "Loại 1",
         "grade_color": "#22c55e", "yolo_confidence": 0.72,
         "efficientnet_confidence": 0.0, "efficientnet_top3": [],
         "hsv_freshness": 0.65, "hsv_color": "vàng", "hsv_defect_ratio": 0.03,
         "color_uniformity": 0.75, "price_range": (25000, 40000),
         "recommendation": "", "reasoning": ""},
    ]
    result = merge_tile_detections(dets, iou_threshold=0.65)
    assert len(result) == 1
    assert result[0]["confidence"] == 0.88   # keep higher confidence


def test_merge_keeps_detections_from_different_areas():
    """Fruits in different tiles (no overlap) → all kept."""
    dets = [
        {"bbox": [10, 10, 80, 80],   "confidence": 0.80, "grade": "grade_1",
         "fruit_type": "Mango", "fruit_type_vi": "Xoài",
         "quality_level": "Fresh", "grade_label_vi": "Loại 1",
         "grade_color": "#22c55e", "yolo_confidence": 0.80,
         "efficientnet_confidence": 0.0, "efficientnet_top3": [],
         "hsv_freshness": 0.7, "hsv_color": "vàng", "hsv_defect_ratio": 0.02,
         "color_uniformity": 0.8, "price_range": (25000, 40000),
         "recommendation": "", "reasoning": ""},
        {"bbox": [300, 300, 380, 380], "confidence": 0.75, "grade": "grade_1",
         "fruit_type": "Mango", "fruit_type_vi": "Xoài",
         "quality_level": "Fresh", "grade_label_vi": "Loại 1",
         "grade_color": "#22c55e", "yolo_confidence": 0.75,
         "efficientnet_confidence": 0.0, "efficientnet_top3": [],
         "hsv_freshness": 0.65, "hsv_color": "vàng", "hsv_defect_ratio": 0.03,
         "color_uniformity": 0.75, "price_range": (25000, 40000),
         "recommendation": "", "reasoning": ""},
    ]
    result = merge_tile_detections(dets, iou_threshold=0.65)
    assert len(result) == 2
