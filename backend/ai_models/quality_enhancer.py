"""
Quality enhancer: HSV analysis + confidence calibration + reasoning.

Adds a second opinion on top of YOLO11's detection:
  1. HSVAnalyzer  — OpenCV color analysis of each cropped fruit
  2. calibrate_confidence — weighted combination of YOLO + HSV scores
  3. generate_reasoning  — Vietnamese explanation of the grade

No additional training needed. EfficientNet (Cycle 4) plugs in separately.
"""
from __future__ import annotations

import cv2
import numpy as np


# ── Cycle 1: HSV color analysis ───────────────────────────────────────────────

class HSVAnalyzer:
    """Analyse a cropped fruit image in HSV color space.

    Returns a dict with freshness_score (0-1) and qualitative labels.
    Higher freshness_score → more likely Fresh / Grade 1.
    """

    def analyze(self, bgr_image: np.ndarray) -> dict:
        if bgr_image is None or bgr_image.size == 0:
            return self._empty()

        hsv = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)

        mean_s = float(np.mean(s))
        mean_v = float(np.mean(v))
        mean_h = float(np.mean(h))

        # Color uniformity: low std in H channel → uniform color → healthy
        std_h = float(np.std(h))
        color_uniformity = max(0.0, 1.0 - std_h / 90.0)   # 90 = max meaningful std for H

        # Defect proxy: dark spots (V < 50) as fraction of pixels
        dark_mask = (v < 50).astype(np.uint8)
        defect_ratio = float(dark_mask.sum()) / dark_mask.size

        # Saturation level label
        if mean_s >= 150:
            saturation_level = "cao"
        elif mean_s >= 80:
            saturation_level = "trung bình"
        else:
            saturation_level = "thấp"

        # Brightness level label
        if mean_v >= 150:
            brightness_level = "sáng"
        elif mean_v >= 80:
            brightness_level = "bình thường"
        else:
            brightness_level = "tối"

        # Dominant hue label (OpenCV H: 0-180)
        dominant_hue = _hue_label(mean_h)

        # Freshness score: reward high saturation, high brightness, uniform color, few defects
        sat_score = min(mean_s / 180.0, 1.0)
        val_score = min(mean_v / 200.0, 1.0)
        defect_penalty = min(defect_ratio * 3.0, 1.0)

        freshness_score = (
            0.35 * sat_score
            + 0.30 * val_score
            + 0.25 * color_uniformity
            - 0.10 * defect_penalty
        )
        freshness_score = float(np.clip(freshness_score, 0.0, 1.0))

        return {
            "freshness_score": round(freshness_score, 3),
            "dominant_hue": dominant_hue,
            "saturation_level": saturation_level,
            "brightness_level": brightness_level,
            "defect_ratio": round(defect_ratio, 3),
            "color_uniformity": round(color_uniformity, 3),
            "mean_hue": round(mean_h, 1),
            "mean_saturation": round(mean_s, 1),
            "mean_value": round(mean_v, 1),
        }

    @staticmethod
    def _empty() -> dict:
        return {
            "freshness_score": 0.5, "dominant_hue": "không xác định",
            "saturation_level": "không xác định", "brightness_level": "không xác định",
            "defect_ratio": 0.0, "color_uniformity": 0.5,
        }


def _hue_label(mean_h: float) -> str:
    """Map mean OpenCV hue (0-180) to Vietnamese color name."""
    if mean_h < 10 or mean_h > 160:
        return "đỏ"
    if mean_h < 25:
        return "cam"
    if mean_h < 35:
        return "vàng cam"
    if mean_h < 55:
        return "vàng tươi"
    if mean_h < 80:
        return "vàng xanh"
    if mean_h < 100:
        return "xanh lá"
    if mean_h < 130:
        return "xanh dương"
    return "tím / nâu"


# ── Cycle 2: Confidence calibration ──────────────────────────────────────────

def calibrate_confidence(
    yolo_conf: float,
    hsv_score: float,
    n_detections: int = 1,
) -> float:
    """Combine YOLO detection confidence with HSV freshness score.

    n_detections > 1 slightly reduces confidence (mixed quality in frame).
    """
    # Weighted average: YOLO confidence carries more weight (trained signal)
    combined = 0.65 * yolo_conf + 0.35 * hsv_score

    # Penalty when multiple objects in frame (harder to assess individual quality)
    if n_detections > 1:
        penalty = min((n_detections - 1) * 0.04, 0.15)
        combined -= penalty

    return float(np.clip(combined, 0.0, 1.0))


# ── Cycle 3: Reasoning text generation ───────────────────────────────────────

_GRADE_TEMPLATES = {
    "grade_1": [
        "{fruit} chất lượng tốt — {hue}, {sat} độ bão hòa, ít khuyết tật ({defect:.0%} pixel bất thường). "
        "Phù hợp xuất khẩu hoặc siêu thị.",
        "Hình ảnh cho thấy {fruit} tươi, màu {hue} đồng đều (độ đồng nhất {uniform:.0%}). "
        "Độ sáng {bright} và không có dấu hiệu hư hỏng rõ ràng — xếp Loại 1.",
    ],
    "grade_2": [
        "{fruit} chất lượng trung bình — màu {hue}, độ bão hòa {sat}. "
        "Có {defect:.0%} pixel bất thường (vết nhỏ hoặc màu không đều). Phù hợp chợ đầu mối.",
        "Phát hiện một số điểm bất thường ({defect:.0%} diện tích). {fruit} vẫn có thể bán nhưng "
        "nên ưu tiên kênh phân phối nội địa.",
    ],
    "grade_3": [
        "{fruit} có dấu hiệu xuống cấp — màu {hue} với độ bão hòa {sat}. "
        "Tỷ lệ pixel bất thường cao ({defect:.0%}). Nên bán nhanh hoặc chế biến.",
        "Chất lượng giảm rõ: độ đồng nhất màu chỉ đạt {uniform:.0%}. "
        "{fruit} xếp Loại 3 — phù hợp chế biến hoặc bán giá thấp.",
    ],
    "damaged": [
        "{fruit} hư hỏng nặng — tỷ lệ vùng tối/bất thường {defect:.0%}, màu {hue} không đặc trưng. "
        "Không nên bán tươi. Chuyển chế biến hoặc loại bỏ.",
        "Hình ảnh cho thấy {fruit} đã hỏng: độ đồng nhất màu thấp ({uniform:.0%}), "
        "nhiều vùng tối ({defect:.0%}). Nên loại bỏ hoặc xử lý riêng.",
    ],
}


def generate_reasoning(
    fruit_type_vi: str,
    grade: str,
    hsv_result: dict,
    confidence: float,
) -> str:
    """Generate Vietnamese explanation for the quality grade."""
    templates = _GRADE_TEMPLATES.get(grade, _GRADE_TEMPLATES["grade_1"])
    template = templates[int(confidence * 10) % len(templates)]

    text = template.format(
        fruit=fruit_type_vi,
        hue=hsv_result.get("dominant_hue", "không xác định"),
        sat=hsv_result.get("saturation_level", ""),
        bright=hsv_result.get("brightness_level", ""),
        defect=hsv_result.get("defect_ratio", 0.0),
        uniform=hsv_result.get("color_uniformity", 0.5),
    )

    conf_note = f" (Độ tin cậy tổng hợp: {confidence:.0%})"
    return text + conf_note
