"""
Chia ảnh thô thành train/val tự động (80/20).

Cấu trúc đầu vào:
  raw_data/
    fresh/       *.jpg  (hoặc .png)
    semifresh/
    semirotten/
    rotten/

Chạy:
  python prepare_dataset.py
"""

import os, shutil, random
from pathlib import Path

RAW_DIR  = "raw_data"   # thư mục ảnh gốc của bạn
OUT_DIR  = "data"       # output cho train_quality_cnn.py
VAL_SPLIT = 0.2
SEED      = 42

random.seed(SEED)

classes = [d for d in os.listdir(RAW_DIR) if os.path.isdir(os.path.join(RAW_DIR, d))]
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
