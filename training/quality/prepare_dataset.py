"""
Chia ảnh thô thành train/val tự động (80/20).

Cấu trúc đầu vào:
  raw_data/
    fresh/       *.jpg  (hoặc .png)
    semifresh/
    semirotten/
    rotten/

Chạy:
  python training/quality/prepare_dataset.py
"""

import os, shutil, random
from pathlib import Path

QUALITY_DIR = Path(__file__).resolve().parent
RAW_DIR  = Path(os.getenv("AGRI_RAW_DATA_DIR", QUALITY_DIR / "raw_data"))
OUT_DIR  = Path(os.getenv("AGRI_DATA_DIR", QUALITY_DIR / "data"))
VAL_SPLIT = 0.2
SEED      = 42

random.seed(SEED)

classes = [d for d in os.listdir(RAW_DIR) if (RAW_DIR / d).is_dir()]
print(f"Classes tìm thấy: {classes}")

for cls in classes:
    src = Path(RAW_DIR) / cls
    imgs = [f for f in src.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png")]
    random.shuffle(imgs)

    n_val = max(1, int(len(imgs) * VAL_SPLIT))
    splits = {"val": imgs[:n_val], "train": imgs[n_val:]}

    for split, files in splits.items():
        dst = Path(OUT_DIR) / split / cls
        dst.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copy(f, dst / f.name)

    print(f"  {cls}: {len(splits['train'])} train | {len(splits['val'])} val")

print(f"\nDone! Dataset sẵn sàng tại '{OUT_DIR}/'")
print("Chạy tiếp: python train_quality_cnn.py")
