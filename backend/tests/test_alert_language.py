"""
TDD: cảnh báo gửi tới nông dân phải bằng tiếng Việt.

alert_service sinh title/message tiếng Anh cứng; frontend chỉ dịch được vài
từ lẻ qua translateUiText nên hiện ra câu lai:
    "Thời tiết risk high in Dak Lak"
    "Review weather risk before irrigation, spraying or harvest."

Người dùng là nông dân Việt Nam — cảnh báo phải đọc được.
"""
import pytest

from app.core.database import SessionLocal
from app.services.alert_service import alert_service

# Từ tiếng Anh không được xuất hiện trong nội dung gửi người dùng
ENGLISH_MARKERS = ("risk", "Review", "weather", "irrigation", "spraying", "harvest", " in ")


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


def test_auto_generated_alerts_are_vietnamese(db):
    result = alert_service.auto_generate_alerts(
        db, {"region": "Đắk Lắk", "crop_name": "ca phe"}, user=None
    )
    alerts = result.get("alerts") or result.get("generated") or []
    assert alerts, f"Không sinh được cảnh báo nào: {result}"

    for a in alerts:
        text = f"{a.get('title','')} {a.get('message','')}"
        found = [w for w in ENGLISH_MARKERS if w.lower() in text.lower()]
        assert not found, f"Cảnh báo còn tiếng Anh {found}: {text!r}"


def test_alert_title_names_the_region(db):
    """Nông dân phải biết cảnh báo cho vùng nào."""
    result = alert_service.auto_generate_alerts(
        db, {"region": "Đắk Lắk", "crop_name": "ca phe"}, user=None
    )
    alerts = result.get("alerts") or result.get("generated") or []
    assert any("Đắk Lắk" in a.get("title", "") for a in alerts), (
        f"Không cảnh báo nào nêu tên vùng: {[a.get('title') for a in alerts]}"
    )
