"""
Sửa dữ liệu tiếng Việt đã mất dấu do cột từng là VARCHAR.

Cột VARCHAR không lưu được 'ị', 'ườ', 'ả'... nên chúng bị thay bằng '?' NGAY
LÚC GHI. Ký tự gốc mất hẳn, không đọc lại được từ DB. Script này chỉ khôi
phục những giá trị **suy lại được**:

  - SourceName / SourceURL: là hằng số trong code, gán lại từ nguồn chuẩn.
  - Region: chuẩn hoá qua bảng alias (khớp phần không dấu rồi trả tên có dấu).

Không suy lại được (cần người dùng tự nhập lại):
  - Users.FullName — tên riêng, không có nguồn nào để đối chiếu.

Chạy:
  python scripts/repair_vietnamese.py           # xem trước
  python scripts/repair_vietnamese.py --apply   # thực hiện
"""

import re
import sys
import unicodedata

# Console Windows mac dinh cp1252, khong in duoc tieng Viet
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND / ".env")

from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import IntegrityError, SQLAlchemyError  # noqa: E402

from app.core.database import engine  # noqa: E402


def _bo_dau(s: str) -> str:
    """Bỏ dấu tiếng Việt.

    Lưu ý 'ð' (U+00F0, eth Bắc Âu): khi cột còn là VARCHAR, SQL Server ánh xạ
    'Đ' sang 'Ð' thay vì thành '?'. Không quy nó về 'd' thì chuỗi hỏng sẽ
    không khớp được alias nào.
    """
    s = (s or "").lower().replace("đ", "d").replace("ð", "d")
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _sua_source_name(conn, apply: bool) -> int:
    """SourceName là hằng số — gán lại nguyên vẹn từ code."""
    from app.core.real_data import OFFICIAL_AGRI_SOURCE_NAME

    n = conn.execute(
        text("SELECT COUNT(*) FROM MarketPrices WHERE SourceName LIKE :mau"),
        {"mau": "%?%"},
    ).scalar()
    if n and apply:
        conn.execute(
            text("UPDATE MarketPrices SET SourceName = :ten WHERE SourceName LIKE :mau"),
            {"ten": OFFICIAL_AGRI_SOURCE_NAME, "mau": "%?%"},
        )
    return n or 0


def _sua_region(conn, bang: str, apply: bool) -> int:
    """Region chuẩn hoá qua bảng alias: khớp phần không dấu -> tên có dấu."""
    from app.services.pricing_service import REGION_DISPLAY_ALIASES

    # pyodbc dung '?' lam placeholder tham so, nen KHONG duoc viet thang
    # LIKE '%?%' trong chuoi SQL — phai truyen qua bind parameter.
    rows = conn.execute(
        text(f"SELECT DISTINCT Region FROM {bang} WHERE Region LIKE :mau"),
        {"mau": "%?%"},
    ).scalars().all()

    sua = 0
    for hong in rows:
        # '?' la ky tu bi mat — coi no la dai dien 1 ky tu bat ky.
        # "D?k L?k" -> regex "d.k l.k" -> khop alias "dak lak".
        mau = re.escape(_bo_dau(hong)).replace(r"\?", ".")
        dung = next(
            (v for k, v in REGION_DISPLAY_ALIASES.items()
             if re.fullmatch(mau, k)),
            None,
        )
        if not dung:
            print(f"    khong suy duoc: {hong!r}")
            continue
        sua += 1
        print(f"    {hong!r} -> {dung!r}")
        if not apply:
            continue

        try:
            with conn.begin_nested():
                conn.execute(text(
                    f"UPDATE {bang} SET Region = :dung WHERE Region = :hong"
                ), {"dung": dung, "hong": hong})
        except IntegrityError:
            # Dong hong trung khoa voi dong da dung (cung vung, cung ngay).
            # Ban dung da co san nen ban hong chi la rac — xoa di, nhung chi
            # khi thuc su ton tai ban dung de khong lam mat du lieu.
            co_ban_dung = conn.execute(
                text(f"SELECT COUNT(*) FROM {bang} WHERE Region = :dung"),
                {"dung": dung},
            ).scalar()
            if co_ban_dung:
                n = conn.execute(
                    text(f"DELETE FROM {bang} WHERE Region = :hong"),
                    {"hong": hong},
                ).rowcount
                print(f"       trung khoa -> xoa {n} dong hong "
                      f"(da co {co_ban_dung} dong dung)")
            else:
                print("       trung khoa nhung KHONG co ban dung — giu nguyen")
    return sua


def main() -> int:
    apply = "--apply" in sys.argv
    print(f"DB: {engine.url.render_as_string(hide_password=True)}\n")

    with engine.begin() as conn:
        n = _sua_source_name(conn, apply)
        print(f"MarketPrices.SourceName : {n} dong mat dau")

        for bang in ("Users", "MarketPrices", "WeatherData"):
            try:
                print(f"{bang}.Region:")
                _sua_region(conn, bang, apply)
            except SQLAlchemyError as exc:
                # Chi nuot loi DB (bang khong co cot Region). Loi khac —
                # vi du console khong in duoc tieng Viet — phai lo ra.
                print(f"    bo qua, khong truy van duoc: {str(exc)[:70]}")

        con_lai = conn.execute(
            text("SELECT COUNT(*) FROM Users WHERE FullName LIKE :mau"),
            {"mau": "%?%"},
        ).scalar()

    print(f"\nUsers.FullName: {con_lai} dong mat dau — KHONG suy lai duoc,")
    print("nguoi dung can tu sua lai ten trong phan Cai dat.")
    print("\n(xem truoc)" if not apply else "\nDa ap dung.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
