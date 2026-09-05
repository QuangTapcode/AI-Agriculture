"""
TDD: công thức train YOLO bản high-level.

Recipe phải là dữ liệu kiểm tra được, không phải tham số rải rác trong
notebook — có vậy mới test được và mới tái lập được giữa các đợt train.

Ràng buộc rút ra từ chính dự án:
- Đợt 1 dùng YOLO11n (nano) → yếu. Bản high-level phải to hơn.
- Model 96 class cần sidecar `<weights>.classes.json`, nếu không code sẽ
  đặt tên class_0..class_N (xem efficientnet_classifier.load_class_names).
- conf production 0.15 là lựa chọn có chủ đích để tăng recall; recipe chỉ
  giữ ngưỡng dùng khi đo mAP, không đụng vào cấu hình chạy thật.
"""
import pytest

from train_dot2.recipe import HIGH_LEVEL, build_train_args, write_classes_sidecar


def test_uses_a_bigger_backbone_than_nano():
    """Đợt 1 là yolo11n; bản high-level phải mạnh hơn hẳn."""
    assert HIGH_LEVEL.model.startswith("yolo11")
    assert not HIGH_LEVEL.model.startswith("yolo11n"), "Vẫn là nano — không phải high-level"


def test_train_args_are_valid_for_ultralytics():
    args = build_train_args(data_yaml="/ds/data.yaml", epochs=120)

    assert args["data"] == "/ds/data.yaml"
    assert args["epochs"] == 120
    assert args["imgsz"] >= 640
    assert 0 < args["lr0"] <= 0.1
    assert args["patience"] > 0


def test_colour_augmentation_stays_gentle():
    """Màu là NHÃN của bài toán này, không phải nhiễu cần làm bền.

    Quả tươi vs quả hỏng khác nhau ở hue/saturation. Recipe mặc định của
    ultralytics kéo hsv_s=0.7, đủ để biến quả tươi thành quả héo trong mắt
    model và dạy nó bỏ qua đúng đặc trưng cần học.
    """
    from train_dot2.recipe import BASELINE_NANO

    assert HIGH_LEVEL.hsv_s < BASELINE_NANO.hsv_s
    assert HIGH_LEVEL.hsv_h <= 0.015
    assert HIGH_LEVEL.hsv_s <= 0.3
    assert HIGH_LEVEL.hsv_v <= 0.3


def test_val_threshold_is_separate_from_production_recall_setting():
    """Ngưỡng đo mAP tách khỏi ngưỡng chạy thật.

    Production cố ý dùng conf thấp (0.15) để ưu tiên recall — xem
    test_recall_improvement.py. Recipe không được vô tình ghi đè lên nó.
    """
    assert HIGH_LEVEL.val_conf >= 0.25, "Ngưỡng đo mAP quá thấp thì số liệu bị thổi phồng"
    assert not hasattr(HIGH_LEVEL, "conf"), "Đừng đặt tên trùng khiến người đọc tưởng là ngưỡng production"


def test_sidecar_lets_backend_name_the_classes(tmp_path):
    """Ghi classes.json đúng chỗ backend tìm: <weights>.classes.json."""
    import json

    weights = tmp_path / "best.pt"
    weights.write_bytes(b"khong-phai-weights-that")
    names = ["Tomato Fresh", "Tomato Rotten", "Carrot Fresh"]

    sidecar = write_classes_sidecar(weights, names)

    assert sidecar.name == "best.classes.json"
    assert json.loads(sidecar.read_text(encoding="utf-8")) == names


def test_sidecar_refuses_empty_class_list(tmp_path):
    """Sidecar rỗng vô dụng mà lại che mất lỗi — phải nổ ngay."""
    with pytest.raises(ValueError):
        write_classes_sidecar(tmp_path / "best.pt", [])


# ── Recipe phải nói rõ chạy được ở đâu ────────────────────────────────────

def test_recipe_ghi_ro_vram_can_thiet():
    """Không ghi VRAM thì người dùng chạy rồi mới biết OOM sau vài phút."""
    from train_dot2 import recipe

    assert getattr(HIGH_LEVEL, "vram_gb", None), (
        "HIGH_LEVEL không nêu VRAM tối thiểu — GTX 1650 (4GB) sẽ OOM ngay"
    )
    assert HIGH_LEVEL.vram_gb >= 12, "yolo11m @768 batch16 cần khoảng 13GB"


def test_co_recipe_chay_duoc_tren_gpu_4gb():
    """Máy dev dùng GTX 1650 4GB — phải có lựa chọn train được tại chỗ."""
    from train_dot2.recipe import LOCAL_4GB

    assert LOCAL_4GB.vram_gb <= 4, f"LOCAL_4GB cần {LOCAL_4GB.vram_gb}GB, không vừa"
    assert LOCAL_4GB.model.startswith("yolo11"), "Vẫn phải là họ YOLO11"
    assert LOCAL_4GB.batch <= 8, "Batch lớn sẽ tràn VRAM 4GB"
    # Giữ nguyên bài học về màu — đây là nhãn của bài toán, không phải nhiễu
    assert LOCAL_4GB.hsv_s <= 0.3


def test_moi_recipe_deu_khai_vram():
    from train_dot2.recipe import BASELINE_NANO, LOCAL_4GB

    for r in (HIGH_LEVEL, BASELINE_NANO, LOCAL_4GB):
        assert getattr(r, "vram_gb", None), f"{r.name} thiếu vram_gb"
