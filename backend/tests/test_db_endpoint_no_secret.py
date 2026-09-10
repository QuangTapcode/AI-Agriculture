"""
/db-test không được lộ thông tin đăng nhập database.

Endpoint này không yêu cầu đăng nhập và đang trả về nguyên chuỗi kết nối:

    "database_url": "mssql+pymssql://sa:YourStrongPassword123!@db:1433/NongNghiepAI"

Tức là ai gọi được API cũng có mật khẩu tài khoản sa — quyền quản trị toàn
bộ SQL Server, không chỉ database này.

Vẫn cần biết mình đang nối vào DB nào: dự án có lúc chạy hai database song
song (.\SQLEXPRESS trên máy và db:1433 trong container) với số liệu khác
nhau, nên endpoint phải nói rõ host + tên database — nhưng không kèm mật khẩu.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# Conftest ep DATABASE_URL sang SQLite nen goi endpoint that se khong bao gio
# lo mat khau. Phai kiem tra chinh ham che, voi chuoi ket noi that.
CHUOI_THAT = "mssql+pymssql://sa:YourStrongPassword123!@db:1433/NongNghiepAI"


def test_che_mat_khau_trong_chuoi_ket_noi():
    from app.core.database import che_thong_tin_dang_nhap

    che = che_thong_tin_dang_nhap(CHUOI_THAT)

    assert "YourStrongPassword123!" not in che, f"Van lo mat khau: {che}"
    assert "sa:" not in che, f"Van lo ten dang nhap: {che}"


def test_che_xong_van_doc_duoc_host_va_db():
    from app.core.database import che_thong_tin_dang_nhap

    che = che_thong_tin_dang_nhap(CHUOI_THAT)

    assert "db:1433" in che, che
    assert "NongNghiepAI" in che, che


def test_khong_lam_hong_url_sqlite():
    from app.core.database import che_thong_tin_dang_nhap

    assert che_thong_tin_dang_nhap("sqlite:///./agri.db") == "sqlite:///./agri.db"


def test_endpoint_khong_tra_chuoi_co_mat_khau():
    body = client.get("/db-test").text

    for bi_mat in ("YourStrongPassword123!", "password="):
        assert bi_mat not in body, f"Lo {bi_mat!r} trong /db-test"


def test_van_noi_ro_dang_noi_vao_dau():
    """Che mật khẩu nhưng vẫn phải phân biệt được hai database."""
    d = client.get("/db-test").json()

    assert d.get("status") == "success"
    # SQLite định danh bằng đường dẫn file, không có host — chấp nhận cả hai.
    assert d.get("database") or d.get("database_url"), "Không cho biết đang nối vào đâu"
    assert "sqlite" in str(d.get("database_url")) or d.get("host"), (
        "Không cho biết host — không phân biệt được local với container"
    )
