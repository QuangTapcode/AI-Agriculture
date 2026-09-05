"""
EfficientNet-B0 quality classifier.

Input : BGR crop từ YOLO bounding box (numpy array)
Output: class probabilities + top prediction

Số class lấy từ chính checkpoint, tên class lấy từ file sidecar
`<weights>.classes.json` (một mảng JSON, thứ tự đúng bằng index của model).
Nhờ vậy mở rộng đợt 2 lên 96 class chỉ cần thay weights + sidecar.

Không có sidecar thì dùng 16 class đợt 1:
  Apple / Banana / Mango / Orange  ×  Fresh / Rotten / Semifresh / Semirotten
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Class order must match the training dataset folder sort order (alphabetical)
DEFAULT_CLASS_NAMES: list[str] = [
    "Apple Fresh",    "Apple Rotten",    "Apple Semifresh",    "Apple Semirotten",
    "Banana Fresh",   "Banana Rotten",   "Banana Semifresh",   "Banana Semirotten",
    "Mango Fresh",    "Mango Rotten",    "Mango Semifresh",    "Mango Semirotten",
    "Orange Fresh",   "Orange Rotten",   "Orange Semifresh",   "Orange Semirotten",
]

# Giữ tên cũ cho code đã import CLASS_NAMES/NUM_CLASSES.
CLASS_NAMES: list[str] = DEFAULT_CLASS_NAMES
NUM_CLASSES = len(DEFAULT_CLASS_NAMES)  # 16


def _sidecar_path(model_path: str) -> Path:
    """`.../best.pt` -> `.../best.classes.json`"""
    return Path(model_path).with_suffix(".classes.json")


def load_class_names(model_path: str, num_classes: int) -> list[str]:
    """Tên class cho checkpoint: sidecar nếu có và khớp số lượng, không thì suy ra.

    Sidecar sai số lượng là lỗi cấu hình dễ gây gán nhãn lệch hàng loạt, nên
    bị bỏ qua kèm cảnh báo thay vì dùng bừa.
    """
    path = _sidecar_path(model_path)
    if path.is_file():
        try:
            names = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(names, list) and len(names) == num_classes:
                return [str(n) for n in names]
            logger.warning(
                "[EfficientNet] %s có %s tên nhưng model có %s class — bỏ qua sidecar",
                path, len(names) if isinstance(names, list) else "?", num_classes,
            )
        except Exception as exc:
            logger.warning("[EfficientNet] Không đọc được %s: %s", path, exc)

    if num_classes == len(DEFAULT_CLASS_NAMES):
        return list(DEFAULT_CLASS_NAMES)

    logger.warning(
        "[EfficientNet] Model %s class nhưng thiếu %s — dùng tên tạm class_N",
        num_classes, path.name,
    )
    return [f"class_{i}" for i in range(num_classes)]

# ImageNet normalization (EfficientNet standard)
_MEAN = [0.485, 0.456, 0.406]
_STD  = [0.229, 0.224, 0.225]
_IMG_SIZE = 224


class EfficientNetClassifier:
    """Loads fine-tuned EfficientNet-B0 and classifies a single cropped fruit."""

    def __init__(self, model_path: str = "ai_models/weights/efficientnet_quality.pt"):
        self.model_path = model_path
        self._model: Any = None
        self._class_names: list[str] = list(DEFAULT_CLASS_NAMES)

    # ── Public interface ──────────────────────────────────────────────────────

    def classify(self, bgr_crop: np.ndarray) -> dict:
        """Classify a BGR-format cropped fruit image.

        Returns:
            {
                "class_name":   "Banana Fresh",
                "fruit_type":   "Banana",
                "quality_level": "Fresh",
                "confidence":   0.95,
                "top3": [("Banana Fresh", 0.95), ("Banana Semifresh", 0.04), ...],
                "probabilities": {"Apple Fresh": 0.001, ...}
            }
        """
        if bgr_crop is None or bgr_crop.size == 0:
            return self._fallback("empty_crop")
        self._load()
        if self._model is None:
            return self._fallback("model_unavailable")

        tensor = self._preprocess(bgr_crop)
        probs = self._forward(tensor)
        if probs is None:
            return self._fallback("inference_failed")

        names = self._class_names
        top_idx = int(probs.argmax())
        top_class = names[top_idx]
        parts = top_class.split(" ", 1)
        fruit_type = parts[0]
        quality_level = parts[1] if len(parts) == 2 else "Fresh"

        prob_list = probs.tolist()
        top3 = sorted(enumerate(prob_list), key=lambda x: -x[1])[:3]

        return {
            "class_name":    top_class,
            "fruit_type":    fruit_type,
            "quality_level": quality_level,
            "confidence":    round(prob_list[top_idx], 4),
            "top3":          [(names[i], round(p, 4)) for i, p in top3],
            "probabilities": {names[i]: round(p, 4) for i, p in enumerate(prob_list)},
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            import torch.nn as nn
            from torchvision import models

            state = torch.load(self.model_path, map_location="cpu", weights_only=True)

            # Số class do checkpoint quyết định, không hardcode — nếu không,
            # weights đợt 2 (96 class) sẽ mismatch và bị nuốt lỗi thành model=None.
            num_classes = int(state["classifier.1.weight"].shape[0])

            model = models.efficientnet_b0(weights=None)
            model.classifier[1] = nn.Linear(1280, num_classes)
            model.load_state_dict(state)
            model.eval()

            self._model = model
            self._class_names = load_class_names(self.model_path, num_classes)
            logger.info(
                "[EfficientNet] Loaded from %s (%s class)", self.model_path, num_classes
            )
        except Exception as exc:
            logger.error("[EfficientNet] Failed to load: %s", exc)
            self._model = None

    def _preprocess(self, bgr: np.ndarray):
        """BGR numpy → normalized float tensor [1, 3, 224, 224]."""
        try:
            import torch
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            resized = cv2.resize(rgb, (_IMG_SIZE, _IMG_SIZE))
            arr = resized.astype(np.float32) / 255.0
            arr = (arr - np.array(_MEAN, dtype=np.float32)) / np.array(_STD, dtype=np.float32)
            # HWC → CHW → NCHW
            tensor = torch.from_numpy(arr.transpose(2, 0, 1)).unsqueeze(0)
            return tensor
        except Exception as exc:
            logger.warning("[EfficientNet] Preprocess failed: %s", exc)
            return None

    def _forward(self, tensor):
        if tensor is None:
            return None
        try:
            import torch
            with torch.no_grad():
                logits = self._model(tensor)
                return torch.softmax(logits, dim=1)[0].numpy()
        except Exception as exc:
            logger.warning("[EfficientNet] Forward pass failed: %s", exc)
            return None

    @staticmethod
    def _fallback(reason: str) -> dict:
        return {
            "class_name": "Unknown Fresh",
            "fruit_type": "Unknown",
            "quality_level": "Fresh",
            "confidence": 0.0,
            "top3": [],
            "probabilities": {},
            "error": reason,
        }


# Singleton
efficientnet_classifier = EfficientNetClassifier()
