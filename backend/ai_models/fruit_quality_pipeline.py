"""
Fruit quality pipeline using the trained YOLO11 model.

Model classes: {FruitType} {QualityLevel}
  FruitTypes   : Apple, Banana, Mango, Orange
  QualityLevels: Fresh, Semifresh, Semirotten, Rotten

Public interface:
    parse_class_name(cls_name)   -> (fruit_type, quality_level)
    quality_to_grade(quality)    -> {"grade": ..., "label_vi": ..., "color": ...}
    draw_annotated(bgr, detections) -> annotated BGR image (numbered boxes)
    FruitQualityPipeline.analyze(image_path) -> result dict + annotated_b64
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dep
def _get_enhancer():
    from ai_models.quality_enhancer import HSVAnalyzer, calibrate_confidence, generate_reasoning
    from ai_models.efficientnet_classifier import efficientnet_classifier
    return HSVAnalyzer(), calibrate_confidence, generate_reasoning, efficientnet_classifier

# ── Label mappings ────────────────────────────────────────────────────────────

_FRUIT_VI = {
    "Apple":  "Táo",
    "Banana": "Chuối",
    "Mango":  "Xoài",
    "Orange": "Cam",
}

_QUALITY_MAP = {
    "Fresh":      {"grade": "grade_1",  "label_vi": "Loại 1",  "color": "#22c55e"},
    "Semifresh":  {"grade": "grade_2",  "label_vi": "Loại 2",  "color": "#eab308"},
    "Semirotten": {"grade": "grade_3",  "label_vi": "Loại 3",  "color": "#f97316"},
    "Rotten":     {"grade": "damaged",  "label_vi": "Hỏng",    "color": "#ef4444"},
}

_GRADE_TO_QUALITY = {
    "grade_1": "Fresh",
    "grade_2": "Semifresh",
    "grade_3": "Semirotten",
    "damaged": "Rotten",
}

_GRADE_PRICE_VND = {
    "grade_1": (25_000, 40_000),
    "grade_2": (15_000, 24_000),
    "grade_3": (8_000,  14_000),
    "damaged": (2_000,   7_000),
}

_GRADE_RECOMMENDATION = {
    "grade_1":  "Chất lượng tốt — phù hợp siêu thị, xuất khẩu.",
    "grade_2":  "Chất lượng trung bình — phù hợp chợ đầu mối.",
    "grade_3":  "Chất lượng thấp — bán nhanh hoặc chế biến.",
    "damaged":  "Hỏng — không bán tươi, chuyển chế biến hoặc loại bỏ.",
}


# ── Pure functions (testable without model) ───────────────────────────────────

def parse_class_name(cls_name: str) -> tuple[str, str]:
    """Split "FruitType QualityLevel" into (fruit_type, quality_level).

    Examples:
        "Apple Fresh"      -> ("Apple", "Fresh")
        "Mango Semirotten" -> ("Mango", "Semirotten")
    """
    parts = cls_name.strip().split(" ", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return cls_name, "Fresh"


def quality_to_grade(quality_level: str) -> dict:
    """Map quality level string to grade info dict.

    Returns {"grade": ..., "label_vi": ..., "color": ...}.
    Defaults to grade_1 for unknown quality levels.
    """
    return dict(_QUALITY_MAP.get(quality_level, _QUALITY_MAP["Fresh"]))


# ── Pipeline ─────────────────────────────────────────────────────────────────

# ── Fruit type override ───────────────────────────────────────────────────────

# Maps normalized user hint → (English type, Vietnamese name)
_HINT_TO_FRUIT: dict[str, tuple[str, str]] = {
    "xoai":   ("Mango",  "Xoài"),
    "chuoi":  ("Banana", "Chuối"),
    "tao":    ("Apple",  "Táo"),
    "cam":    ("Orange", "Cam"),
}


def resolve_fruit_hint(crop_name_hint: str) -> tuple[str, str]:
    """Gợi ý loại quả của người dùng → (tên tiếng Anh, tên tiếng Việt).

    Bỏ dấu và không phân biệt hoa thường, nên "Xoài", "xoai", "XOÀI" như nhau.
    Không nhận ra thì trả ("", "") — nguồn duy nhất cho mọi nhánh dùng hint,
    tránh cảnh mỗi nhánh giữ một bảng map riêng rồi lệch nhau khi thêm rau củ.
    """
    if not crop_name_hint or not crop_name_hint.strip():
        return "", ""

    import unicodedata as _ud
    key = _ud.normalize("NFD", crop_name_hint.strip().lower()).replace("đ", "d")
    key = "".join(c for c in key if _ud.category(c) != "Mn")
    return _HINT_TO_FRUIT.get(key, ("", ""))


def override_fruit_type(detections: list[dict], crop_name_hint: str) -> list[dict]:
    """Override YOLO fruit type with user's crop selection.

    YOLO is reliable for quality level (Fresh/Rotten/…) but can confuse
    visually similar fruits (e.g. orange-colored mango → Orange).
    The user knows which fruit they are photographing.

    Quality level, grade, confidence are preserved unchanged.
    """
    if not crop_name_hint or not detections:
        return detections

    en_type, vi_type = resolve_fruit_hint(crop_name_hint)
    if not en_type:
        return detections  # unknown hint, keep YOLO result

    result = []
    for det in detections:
        d = dict(det)
        d["fruit_type"]    = en_type
        d["fruit_type_vi"] = vi_type
        result.append(d)
    return result


# ── OpenCV annotation ────────────────────────────────────────────────────────

# BGR colors per grade  (used for cv2 rectangles/circles)
_GRADE_BGR = {
    "grade_1":  (34,  197,  94),
    "grade_2":  (8,   179, 234),
    "grade_3":  (22,  115, 249),
    "damaged":  (68,   68, 239),
}
# RGB equivalents for PIL
_GRADE_RGB = {k: (v[2], v[1], v[0]) for k, v in _GRADE_BGR.items()}

# Font path — Arial supports Vietnamese on Windows; fallback to None (PIL default)
_FONT_PATHS = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/tahoma.ttf",
]
_FONT_PATH = next((p for p in _FONT_PATHS if Path(p).exists()), None)


def _pil_font(size: int = 14):
    """Load a PIL font with Vietnamese support."""
    try:
        from PIL import ImageFont
        if _FONT_PATH:
            return ImageFont.truetype(_FONT_PATH, size)
    except Exception:
        pass
    try:
        from PIL import ImageFont
        return ImageFont.load_default()
    except Exception:
        return None


def draw_annotated(bgr_image: np.ndarray, detections: list[dict]) -> np.ndarray:
    """Draw numbered bounding boxes with Vietnamese labels on bgr_image copy.

    Uses PIL for text rendering (supports Vietnamese Unicode).
    Falls back to ASCII-stripped cv2.putText if PIL unavailable.

    Returns a new array (original is not modified).
    """
    if bgr_image is None or bgr_image.size == 0:
        return bgr_image

    out = bgr_image.copy()

    # Draw cv2 boxes and circles first
    for idx, det in enumerate(detections, start=1):
        bbox = det.get("bbox", [])
        if len(bbox) < 4:
            continue
        x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        color_bgr = _GRADE_BGR.get(det.get("grade", "grade_2"), (150, 150, 150))

        cv2.rectangle(out, (x1, y1), (x2, y2), color_bgr, 2)
        cx, cy = x1 + 14, y1 + 14
        cv2.circle(out, (cx, cy), 14, color_bgr, -1)
        cv2.putText(out, str(idx), (cx - 5 if idx < 10 else cx - 8, cy + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)

    # Overlay Vietnamese text with PIL
    try:
        from PIL import Image as PILImage, ImageDraw
        pil_img = PILImage.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)
        font = _pil_font(14)
        font_small = _pil_font(12)

        for idx, det in enumerate(detections, start=1):
            bbox = det.get("bbox", [])
            if len(bbox) < 4:
                continue
            x1, y1 = int(bbox[0]), int(bbox[1])
            color_rgb = _GRADE_RGB.get(det.get("grade", "grade_2"), (150, 150, 150))
            fruit_vi = det.get("fruit_type_vi", det.get("fruit_type", "?"))
            grade_vi = det.get("grade_label_vi", "")
            conf     = det.get("confidence", 0.0)

            label = f"#{idx} {fruit_vi} {grade_vi} {conf:.0%}"

            # Measure text
            if font:
                try:
                    bbox_text = draw.textbbox((0, 0), label, font=font)
                    tw = bbox_text[2] - bbox_text[0]
                    th = bbox_text[3] - bbox_text[1]
                except Exception:
                    tw, th = len(label) * 8, 16
            else:
                tw, th = len(label) * 8, 16

            label_y = max(y1 - th - 4, 0)
            # Background rectangle
            draw.rectangle([x1, label_y, x1 + tw + 6, label_y + th + 4], fill=color_rgb)
            # Text
            draw.text((x1 + 3, label_y + 2), label, fill=(255, 255, 255),
                      font=font if font else None)

        out = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        logger.warning("[draw_annotated] PIL text failed, using ASCII fallback: %s", exc)
        # ASCII fallback — strip diacritics
        import unicodedata
        for idx, det in enumerate(detections, start=1):
            bbox = det.get("bbox", [])
            if len(bbox) < 4:
                continue
            x1, y1 = int(bbox[0]), int(bbox[1])
            color_bgr = _GRADE_BGR.get(det.get("grade", "grade_2"), (150, 150, 150))
            fruit_raw = det.get("fruit_type_vi", "?")
            grade_raw = det.get("grade_label_vi", "")
            conf = det.get("confidence", 0.0)
            # Strip Vietnamese diacritics for ASCII-only rendering
            def _strip(s):
                n = unicodedata.normalize("NFD", s).replace("đ", "d")
                return "".join(c for c in n if unicodedata.category(c) != "Mn")
            label = f"#{idx} {_strip(fruit_raw)} {_strip(grade_raw)} {conf:.0%}"
            (lw, lh), bl = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            ly = max(y1 - 4, lh + 4)
            cv2.rectangle(out, (x1, ly - lh - bl - 2), (x1 + lw + 4, ly), color_bgr, -1)
            cv2.putText(out, label, (x1 + 2, ly - bl),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

    return out


# ── Diagnostic utilities ──────────────────────────────────────────────────────

def save_debug_crops(
    bgr_image: np.ndarray,
    detections: list[dict],
    out_dir: str = "storage/raw_crawl/debug_crops",
) -> list[str]:
    """Save each YOLO crop to disk for visual inspection.

    Filename: crop_{idx}_{fruit_vi}_{grade_vi}.jpg
    Use this to verify what EfficientNet actually receives.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []

    for idx, det in enumerate(detections, start=1):
        bbox = det.get("bbox", [])
        if len(bbox) < 4 or bgr_image is None:
            continue
        x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        h, w = bgr_image.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            continue
        crop = bgr_image[y1:y2, x1:x2]
        fruit = det.get("fruit_type_vi", "unknown")
        grade = det.get("grade_label_vi", "?")
        fname = f"crop_{idx}_{fruit}_{grade}.jpg"
        path = str(out / fname)
        cv2.imwrite(path, crop)
        saved.append(path)

    if saved:
        logger.info("[Debug] Saved %d crops to %s", len(saved), out_dir)
    return saved


def grade_distribution(detections: list[dict]) -> dict[str, int]:
    """Count detections per grade."""
    counts = {"grade_1": 0, "grade_2": 0, "grade_3": 0, "damaged": 0}
    for d in detections:
        key = d.get("grade", "grade_2")
        if key in counts:
            counts[key] += 1
    return counts


def is_rotten_biased(distribution: dict[str, int], threshold: float = 0.60) -> bool:
    """Return True when 'damaged' grade exceeds threshold fraction of all detections.

    Indicates possible class imbalance in training data.
    """
    total = sum(distribution.values())
    if total == 0:
        return False
    return distribution.get("damaged", 0) / total > threshold


def compute_iou(box_a: list, box_b: list) -> float:
    """Compute Intersection over Union for two [x1,y1,x2,y2] boxes."""
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def deduplicate_detections(
    detections: list[dict],
    iou_threshold: float = 0.5,
) -> list[dict]:
    """Greedy NMS on the final detection list.

    Removes boxes that overlap > iou_threshold with a higher-confidence box.
    Fixes the TTA (augment=True) overcounting problem where the same fruit
    is detected multiple times from different augmentation passes.
    """
    if not detections:
        return detections
    # Sort by confidence descending — keep highest confidence when merging
    sorted_dets = sorted(detections, key=lambda d: d.get("confidence", 0), reverse=True)
    kept: list[dict] = []
    for det in sorted_dets:
        bbox = det.get("bbox", [])
        if len(bbox) < 4:
            kept.append(det)
            continue
        overlaps = any(
            compute_iou(bbox, k.get("bbox", [])) > iou_threshold
            for k in kept
            if len(k.get("bbox", [])) == 4
        )
        if not overlaps:
            kept.append(det)
    return kept


def apply_hsv_sanity(
    grade: str,
    hsv_freshness: float,
    defect_ratio: float,
) -> str:
    """Override 'damaged' grade when HSV signals indicate the fruit is visually fresh.

    Domain rule: a fruit with vibrant color and few dark spots cannot be damaged.
    This corrects model bias from training data where ripe orange fruit was mislabeled.

    Conditions to override damaged → grade_2:
      - hsv_freshness >= 0.60  (color is still vibrant / not darkened)
      - defect_ratio  <= 0.25  (< 25% dark-spot pixels)
    """
    if grade != "damaged":
        return grade
    if hsv_freshness >= 0.60 and defect_ratio <= 0.25:
        return "grade_2"
    return "damaged"


def ensemble_quality_v2(
    yolo_quality: str, yolo_conf: float,
    eff_quality: str,  eff_conf: float,
) -> str:
    """Decide final quality level, trusting CNN over YOLO when CNN is confident.

    Rules (Karpathy-simple — no floating weights):
    1. Both agree → use it (regardless of confidence)
    2. CNN confident (≥0.55) → trust CNN
    3. YOLO confident (≥0.65) AND CNN uncertain (<0.45) → trust YOLO
    4. Default → CNN (trained specifically on crops, less affected by class imbalance)
    """
    if yolo_quality == eff_quality:
        return yolo_quality
    if eff_conf >= 0.55:
        return eff_quality
    if yolo_conf >= 0.65 and eff_conf < 0.45:
        return yolo_quality
    return eff_quality   # default: trust CNN


def _image_to_b64(bgr: np.ndarray) -> str:
    """Encode BGR image to base64 JPEG string."""
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        return ""
    return base64.b64encode(buf.tobytes()).decode("utf-8")


class FruitQualityPipeline:
    """One-shot YOLO11 inference: detect fruit + classify quality in a single pass."""

    def __init__(self, model_path: str = "ai_models/weights/best.pt"):
        self.model_path = model_path
        self._model = None

    def classify_full_image(self, image_path: str, crop_name_hint: str = "") -> dict:
        """Classify quality on the full image (no bounding box needed).

        Used when YOLO returns no detections but the user specified a crop type.
        Runs EfficientNet on the full image + HSV analysis.
        """
        bgr = cv2.imread(image_path)
        if bgr is None:
            return _full_image_fallback(crop_name_hint, "image_unreadable")

        hsv_analyzer, calibrate_conf_fn, gen_reasoning_fn, eff_classifier = _get_enhancer()
        hsv_result = hsv_analyzer.analyze(bgr)
        eff_result = eff_classifier.classify(bgr)

        # Classifier không chạy được (thiếu weights, state_dict lệch...) — kết quả
        # degraded phải lộ ra, nếu không nó sẽ mang nhãn "Fresh" mặc định và bị
        # chấm Loại 1 y như một lần phân tích thành công.
        if eff_result.get("error"):
            return _full_image_fallback(crop_name_hint, eff_result["error"])

        hint_en, _ = resolve_fruit_hint(crop_name_hint)

        # If EfficientNet agrees with hint (or no hint), trust it
        eff_fruit = eff_result.get("fruit_type", "")
        eff_quality = eff_result.get("quality_level", "Fresh")
        eff_conf = eff_result.get("confidence", 0.0)

        # Use hint to disambiguate when EfficientNet is uncertain
        if hint_en and eff_conf < 0.50:
            fruit_type = hint_en
            fruit_vi = _FRUIT_VI.get(hint_en, crop_name_hint)
        else:
            fruit_type = eff_fruit or hint_en or "Unknown"
            fruit_vi = _FRUIT_VI.get(fruit_type, crop_name_hint or fruit_type)

        grade_info = quality_to_grade(eff_quality)
        grade = grade_info["grade"]
        confidence = _ensemble_confidence(0.0, eff_conf, hsv_result["freshness_score"], 1)
        reasoning = gen_reasoning_fn(fruit_vi, grade, hsv_result, confidence)

        return {
            "fruit_type":       fruit_type,
            "fruit_type_vi":    fruit_vi,
            "quality_level":    eff_quality,
            "grade":            grade,
            "grade_label_vi":   grade_info["label_vi"],
            "grade_color":      grade_info["color"],
            "confidence":       round(confidence, 3),
            "yolo_confidence":  0.0,
            "efficientnet_confidence": round(eff_conf, 3),
            "efficientnet_top3": eff_result.get("top3", []),
            "hsv_freshness":    hsv_result["freshness_score"],
            "hsv_color":        hsv_result["dominant_hue"],
            "hsv_defect_ratio": hsv_result["defect_ratio"],
            "color_uniformity": hsv_result["color_uniformity"],
            "bbox":             [],
            "price_range":      _GRADE_PRICE_VND.get(grade, (0, 0)),
            "recommendation":   _GRADE_RECOMMENDATION.get(grade, ""),
            "reasoning":        reasoning,
            "source":           "efficientnet_fullimage",
        }

    def _load(self):
        if self._model is not None:
            return
        try:
            from ultralytics import YOLO
            self._model = YOLO(self.model_path)
            logger.info("[FruitPipeline] Model loaded from %s", self.model_path)
        except Exception as exc:
            logger.error("[FruitPipeline] Failed to load model: %s", exc)
            self._model = None

    def analyze(self, image_path: str, conf: float = 0.15, crop_name_hint: str = "") -> dict:
        """Run YOLO inference. Retries at lower conf if nothing detected.

        conf mặc định thấp là có chủ đích, ưu tiên recall — xem
        tests/test_recall_improvement.py trước khi đổi.

        crop_name_hint: user-selected crop (e.g. "xoai") — overrides YOLO fruit
        type while preserving quality level. Fixes color-confusion errors like
        orange-colored mango being classified as Orange.

        Returns:
            {
                "detections": [
                    {
                        "fruit_type": "Mango",
                        "fruit_type_vi": "Xoài",
                        "quality_level": "Fresh",
                        "grade": "grade_1",
                        "grade_label_vi": "Loại 1",
                        "grade_color": "#22c55e",
                        "confidence": 0.92,
                        "bbox": [x1, y1, x2, y2],
                        "price_range": (25000, 40000),
                        "recommendation": "...",
                    },
                    ...
                ],
                "summary": {
                    "total": N,
                    "grade_1": N, "grade_2": N, "grade_3": N, "damaged": N,
                    "dominant_grade": "grade_1",
                },
            }
        """
        self._load()

        if self._model is None:
            return {"detections": [], "summary": _empty_summary(), "annotated_b64": "", "error": "model_unavailable"}

        # Best params from recall improvement tests:
        #   conf=0.15, iou=0.7, augment=True  →  3 vs baseline 2
        #   imgsz=1280 was tested and HURTS recall (model trained at 640)
        _tried_conf = conf
        try:
            results = self._model(
                image_path,
                conf=conf,
                iou=0.7,
                augment=True,   # TTA: flip/scale passes → better recall
                max_det=100,
                verbose=False,
            )
            if not any(r.boxes and len(r.boxes) for r in results):
                _tried_conf = 0.10
                results = self._model(
                    image_path, conf=0.10, iou=0.7,
                    augment=True, max_det=100, verbose=False,
                )
                logger.debug("[FruitPipeline] Retried at conf=0.10")
        except Exception as exc:
            logger.warning("[FruitPipeline] Inference failed: %s", exc)
            return {"detections": [], "summary": _empty_summary(), "annotated_b64": "", "error": str(exc)}

        # Load image once for HSV crops
        bgr_image = cv2.imread(image_path)
        hsv_analyzer, calibrate_conf_fn, gen_reasoning_fn, eff_classifier = _get_enhancer()

        detections: list[dict] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0])
                cls_name = result.names[cls_id]
                yolo_conf = float(box.conf[0])
                bbox = [round(v) for v in box.xyxy[0].tolist()]

                fruit_type, quality_level = parse_class_name(cls_name)
                grade_info = quality_to_grade(quality_level)
                grade = grade_info["grade"]
                fruit_vi = _FRUIT_VI.get(fruit_type, fruit_type)

                # Step A: Crop the fruit region
                crop = _get_crop(bgr_image, bbox)

                # Step B: HSV color analysis
                hsv_result = hsv_analyzer.analyze(crop) if crop is not None else hsv_analyzer._empty()

                # Step C: EfficientNet second opinion on crop
                eff_result = eff_classifier.classify(crop) if crop is not None else {}
                eff_conf = eff_result.get("confidence", 0.0)
                eff_quality = eff_result.get("quality_level", quality_level)

                # Step D: Ensemble grade — EfficientNet overrides if confident
                # Use v2 ensemble: CNN-first policy to counter YOLO's Rotten bias
                final_quality = ensemble_quality_v2(quality_level, yolo_conf, eff_quality, eff_conf)
                final_grade_info = quality_to_grade(final_quality)
                final_grade = final_grade_info["grade"]

                # HSV sanity: vibrant color cannot be damaged (fixes Rotten-biased dataset)
                sanity_grade = apply_hsv_sanity(
                    final_grade,
                    hsv_freshness=hsv_result.get("freshness_score", 0),
                    defect_ratio=hsv_result.get("defect_ratio", 0),
                )
                if sanity_grade != final_grade:
                    logger.info("[HSV sanity] grade %s → %s (freshness=%.2f)",
                                final_grade, sanity_grade,
                                hsv_result.get("freshness_score", 0))
                    final_grade_info = quality_to_grade(
                        _GRADE_TO_QUALITY.get(sanity_grade, final_quality)
                    )
                    final_grade = sanity_grade

                # Step E: Ensemble confidence (YOLO 40% + EfficientNet 45% + HSV 15%)
                n_boxes = len(result.boxes)
                ensemble_conf = _ensemble_confidence(
                    yolo_conf, eff_conf, hsv_result["freshness_score"], n_boxes
                )

                # Step F: Reasoning in Vietnamese
                reasoning = gen_reasoning_fn(fruit_vi, final_grade, hsv_result, ensemble_conf)

                detections.append({
                    "fruit_type":       fruit_type,
                    "fruit_type_vi":    fruit_vi,
                    "quality_level":    final_quality,
                    "grade":            final_grade,
                    "grade_label_vi":   final_grade_info["label_vi"],
                    "grade_color":      final_grade_info["color"],
                    "confidence":       round(ensemble_conf, 3),
                    # Breakdown of each signal
                    "yolo_confidence":  round(yolo_conf, 3),
                    "efficientnet_confidence": round(eff_conf, 3),
                    "efficientnet_top3": eff_result.get("top3", []),
                    "hsv_freshness":    hsv_result["freshness_score"],
                    "hsv_color":        hsv_result["dominant_hue"],
                    "hsv_defect_ratio": hsv_result["defect_ratio"],
                    "color_uniformity": hsv_result["color_uniformity"],
                    "bbox":             bbox,
                    "price_range":      _GRADE_PRICE_VND.get(final_grade, (0, 0)),
                    "recommendation":   _GRADE_RECOMMENDATION.get(final_grade, ""),
                    "reasoning":        reasoning,
                })

        # Post-NMS deduplication: remove TTA duplicates (IoU > 0.65)
        before = len(detections)
        detections = deduplicate_detections(detections, iou_threshold=0.65)
        if len(detections) < before:
            logger.info("[FruitPipeline] Dedup full-img: %d → %d", before, len(detections))

        # Tiling: add detections from sliced tiles (catches occluded/shadowed fruits)
        tile_dets = tile_detect(self, image_path, tile_size=320, overlap=0.25, conf=conf)
        if tile_dets:
            combined = detections + tile_dets
            before_merge = len(combined)
            detections = merge_tile_detections(combined, iou_threshold=0.65)
            logger.info("[FruitPipeline] Tiles added %d raw → merged to %d total",
                        len(tile_dets), len(detections))

        # Apply fruit type override BEFORE annotation
        if crop_name_hint:
            detections = override_fruit_type(detections, crop_name_hint)

        # Save debug crops (always — inspect at storage/raw_crawl/debug_crops/)
        if detections and bgr_image is not None:
            save_debug_crops(bgr_image, detections)

        # Annotated image with numbered boxes
        annotated_b64 = ""
        if detections and bgr_image is not None:
            annotated = draw_annotated(bgr_image, detections)
            annotated_b64 = _image_to_b64(annotated)

        summary = _build_summary(detections)
        dist = grade_distribution(detections)
        biased = is_rotten_biased(dist)
        if biased:
            logger.warning(
                "[FruitPipeline] Rotten bias detected: %d/%d detections are 'damaged'. "
                "Consider rebalancing training data.",
                dist["damaged"], summary["total"],
            )
        return {
            "detections":    detections,
            "summary":       {**summary, "rotten_biased": biased, "grade_distribution": dist},
            "annotated_b64": annotated_b64,
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

# ── Tiling detection ─────────────────────────────────────────────────────────

def tile_detect(
    pipeline: "FruitQualityPipeline",
    image_path: str,
    tile_size: int = 320,
    overlap: float = 0.2,
    conf: float = 0.15,
) -> list[dict]:
    """Slice image into overlapping tiles, detect in each, return detections
    mapped back to original image coordinates.

    Fixes: small/occluded/shadowed fruits that are missed in full-image detection.
    Each tile is processed at native scale so smaller fruits appear larger.
    """
    bgr = cv2.imread(image_path)
    if bgr is None:
        return []
    h, w = bgr.shape[:2]

    # Compute tile positions with overlap
    step = int(tile_size * (1 - overlap))
    xs = list(range(0, max(1, w - tile_size + 1), step)) + ([w - tile_size] if w > tile_size else [])
    ys = list(range(0, max(1, h - tile_size + 1), step)) + ([h - tile_size] if h > tile_size else [])
    xs = sorted(set(max(0, x) for x in xs))
    ys = sorted(set(max(0, y) for y in ys))

    pipeline._load()
    if pipeline._model is None:
        return []

    all_dets: list[dict] = []
    hsv_analyzer, calibrate_conf_fn, gen_reasoning_fn, eff_classifier = _get_enhancer()

    for y0 in ys:
        for x0 in xs:
            x1, y1 = x0 + tile_size, y0 + tile_size
            x1, y1 = min(x1, w), min(y1, h)
            tile = bgr[y0:y1, x0:x1]
            if tile.size == 0:
                continue

            # Save tile to temp file for YOLO
            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
                cv2.imwrite(tf.name, tile)
                tmp = tf.name
            try:
                results = pipeline._model(tmp, conf=conf, iou=0.5, verbose=False)
            except Exception:
                os.unlink(tmp)
                continue
            os.unlink(tmp)

            for result in results:
                if result.boxes is None:
                    continue
                for box in result.boxes:
                    # Map tile coordinates back to original image
                    tx1, ty1, tx2, ty2 = box.xyxy[0].tolist()
                    ox1, oy1 = tx1 + x0, ty1 + y0
                    ox2, oy2 = tx2 + x0, ty2 + y0
                    bbox = [round(ox1), round(oy1), round(ox2), round(oy2)]

                    cls_id = int(box.cls[0])
                    cls_name = result.names[cls_id]
                    yolo_conf = float(box.conf[0])

                    fruit_type, quality_level = parse_class_name(cls_name)
                    grade_info = quality_to_grade(quality_level)
                    grade = grade_info["grade"]
                    fruit_vi = _FRUIT_VI.get(fruit_type, fruit_type)

                    crop = _get_crop(bgr, bbox)
                    hsv_result = hsv_analyzer.analyze(crop) if crop is not None else hsv_analyzer._empty()
                    eff_result = eff_classifier.classify(crop) if crop is not None else {}
                    eff_conf = eff_result.get("confidence", 0.0)
                    eff_quality = eff_result.get("quality_level", quality_level)

                    final_quality = ensemble_quality_v2(quality_level, yolo_conf, eff_quality, eff_conf)
                    final_grade_info = quality_to_grade(final_quality)
                    final_grade = final_grade_info["grade"]
                    sanity_grade = apply_hsv_sanity(
                        final_grade, hsv_result.get("freshness_score", 0),
                        hsv_result.get("defect_ratio", 0),
                    )
                    if sanity_grade != final_grade:
                        final_grade_info = quality_to_grade(
                            _GRADE_TO_QUALITY.get(sanity_grade, final_quality)
                        )
                        final_grade = sanity_grade

                    ensemble_conf = _ensemble_confidence(yolo_conf, eff_conf, hsv_result["freshness_score"], 1)
                    reasoning = gen_reasoning_fn(fruit_vi, final_grade, hsv_result, ensemble_conf)

                    all_dets.append({
                        "fruit_type": fruit_type, "fruit_type_vi": fruit_vi,
                        "quality_level": final_quality, "grade": final_grade,
                        "grade_label_vi": final_grade_info["label_vi"],
                        "grade_color": final_grade_info["color"],
                        "confidence": round(ensemble_conf, 3),
                        "yolo_confidence": round(yolo_conf, 3),
                        "efficientnet_confidence": round(eff_conf, 3),
                        "efficientnet_top3": eff_result.get("top3", []),
                        "hsv_freshness": hsv_result["freshness_score"],
                        "hsv_color": hsv_result["dominant_hue"],
                        "hsv_defect_ratio": hsv_result["defect_ratio"],
                        "color_uniformity": hsv_result["color_uniformity"],
                        "bbox": bbox,
                        "price_range": _GRADE_PRICE_VND.get(final_grade, (0, 0)),
                        "recommendation": _GRADE_RECOMMENDATION.get(final_grade, ""),
                        "reasoning": reasoning,
                    })

    return all_dets


def merge_tile_detections(detections: list[dict], iou_threshold: float = 0.65) -> list[dict]:
    """Merge detections from multiple tiles using deduplicate_detections.

    Same fruit appearing in adjacent tiles → merged to single highest-confidence box.
    """
    return deduplicate_detections(detections, iou_threshold=iou_threshold)


def _full_image_fallback(crop_hint: str, reason: str) -> dict:
    return {
        "fruit_type": "Unknown", "fruit_type_vi": crop_hint or "Không xác định",
        "quality_level": "Fresh", "grade": "grade_2",
        "grade_label_vi": "Loại 2", "grade_color": "#eab308",
        "confidence": 0.0, "yolo_confidence": 0.0, "efficientnet_confidence": 0.0,
        "efficientnet_top3": [], "hsv_freshness": 0.5,
        "hsv_color": "không xác định", "hsv_defect_ratio": 0.0,
        "color_uniformity": 0.5, "bbox": [], "price_range": (0, 0),
        "recommendation": "", "reasoning": f"Không thể phân tích ảnh ({reason}).",
        "source": "fallback",
    }


def _get_crop(bgr_image: np.ndarray | None, bbox: list[int]) -> np.ndarray | None:
    """Return the cropped region from the full image, or None if invalid."""
    if bgr_image is None:
        return None
    x1, y1, x2, y2 = bbox
    h, w = bgr_image.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return None
    return bgr_image[y1:y2, x1:x2]


def _ensemble_quality(yolo_quality: str, eff_quality: str, yolo_conf: float, eff_conf: float) -> str:
    """Decide final quality level from YOLO and EfficientNet predictions.

    EfficientNet overrides YOLO when it is sufficiently confident (≥0.55)
    and the two predictions differ — EfficientNet was trained specifically
    on cropped fruit images so its quality read is more reliable than YOLO.
    """
    if yolo_quality == eff_quality:
        return yolo_quality
    # Both confident but disagree → trust EfficientNet (crop-specialized)
    if eff_conf >= 0.55:
        return eff_quality
    # EfficientNet uncertain → keep YOLO
    return yolo_quality


def _ensemble_confidence(yolo_conf: float, eff_conf: float, hsv_score: float, n_boxes: int) -> float:
    """Weighted ensemble: EfficientNet 45%, YOLO 40%, HSV 15%."""
    combined = 0.40 * yolo_conf + 0.45 * eff_conf + 0.15 * hsv_score
    if n_boxes > 1:
        combined -= min((n_boxes - 1) * 0.03, 0.12)
    return float(np.clip(combined, 0.0, 1.0))


def _analyze_crop(bgr_image, bbox: list[int], hsv_analyzer) -> dict:
    """Crop bounding box region and run HSV analysis."""
    if bgr_image is None:
        return hsv_analyzer._empty()
    x1, y1, x2, y2 = bbox
    h, w = bgr_image.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return hsv_analyzer._empty()
    crop = bgr_image[y1:y2, x1:x2]
    return hsv_analyzer.analyze(crop)


def _empty_summary() -> dict:
    return {"total": 0, "grade_1": 0, "grade_2": 0, "grade_3": 0, "damaged": 0, "dominant_grade": None}


def _build_summary(detections: list[dict]) -> dict:
    counts: dict[str, int] = {"grade_1": 0, "grade_2": 0, "grade_3": 0, "damaged": 0}
    for d in detections:
        key = d["grade"]
        if key in counts:
            counts[key] += 1
    dominant = max(counts, key=counts.get) if detections else None
    return {"total": len(detections), **counts, "dominant_grade": dominant}


# Singleton — reused across requests
fruit_quality_pipeline = FruitQualityPipeline()
