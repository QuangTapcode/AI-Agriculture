"""
TDD: mọi cột chữ phải khai Unicode, không được dùng String.

Trên MSSQL, SQLAlchemy `String` -> VARCHAR còn `Unicode` -> NVARCHAR. Quan
trọng hơn: pyodbc bind tham số theo KIỂU MODEL KHAI, nên cột khai `String`
bị hạ xuống codepage ANSI ngay lúc ghi — mất dấu tiếng Việt kể cả khi cột
trong DB đã là NVARCHAR.

Bằng chứng đối chứng: cùng model, cùng schema, chỉ khác driver —
  pymssql (Docker) -> 'Thông tin thị trường nông sản'   đúng
  pyodbc  (native) -> 'Thông tin th? tru?ng nông s?n'   hỏng

Quy tắc là tuyệt đối, không có ngoại lệ: phán đoán "cột này chắc chỉ chứa
ASCII" là chỗ dễ sai nhất (Region, SourceName, ErrorMessage đều từng bị xếp
nhầm vào nhóm đó). NVARCHAR tốn 2 byte/ký tự thay vì 1 — không đáng kể so
với việc hỏng dữ liệu người dùng.

Lưu ý về cây kiểu của SQLAlchemy: `UnicodeText` kế thừa `Text` chứ KHÔNG kế
thừa `Unicode`, nên phải kiểm tra cả hai — chỉ hỏi isinstance(..., Unicode)
sẽ báo nhầm mọi cột UnicodeText là lỗi.
"""
from sqlalchemy import String, Unicode, UnicodeText

from app.core.database import Base
import app.models  # noqa: F401 — nạp toàn bộ model vào Base.metadata


def test_every_text_column_is_unicode():
    offenders = [
        f"{table_name}.{col.name}"
        for table_name, table in Base.metadata.tables.items()
        for col in table.columns
        if isinstance(col.type, String)
        and not isinstance(col.type, (Unicode, UnicodeText))
    ]

    assert not offenders, (
        f"{len(offenders)} cột chữ còn dùng String — sẽ mất dấu tiếng Việt "
        f"khi ghi qua pyodbc:\n  " + "\n  ".join(sorted(offenders))
    )


def test_vietnamese_survives_roundtrip_through_real_driver(tmp_path):
    """Ghi rồi đọc lại tiếng Việt có dấu qua đúng driver đang cấu hình.

    Chạy trên SQLite (mặc định của test) sẽ luôn đạt vì SQLite là Unicode
    thuần — giá trị thật của test này là khi chạy với AGRI_TEST_DB=real
    trên SQL Server + pyodbc, nơi bug từng xảy ra.
    """
    from app.core.database import SessionLocal
    from app.models.crop import CropType

    goc = "Thông tin thị trường nông sản — Đắk Lắk, Quảng Ngãi"
    db = SessionLocal()
    try:
        crop = CropType(
            CropName="__test_dấu_tiếng_việt__",
            Category="Khac",   # CHECK constraint chỉ nhận giá trị không dấu
            Description=goc,
        )
        db.add(crop)
        db.commit()
        crop_id = crop.CropID

        db.expire_all()
        doc_lai = db.get(CropType, crop_id)
        assert doc_lai.Description == goc, (
            f"Mất dấu khi ghi/đọc:\n  ghi : {goc!r}\n  đọc: {doc_lai.Description!r}"
        )
        assert "?" not in doc_lai.CropName

        db.delete(doc_lai)
        db.commit()
    finally:
        db.close()
