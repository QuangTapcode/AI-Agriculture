"""
TDD: model weights phải thực sự được deploy tới đường dẫn mà code trỏ tới.

Bối cảnh: model đã train nằm ở `Training/*.pt` (repo root), nhưng code nạp từ
`ai_models/weights/*.pt`. Nếu thiếu, EfficientNet im lặng trả fallback
"Fresh" (= Loại 1) → mọi nông sản đều được chấm tươi. Đây là fail nguy hiểm
vì không có lỗi nào nổi lên.
"""
from pathlib import Path

import numpy as np

from ai_models.efficientnet_classifier import EfficientNetClassifier
from ai_models.fruit_quality_pipeline import FruitQualityPipeline


# ── Cycle 1: weights có mặt tại đường dẫn mặc định ─────────────────────────

def test_efficientnet_default_weights_exist():
    """Đường dẫn mặc định của classifier phải trỏ tới file có thật."""
    path = Path(EfficientNetClassifier().model_path)
    assert path.is_file(), f"Thiếu weights EfficientNet tại {path}"


def test_yolo_default_weights_exist():
    """Đường dẫn mặc định của pipeline phải trỏ tới file có thật."""
    path = Path(FruitQualityPipeline().model_path)
    assert path.is_file(), f"Thiếu weights YOLO tại {path}"


# ── Cycle 2: weights nạp được thật, không chỉ tồn tại ──────────────────────

def test_efficientnet_classifies_with_trained_model():
    """classify() phải chạy qua model đã train, không rơi vào nhánh fallback.

    Bắt được cả trường hợp file có mặt nhưng state_dict lệch kiến trúc
    (vd nạp checkpoint 96 class vào đầu ra 16 class).
    """
    crop = np.full((224, 224, 3), 128, dtype=np.uint8)

    result = EfficientNetClassifier().classify(crop)

    assert "error" not in result, f"Model không nạp được: {result.get('error')}"
    assert result["fruit_type"] != "Unknown"
    assert result["confidence"] > 0.0
    # Softmax trên đủ 16 class → tổng xác suất ≈ 1
    assert len(result["probabilities"]) == 16
    assert abs(sum(result["probabilities"].values()) - 1.0) < 0.01


# ── Cycle 3: model hỏng phải lộ ra, không được chấm bừa "Loại 1" ───────────

def test_full_image_result_flagged_when_classifier_unavailable(tmp_path, monkeypatch):
    """Model không nạp được → kết quả phải phân biệt được với phân tích thật.

    Trước đây nhánh này trả `source="efficientnet_fullimage"`,
    `quality_level="Fresh"` → grade_1 → "phù hợp siêu thị, xuất khẩu",
    giống hệt một lần phân tích thành công. Nông dân nhận Loại 1 cho quả hỏng.
    """
    import cv2

    from ai_models import efficientnet_classifier as eff_module

    # Trỏ classifier vào file không tồn tại → buộc đi nhánh không nạp được model
    monkeypatch.setattr(
        eff_module.efficientnet_classifier, "model_path", str(tmp_path / "missing.pt")
    )
    monkeypatch.setattr(eff_module.efficientnet_classifier, "_model", None)

    img_path = str(tmp_path / "fruit.jpg")
    cv2.imwrite(img_path, np.full((640, 640, 3), 128, dtype=np.uint8))

    result = FruitQualityPipeline().classify_full_image(img_path, crop_name_hint="xoài")

    assert result["source"] != "efficientnet_fullimage", (
        "Kết quả degraded đang giả dạng phân tích thật"
    )
    assert result["confidence"] == 0.0
    assert result["grade"] != "grade_1"
