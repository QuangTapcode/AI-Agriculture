"""
Công thức train YOLO cho đánh giá chất lượng nông sản — bản high-level.

Vì sao tách thành module thay vì để rải trong notebook: tham số train là thứ
quyết định model mạnh hay yếu, nên nó cần test được, diff được giữa các đợt,
và tái lập được. Notebook chỉ gọi vào đây.

Ba quyết định quan trọng, đều xuất phát từ đặc thù bài toán:

1. **Backbone yolo11m thay vì yolo11n.** Đợt 1 dùng nano (~2.6M tham số) —
   nhỏ nhất họ YOLO11. Phân biệt Semifresh với Semirotten là bài toán khó,
   khác biệt nằm ở vệt thâm nhỏ và sắc độ, cần dung lượng model lớn hơn.

2. **Augmentation màu phải NHẸ.** Đây là điểm dễ sai nhất. Với detection
   thông thường, đảo màu mạnh giúp model bền vững. Nhưng ở đây *màu chính là
   nhãn*: quả tươi và quả hỏng khác nhau chủ yếu ở hue/saturation. Kéo
   hsv_s=0.7 như recipe mặc định sẽ biến quả tươi thành quả héo trong mắt
   model, dạy nó bỏ qua đúng đặc trưng cần học. Nên hsv_s/hsv_v giảm mạnh.

3. **imgsz 768 thay vì 640.** Khuyết tật trên vỏ (đốm thâm, mốc) là chi tiết
   nhỏ; tăng độ phân giải giữ được chúng sau khi resize.

Chọn recipe theo GPU đang có:

    HIGH_LEVEL   yolo11m @768 batch16   can ~13GB  -> Colab T4 (mien phi)
    LOCAL_4GB    yolo11s @640 batch8    can ~3.5GB -> GTX 1650 train tai cho
    BASELINE_NANO yolo11n @640          can ~4GB   -> giu de so sanh A/B

Suy luan nhe hon train rat nhieu: yolo11m chi ton ~1.5-2GB khi chay, nen
GTX 1650 van chay tot model train tren Colab.

Lưu ý về ngưỡng conf: `val_conf` ở đây chỉ dùng khi đo mAP lúc train. Ngưỡng
chạy thật (`FruitQualityPipeline.analyze`) đang cố ý để thấp (0.15) nhằm ưu
tiên recall — đó là kết quả tinh chỉnh có chủ đích, đừng đổi nếu chưa đo lại.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class TrainRecipe:
    """Một bộ tham số train hoàn chỉnh, đặt tên được."""

    name: str
    model: str
    imgsz: int
    epochs: int
    batch: int
    lr0: float
    lrf: float
    optimizer: str
    patience: int
    warmup_epochs: float
    close_mosaic: int

    # Augmentation — xem ghi chú (2) ở đầu file
    hsv_h: float
    hsv_s: float
    hsv_v: float
    degrees: float
    scale: float
    fliplr: float
    flipud: float
    mosaic: float
    mixup: float

    # VRAM tối thiểu để TRAIN được cấu hình này. Suy luận chạy nhẹ hơn nhiều
    # (yolo11m chỉ ~1.5-2GB), nên máy 4GB vẫn chạy được model train ở nơi khác.
    vram_gb: float

    # Ngưỡng dùng khi ĐÁNH GIÁ model (val/mAP), KHÔNG phải ngưỡng chạy thật.
    # Production đang cố ý dùng conf thấp để ưu tiên recall — xem
    # backend/tests/test_recall_improvement.py.
    val_conf: float
    val_iou: float

    notes: str = ""


HIGH_LEVEL = TrainRecipe(
    name="high_level_v1",
    model="yolo11m.pt",
    imgsz=768,
    epochs=120,
    batch=16,
    lr0=0.002,          # thấp vì fine-tune từ checkpoint, không train từ đầu
    lrf=0.01,           # cosine giảm về 1% lr0
    optimizer="AdamW",
    patience=30,
    warmup_epochs=5.0,
    close_mosaic=15,    # tắt mosaic 15 epoch cuối để model học ảnh thật

    hsv_h=0.010,        # gần như không đổi hue — hue là tín hiệu độ chín
    hsv_s=0.25,         # nhẹ (mặc định 0.7 phá mất dấu hiệu héo/hỏng)
    hsv_v=0.25,         # nhẹ, chỉ đủ bền với thay đổi ánh sáng
    degrees=12.0,
    scale=0.45,
    fliplr=0.5,
    flipud=0.0,         # quả chụp úp ngược không phải tình huống thật
    mosaic=1.0,
    mixup=0.10,

    vram_gb=13,         # yolo11m @768 batch16 — CHỈ chạy trên Colab T4/A100
    val_conf=0.35,      # ngưỡng chuẩn khi báo cáo mAP, không áp vào production
    val_iou=0.60,
    notes="Ưu tiên giữ nguyên tín hiệu màu; backbone medium; ảnh 768px.",
)


BASELINE_NANO = TrainRecipe(
    name="baseline_dot1",
    model="yolo11n.pt",
    imgsz=640, epochs=80, batch=16, lr0=0.01, lrf=0.01,
    optimizer="auto", patience=20, warmup_epochs=3.0, close_mosaic=10,
    hsv_h=0.015, hsv_s=0.7, hsv_v=0.4, degrees=0.0, scale=0.5,
    fliplr=0.5, flipud=0.0, mosaic=1.0, mixup=0.1,
    vram_gb=4,
    val_conf=0.25, val_iou=0.70,
    notes="Recipe đợt 1, giữ lại để so sánh A/B.",
)


LOCAL_4GB = TrainRecipe(
    name="local_4gb",
    model="yolo11s.pt",   # ~9M tham số — nano quá yếu, medium không vừa 4GB
    imgsz=640,            # 768 làm tràn VRAM; 640 vẫn giữ được đốm thâm cỡ vừa
    epochs=120,
    batch=8,              # giảm còn 4 nếu vẫn OOM
    lr0=0.002,
    lrf=0.01,
    optimizer="AdamW",
    patience=30,
    warmup_epochs=5.0,
    close_mosaic=15,

    # Giữ nguyên bài học quan trọng nhất: màu là NHÃN của bài toán này,
    # không phải nhiễu cần làm bền. Xem ghi chú (2) ở đầu file.
    hsv_h=0.010,
    hsv_s=0.25,
    hsv_v=0.25,
    degrees=12.0,
    scale=0.45,
    fliplr=0.5,
    flipud=0.0,
    mosaic=1.0,
    mixup=0.10,

    vram_gb=3.5,
    val_conf=0.35,
    val_iou=0.60,
    notes=(
        "Train ngay tren GTX 1650 (4GB). Doi lai: mAP thap hon HIGH_LEVEL. "
        "Co Colab thi dung HIGH_LEVEL roi tai best.pt ve chay local."
    ),
)


def build_train_args(
    data_yaml: str,
    recipe: TrainRecipe = HIGH_LEVEL,
    epochs: int | None = None,
    batch: int | None = None,
    project: str = "fruit_veg_quality",
) -> dict:
    """Đổi recipe thành kwargs truyền thẳng vào `YOLO.train(**args)`.

    epochs/batch cho phép ghi đè vì phụ thuộc VRAM máy chạy.
    """
    return {
        "data": data_yaml,
        "epochs": epochs if epochs is not None else recipe.epochs,
        "batch": batch if batch is not None else recipe.batch,
        "imgsz": recipe.imgsz,
        "optimizer": recipe.optimizer,
        "lr0": recipe.lr0,
        "lrf": recipe.lrf,
        "cos_lr": True,
        "warmup_epochs": recipe.warmup_epochs,
        "patience": recipe.patience,
        "close_mosaic": recipe.close_mosaic,
        "hsv_h": recipe.hsv_h,
        "hsv_s": recipe.hsv_s,
        "hsv_v": recipe.hsv_v,
        "degrees": recipe.degrees,
        "scale": recipe.scale,
        "fliplr": recipe.fliplr,
        "flipud": recipe.flipud,
        "mosaic": recipe.mosaic,
        "mixup": recipe.mixup,
        "project": project,
        "name": recipe.name,
        "exist_ok": True,
        "seed": 0,
        "deterministic": True,
        "plots": True,
    }


def write_classes_sidecar(weights_path: str | Path, class_names: list[str]) -> Path:
    """Ghi `<weights>.classes.json` cạnh file weights.

    Backend đọc file này để biết tên class; thiếu nó thì model khác 16 class
    sẽ hiện thành class_0, class_1, ... (xem efficientnet_classifier).
    """
    if not class_names:
        raise ValueError("class_names rỗng — sidecar sẽ vô dụng")

    path = Path(weights_path).with_suffix(".classes.json")
    path.write_text(
        json.dumps(list(class_names), ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return path
