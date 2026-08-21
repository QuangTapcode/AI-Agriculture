"""
Deploy model weights đã train vào nơi backend nạp.

Weights nằm trong `Training/` (theo dõi bằng git) nhưng backend nạp từ
`backend/ai_models/weights/` — thư mục bị .gitignore chặn. Script này nối
hai chỗ đó lại, chạy được nhiều lần.

Chạy:
  python scripts/setup_models.py
"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "Training"
DST_DIR = ROOT / "backend" / "ai_models" / "weights"

# Tên file giữ nguyên: code nạp theo đúng những tên này.
WEIGHTS = ["best.pt", "efficientnet_quality.pt"]


def main() -> int:
    DST_DIR.mkdir(parents=True, exist_ok=True)

    missing = []
    for name in WEIGHTS:
        src, dst = SRC_DIR / name, DST_DIR / name

        if not src.is_file():
            missing.append(name)
            print(f"  THIEU  {name} — khong tim thay {src}")
            continue

        if dst.is_file() and dst.stat().st_size == src.stat().st_size:
            print(f"  OK     {name} ({src.stat().st_size / 1e6:.1f} MB, da co)")
            continue

        shutil.copy2(src, dst)
        print(f"  COPY   {name} ({src.stat().st_size / 1e6:.1f} MB)")

    if missing:
        print(f"\nThieu {len(missing)} weights: {', '.join(missing)}")
        print(f"Dat file da train vao {SRC_DIR} roi chay lai.")
        return 1

    print(f"\nXong. Weights san sang tai {DST_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
