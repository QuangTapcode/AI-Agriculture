"""
EfficientNet-B0 quality classifier.

Input : BGR crop từ YOLO bounding box (numpy array)
Output: class probabilities + top prediction

16 classes mirror the YOLO model:
  Apple / Banana / Mango / Orange  ×  Fresh / Rotten / Semifresh / Semirotten
"""
from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Class order must match the training dataset folder sort order (alphabetical)
CLASS_NAMES: list[str] = [
    "Apple Fresh",    "Apple Rotten",    "Apple Semifresh",    "Apple Semirotten",
    "Banana Fresh",   "Banana Rotten",   "Banana Semifresh",   "Banana Semirotten",
    "Mango Fresh",    "Mango Rotten",    "Mango Semifresh",    "Mango Semirotten",
    "Orange Fresh",   "Orange Rotten",   "Orange Semifresh",   "Orange Semirotten",
]
NUM_CLASSES = len(CLASS_NAMES)  # 16

# ImageNet normalization (EfficientNet standard)
_MEAN = [0.485, 0.456, 0.406]
_STD  = [0.229, 0.224, 0.225]
_IMG_SIZE = 224


class EfficientNetClassifier:
    """Loads fine-tuned EfficientNet-B0 and classifies a single cropped fruit."""

    def __init__(self, model_path: str = "ai_models/weights/efficientnet_quality.pt"):
        self.model_path = model_path
        self._model: Any = None

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

        top_idx = int(probs.argmax())
        top_class = CLASS_NAMES[top_idx]
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
            "top3":          [(CLASS_NAMES[i], round(p, 4)) for i, p in top3],
            "probabilities": {CLASS_NAMES[i]: round(p, 4) for i, p in enumerate(prob_list)},
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            import torch.nn as nn
            from torchvision import models

            model = models.efficientnet_b0(weights=None)
            model.classifier[1] = nn.Linear(1280, NUM_CLASSES)
            state = torch.load(self.model_path, map_location="cpu", weights_only=True)
            model.load_state_dict(state)
            model.eval()
            self._model = model
            logger.info("[EfficientNet] Loaded from %s", self.model_path)
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
