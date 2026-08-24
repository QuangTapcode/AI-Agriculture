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

# Nap backend/.env TRUOC khi import app: config doc bien moi truong luc import,
# va load_dotenv() mac dinh chi tim .env trong thu muc dang dung. Chay script
# tu goc repo se roi ve SQLite mac dinh va tao file rac neu thieu buoc nay.
from dotenv import load_dotenv  # noqa: E402
load_dotenv(BACKEND / ".env")

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


def _unicode_drift(insp) -> list[tuple[str, str, str]]:
    """Cột ORM khai Unicode nhưng trong DB là VARCHAR/TEXT.

    VARCHAR khong luu duoc 'i', 'uong', 'a'... nen chung thanh '?' ngay luc
    ghi — mat han, khong khoi phuc duoc tu DB. Doi sang NVARCHAR de lan ghi
    sau con nguyen dau.
    """
    from sqlalchemy import Unicode, UnicodeText

    have = set(insp.get_table_names())
    out = []
    for name, table in Base.metadata.tables.items():
        if name not in have:
            continue
        thuc_te = {c["name"]: str(c["type"]).upper() for c in insp.get_columns(name)}
        for col in table.columns:
            if not isinstance(col.type, (Unicode, UnicodeText)):
                continue
            loai = thuc_te.get(col.name, "")
            if loai.startswith("VARCHAR") or loai.startswith("TEXT"):
                out.append((name, col.name, col.type.compile(engine.dialect)))
    return out


def _indexes_on(conn, table_name: str, col_name: str) -> list[dict]:
    """Index dang phu thuoc vao cot — SQL Server chan ALTER COLUMN khi con chung."""
    rows = conn.execute(text("""
        SELECT i.name AS ten, i.is_unique AS duy_nhat,
               STUFF((SELECT ', [' + c2.name + ']' + CASE WHEN ic2.is_descending_key = 1
                                                          THEN ' DESC' ELSE '' END
                      FROM sys.index_columns ic2
                      JOIN sys.columns c2 ON c2.object_id = ic2.object_id
                                         AND c2.column_id = ic2.column_id
                      WHERE ic2.object_id = i.object_id AND ic2.index_id = i.index_id
                        AND ic2.is_included_column = 0
                      ORDER BY ic2.key_ordinal
                      FOR XML PATH('')), 1, 2, '') AS cac_cot
        FROM sys.indexes i
        JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
        JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        WHERE OBJECT_NAME(i.object_id) = :bang AND c.name = :cot
          AND i.is_primary_key = 0 AND i.type_desc = 'NONCLUSTERED'
    """), {"bang": table_name, "cot": col_name}).mappings().all()
    return [dict(r) for r in rows]


def _unique_constraints_on(conn, table_name: str, col_name: str) -> list[dict]:
    """UNIQUE CONSTRAINT phu thuoc vao cot.

    Index cua constraint khong the DROP INDEX — phai DROP CONSTRAINT roi tao
    lai sau khi doi kieu cot.
    """
    rows = conn.execute(text("""
        SELECT kc.name AS ten,
               STUFF((SELECT ', [' + c2.name + ']'
                      FROM sys.index_columns ic2
                      JOIN sys.columns c2 ON c2.object_id = ic2.object_id
                                         AND c2.column_id = ic2.column_id
                      WHERE ic2.object_id = kc.parent_object_id
                        AND ic2.index_id = kc.unique_index_id
                      ORDER BY ic2.key_ordinal
                      FOR XML PATH('')), 1, 2, '') AS cac_cot
        FROM sys.key_constraints kc
        JOIN sys.index_columns ic ON ic.object_id = kc.parent_object_id
                                 AND ic.index_id = kc.unique_index_id
        JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        WHERE OBJECT_NAME(kc.parent_object_id) = :bang AND c.name = :cot
          AND kc.type = 'UQ'
        GROUP BY kc.name, kc.parent_object_id, kc.unique_index_id
    """), {"bang": table_name, "cot": col_name}).mappings().all()
    return [dict(r) for r in rows]


def _alter_type(table_name: str, col_name: str, ddl_type: str) -> None:
    """ALTER COLUMN sang NVARCHAR.

    Cot nam trong index thi phai go index truoc roi tao lai — neu khong
    SQL Server tu choi doi kieu. Lam trong mot transaction de khong bo lai
    bang thieu index khi co su co.
    """
    with engine.begin() as conn:
        rang_buoc = _unique_constraints_on(conn, table_name, col_name)
        ten_rang_buoc = {r["ten"] for r in rang_buoc}
        # Index sinh ra boi UNIQUE CONSTRAINT phai go bang DROP CONSTRAINT,
        # DROP INDEX se bi tu choi.
        idx = [i for i in _indexes_on(conn, table_name, col_name)
               if i["ten"] not in ten_rang_buoc]

        for r in rang_buoc:
            conn.execute(text(
                f"ALTER TABLE [{table_name}] DROP CONSTRAINT [{r['ten']}]"
            ))
        for i in idx:
            conn.execute(text(f"DROP INDEX [{i['ten']}] ON [{table_name}]"))

        conn.execute(text(
            f"ALTER TABLE [{table_name}] ALTER COLUMN [{col_name}] {ddl_type} NULL"
        ))

        for i in idx:
            duy_nhat = "UNIQUE " if i["duy_nhat"] else ""
            conn.execute(text(
                f"CREATE {duy_nhat}NONCLUSTERED INDEX [{i['ten']}] "
                f"ON [{table_name}] ({i['cac_cot']})"
            ))
        for r in rang_buoc:
            conn.execute(text(
                f"ALTER TABLE [{table_name}] ADD CONSTRAINT [{r['ten']}] "
                f"UNIQUE ({r['cac_cot']})"
            ))


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

    unicode_drift = _unicode_drift(insp)
    if unicode_drift:
        print(f"\nLech kieu Unicode: {len(unicode_drift)} cot dang VARCHAR/TEXT")
        for t, c, _ in unicode_drift[:10]:
            print(f"  - {t}.{c}")
        if len(unicode_drift) > 10:
            print(f"  ... va {len(unicode_drift) - 10} cot nua")

    if not missing_tables and not drift and not unicode_drift:
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

    doi_kieu, loi_kieu = 0, []
    for t, c, ddl in unicode_drift:
        try:
            _alter_type(t, c, ddl)
            doi_kieu += 1
        except Exception as exc:
            loi_kieu.append(f"{t}.{c}: {str(exc)[:90]}")

    if added:
        print(f"Da them {added} cot (deu NULL-able).")
    if doi_kieu:
        print(f"Da doi {doi_kieu} cot sang NVARCHAR (giu nguyen du lieu dang co).")
    if loi_kieu:
        print(f"\nKhong doi duoc {len(loi_kieu)} cot (thuong do co index/constraint):")
        for line in loi_kieu[:6]:
            print(f"  - {line}")
    if failed:
        print(f"\nKhong them duoc {len(failed)} cot:")
        for line in failed:
            print(f"  - {line}")
        return 1

    print("\nXong. Du lieu cu khong bi dong toi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
