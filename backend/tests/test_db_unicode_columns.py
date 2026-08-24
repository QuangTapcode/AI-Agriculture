"""
TDD: cột ORM khai Unicode thì trong DB phải là NVARCHAR.

Model đã khai đúng Unicode, nhưng DB thật còn 98 cột VARCHAR — phần lớn do
script sync_schema.py tạo trước đây bám theo kiểu ORM lúc đó còn là String.

Hậu quả đo được trên DB thật:
    MarketPrices.SourceName : 30/46 dòng chứa '?'
    Users.Region            : 3/18 dòng chứa '?'
    Users.FullName          : 1/18 dòng chứa '?'

VARCHAR không lưu được 'ị', 'ườ', 'ả'... nên chúng thành '?' ngay lúc ghi —
mất hẳn, không khôi phục được từ DB.

Test bỏ qua trên SQLite (luôn Unicode); chỉ có ý nghĩa với SQL Server.
"""
import pytest
from sqlalchemy import Unicode, UnicodeText, inspect

from app.core.database import Base, engine
import app.models  # noqa: F401

pytestmark = pytest.mark.skipif(
    engine.dialect.name != "mssql",
    reason="Chỉ kiểm được trên SQL Server (SQLite luôn lưu Unicode)",
)


def _cot_unicode_theo_orm():
    for ten_bang, tbl in Base.metadata.tables.items():
        for c in tbl.columns:
            if isinstance(c.type, (Unicode, UnicodeText)):
                yield ten_bang, c.name


def test_moi_cot_unicode_deu_la_nvarchar():
    insp = inspect(engine)
    co_bang = set(insp.get_table_names())
    sai = []

    for ten_bang, ten_cot in _cot_unicode_theo_orm():
        if ten_bang not in co_bang:
            continue
        for c in insp.get_columns(ten_bang):
            if c["name"] == ten_cot:
                loai = str(c["type"]).upper()
                if loai.startswith("VARCHAR") or loai.startswith("TEXT"):
                    sai.append(f"{ten_bang}.{ten_cot} = {loai}")
                break

    assert not sai, (
        f"{len(sai)} cột lưu tiếng Việt vẫn là VARCHAR — sẽ mất dấu khi ghi:\n  "
        + "\n  ".join(sai[:12])
    )
