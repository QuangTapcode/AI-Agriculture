"""
TDD: classifier phải theo số class của checkpoint, không cứng 16.

Đợt 2 mở rộng sang 96 class (4 quả + 20 rau củ × 4 mức). Hiện `CLASS_NAMES`
và `nn.Linear(1280, 16)` đều hardcode, nên thả weights 96 class vào sẽ làm
`load_state_dict` báo shape mismatch — và lỗi đó bị `except` nuốt, model thành
None, hệ thống lặng lẽ chấm mọi thứ là "Fresh".

Tên class phải đi kèm weights (file `<weights>.classes.json`) để việc đổi
danh sách rau củ không cần sửa code.
"""
import json

import numpy as np
import pytest

from ai_models.efficientnet_classifier import EfficientNetClassifier

torch = pytest.importorskip("torch")


def _write_checkpoint(tmp_path, n_classes: int, names: list[str] | None = None):
    """Tạo checkpoint EfficientNet-B0 n_classes + file classes.json cạnh nó."""
    import torch.nn as nn
    from torchvision import models

    model = models.efficientnet_b0(weights=None)
    model.classifier[1] = nn.Linear(1280, n_classes)

    weights_path = tmp_path / f"model_{n_classes}.pt"
    torch.save(model.state_dict(), weights_path)

    if names is not None:
        weights_path.with_suffix(".classes.json").write_text(
            json.dumps(names, ensure_ascii=False), encoding="utf-8"
        )
    return weights_path


def test_loads_checkpoint_with_more_classes(tmp_path):
    """Checkpoint 96 class phải nạp được, không bị shape mismatch."""
    names = [
        f"{fruit} {level}"
        for fruit in [f"Veg{i}" for i in range(24)]
        for level in ("Fresh", "Rotten", "Semifresh", "Semirotten")
    ]
    assert len(names) == 96

    path = _write_checkpoint(tmp_path, 96, names)
    result = EfficientNetClassifier(model_path=str(path)).classify(
        np.full((224, 224, 3), 128, dtype=np.uint8)
    )

    assert "error" not in result, f"Không nạp được checkpoint 96 class: {result.get('error')}"
    assert len(result["probabilities"]) == 96


def test_class_names_come_from_sidecar_file(tmp_path):
    """Đổi danh sách rau củ chỉ cần sửa classes.json, không đụng code."""
    names = ["Tomato Fresh", "Tomato Rotten", "Carrot Fresh", "Carrot Rotten"]
    path = _write_checkpoint(tmp_path, 4, names)

    result = EfficientNetClassifier(model_path=str(path)).classify(
        np.full((224, 224, 3), 200, dtype=np.uint8)
    )

    assert set(result["probabilities"]) == set(names)
    assert result["fruit_type"] in {"Tomato", "Carrot"}


def test_falls_back_to_builtin_16_when_no_sidecar(tmp_path):
    """Không có classes.json => giữ 16 class đợt 1, không vỡ hệ thống cũ."""
    path = _write_checkpoint(tmp_path, 16, names=None)

    result = EfficientNetClassifier(model_path=str(path)).classify(
        np.full((224, 224, 3), 128, dtype=np.uint8)
    )

    assert "error" not in result
    assert len(result["probabilities"]) == 16
    assert "Apple Fresh" in result["probabilities"]
