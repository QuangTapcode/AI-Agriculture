#!/usr/bin/env python3
"""
merge_datasets.py
Gộp 2 dataset YOLO (đợt 1 + đợt 2) thành 1 dataset thống nhất.

DÙNG KHI NÀO?
  - Bạn export RIÊNG dataset đợt 1 và dataset 20 loại mới (2 file zip khác nhau).
  - Cần ghép lại và REMAP class index để không bị trùng/đè nhau.

KHÔNG CẦN script này nếu: bạn gộp cả 2 vào CÙNG 1 project Roboflow
rồi export 1 lần (Roboflow tự quản index - cách khuyến nghị, xem HUONG_DAN.md).

------------------------------------------------------------
Cấu trúc dataset YOLO chuẩn (mỗi dataset):
  dataset/
    train/images/*.jpg   train/labels/*.txt
    valid/images/*.jpg   valid/labels/*.txt
    test/images/*.jpg    test/labels/*.txt
    data.yaml

Label .txt mỗi dòng: <class_id> <cx> <cy> <w> <h>  (toạ độ normalize 0-1)
------------------------------------------------------------

CÁCH CHẠY:
  python merge_datasets.py \
      --d1 ./fruits_dot1 \
      --d2 ./veg_dot2 \
      --out ./fruits-veg-quality

Sau khi gộp, mở data.yaml ở thư mục --out để kiểm tra danh sách class.
"""

import argparse
import shutil
from pathlib import Path
import yaml


SPLITS = ["train", "valid", "test"]


def load_names(yaml_path: Path):
    """Đọc danh sách class names từ data.yaml (hỗ trợ cả list lẫn dict)."""
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    names = data["names"]
    if isinstance(names, dict):
        names = [names[i] for i in sorted(names.keys())]
    return list(names)


def remap_label_file(src_txt: Path, dst_txt: Path, offset: int):
    """Copy 1 file label, cộng offset vào class_id của từng dòng."""
    lines_out = []
    with open(src_txt, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            parts[0] = str(int(parts[0]) + offset)
            lines_out.append(" ".join(parts))
    dst_txt.parent.mkdir(parents=True, exist_ok=True)
    with open(dst_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_out) + ("\n" if lines_out else ""))


def copy_split(src_root: Path, out_root: Path, offset: int, prefix: str):
    """Copy images + labels của 1 dataset sang out, remap index, đổi tên tránh trùng."""
    n_img, n_lbl = 0, 0
    for split in SPLITS:
        img_dir = src_root / split / "images"
        lbl_dir = src_root / split / "labels"
        if not img_dir.exists():
            continue
        for img in img_dir.iterdir():
            if img.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
                continue
            new_name = f"{prefix}_{img.name}"
            dst_img = out_root / split / "images" / new_name
            dst_img.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(img, dst_img)
            n_img += 1
            # label tương ứng
            lbl = lbl_dir / (img.stem + ".txt")
            dst_lbl = out_root / split / "labels" / f"{prefix}_{img.stem}.txt"
            if lbl.exists():
                remap_label_file(lbl, dst_lbl, offset)
                n_lbl += 1
            else:
                # ảnh không có nhãn -> tạo label rỗng (background)
                dst_lbl.parent.mkdir(parents=True, exist_ok=True)
                dst_lbl.write_text("", encoding="utf-8")
    print(f"  [{prefix}] copied {n_img} ảnh, {n_lbl} label (offset={offset})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--d1", required=True, help="Thư mục dataset đợt 1")
    ap.add_argument("--d2", required=True, help="Thư mục dataset đợt 2 (rau củ)")
    ap.add_argument("--out", required=True, help="Thư mục output gộp")
    args = ap.parse_args()

    d1, d2, out = Path(args.d1), Path(args.d2), Path(args.out)

    names1 = load_names(d1 / "data.yaml")
    names2 = load_names(d2 / "data.yaml")
    print(f"Dataset 1: {len(names1)} class")
    print(f"Dataset 2: {len(names2)} class")

    # Đợt 1 giữ index gốc 0..N1-1; đợt 2 dời lên +N1
    offset1 = 0
    offset2 = len(names1)
    merged_names = names1 + names2

    if out.exists():
        print(f"Xoá output cũ: {out}")
        shutil.rmtree(out)

    print("Copy dataset 1...")
    copy_split(d1, out, offset1, prefix="d1")
    print("Copy dataset 2...")
    copy_split(d2, out, offset2, prefix="d2")

    # Ghi data.yaml gộp
    data_out = {
        "path": str(out.resolve()),
        "train": "train/images",
        "val": "valid/images",
        "test": "test/images",
        "nc": len(merged_names),
        "names": {i: n for i, n in enumerate(merged_names)},
    }
    with open(out / "data.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(data_out, f, allow_unicode=True, sort_keys=False)

    print(f"\nXONG. Tổng {len(merged_names)} class -> {out/'data.yaml'}")
    print("Kiểm tra lại danh sách class trước khi train!")


if __name__ == "__main__":
    main()
