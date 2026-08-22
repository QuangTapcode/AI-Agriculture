"""
TDD: tên vùng hiện cho người dùng phải có dấu tiếng Việt.

Cảnh báo hiện "Rủi ro cao thời tiết tại Dak Lak" trong khi mọi chỗ khác là
"Đắk Lắk". Bên trong hệ thống dùng dạng không dấu để so khớp là hợp lý,
nhưng chuỗi đưa ra màn hình thì phải trả về dạng có dấu.
"""
import pytest

from app.core.database import SessionLocal
from app.services.alert_service import alert_service


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.mark.parametrize("nhap, mong_doi", [
    ("Dak Lak", "Đắk Lắk"),
    ("Đắk Lắk", "Đắk Lắk"),
    ("Ha Noi", "Hà Nội"),
    ("Can Tho", "Cần Thơ"),
])
def test_canh_bao_hien_ten_vung_co_dau(db, nhap, mong_doi):
    result = alert_service.auto_generate_alerts(
        db, {"region": nhap, "crop_name": "ca phe"}, user=None
    )
    alerts = result.get("alerts") or result.get("generated") or []
    assert alerts, "Không sinh được cảnh báo"

    titles = [a.get("title", "") for a in alerts]
    assert any(mong_doi in t for t in titles), (
        f"Vùng {nhap!r} hiện không dấu trong cảnh báo: {titles}"
    )
