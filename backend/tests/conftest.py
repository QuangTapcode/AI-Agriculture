"""
Test chạy trên SQLite tạm, không phụ thuộc SQL Server của máy dev.

`app.core.database` dựng engine ngay lúc import, nên DATABASE_URL phải được
đặt TRƯỚC khi bất kỳ module app nào được nạp — conftest được pytest load đầu
tiên nên đây là chỗ duy nhất làm được.

Đặt AGRI_TEST_DB=real để chạy ngược lại trên DATABASE_URL thật trong .env.
"""

import os
import sys
import tempfile
from pathlib import Path

# train_dot2/ nằm ở thư mục gốc repo, ngoài backend/ — cho phép test import nó
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_USE_REAL_DB = os.getenv("AGRI_TEST_DB", "").lower() == "real"

if not _USE_REAL_DB:
    _db_path = Path(tempfile.gettempdir()) / "agri_ai_test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{_db_path.as_posix()}"

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    """Dựng schema một lần cho cả phiên test."""
    from app.core.database import Base, engine
    import app.models  # noqa: F401 — nạp model vào Base.metadata

    if not _USE_REAL_DB:
        # Dựng lại từ đầu mỗi phiên. File nằm cố định trong thư mục temp, mà
        # create_all(checkfirst=True) bỏ qua nguyên bảng đã tồn tại — nên cột
        # mới thêm vào model không bao giờ được tạo, và test đổ với lỗi kiểu
        # "no such column: AIConversations.deleted_at" cho tới khi ai đó xoá
        # file bằng tay.
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

    yield
