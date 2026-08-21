"""
Đồng bộ schema DB cho khớp ORM models.

Hai việc, đều CHỈ THÊM:
  1. Tạo bảng chưa tồn tại (`create_all`, checkfirst=True).
  2. Thêm cột thiếu vào bảng đã có (`ALTER TABLE ... ADD`), luôn NULL-able
     nên hàng cũ nhận NULL và không bị từ chối.

Không xóa bảng, không xóa/đổi kiểu cột, không đụng dữ liệu đang có.
Cũng KHÔNG bơm dữ liệu mẫu — spec anti-mock (TOD0 §1) cấm giá/tin synthetic.

Chạy:
  python scripts/sync_schema.py          # xem trước, không ghi
  python scripts/sync_schema.py --apply  # thực sự thay đổi
"""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from sqlalchemy import inspect, text  # noqa: E402
from sqlalchemy.schema import AddConstraint  # noqa: F401,E402

from app.core.database import Base, engine  # noqa: E402
import app.models  # noqa: F401,E402  — nạp toàn bộ model vào Base.metadata


def _column_drift(insp) -> dict[str, list]:
    """Bảng đã tồn tại nhưng thiếu cột so với model."""
    have = set(insp.get_table_names())
    drift = {}
    for name, table in Base.metadata.tables.items():
        if name not in have:
            continue
        actual = {c["name"] for c in insp.get_columns(name)}
        gap = [c for c in table.columns if c.name not in actual]
        if gap:
            drift[name] = gap
    return drift


def _add_column(table_name: str, column) -> None:
    """ALTER TABLE ... ADD, ép NULL-able để không phá hàng dữ liệu cũ."""
    ddl_type = column.type.compile(engine.dialect)
    stmt = f"ALTER TABLE [{table_name}] ADD [{column.name}] {ddl_type} NULL"
    with engine.begin() as conn:
        conn.execute(text(stmt))


def main() -> int:
    apply = "--apply" in sys.argv
    insp = inspect(engine)

    existing = set(insp.get_table_names())
    declared = set(Base.metadata.tables)
    missing_tables = sorted(declared - existing)
    drift = _column_drift(insp)

    print(f"DB       : {engine.url.render_as_string(hide_password=True)}")
    print(f"Dang co  : {len(existing)} bang")
    print(f"Model can: {len(declared)} bang")

    if missing_tables:
        print(f"\nThieu {len(missing_tables)} bang:")
        for name in missing_tables:
            print(f"  - {name}")

    if drift:
        total = sum(len(v) for v in drift.values())
        print(f"\nLech cot: {len(drift)} bang, {total} cot:")
        for name, cols in sorted(drift.items()):
            print(f"  - {name}: {[c.name for c in cols]}")

    if not missing_tables and not drift:
        print("\nSchema da khop, khong co gi de lam.")
        return 0

    if not apply:
        print("\n(xem truoc) Chay lai voi --apply de thuc hien.")
        return 0

    if missing_tables:
        Base.metadata.create_all(engine, checkfirst=True)
        print(f"\nDa tao {len(missing_tables)} bang.")

    added, failed = 0, []
    for name, cols in sorted(drift.items()):
        for col in cols:
            try:
                _add_column(name, col)
                added += 1
            except Exception as exc:
                failed.append(f"{name}.{col.name}: {str(exc)[:100]}")

    if added:
        print(f"Da them {added} cot (deu NULL-able).")
    if failed:
        print(f"\nKhong them duoc {len(failed)} cot:")
        for line in failed:
            print(f"  - {line}")
        return 1

    print("\nXong. Du lieu cu khong bi dong toi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
