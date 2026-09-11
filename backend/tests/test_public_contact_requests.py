from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import public_contact
from app.core.database import Base, get_db
from app.models.support_request import SupportRequest


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

app = FastAPI()
app.include_router(public_contact.router)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def setup_function():
    with TestingSessionLocal() as db:
        db.query(SupportRequest).delete()
        db.commit()


def valid_request(**overrides):
    body = {
        "name": "Nguyễn An",
        "email": "an@example.com",
        "phone": "",
        "topic": "technical",
        "message": "Tôi cần hỗ trợ kết nối dữ liệu thời tiết.",
        "website": "",
    }
    body.update(overrides)
    return body


def test_contact_request_is_stored_before_success_is_returned():
    response = client.post("/api/public/contact-requests", json=valid_request())

    assert response.status_code == 201
    payload = response.json()
    assert payload["data"]["id"] > 0
    assert payload["data"]["status"] == "new"
    assert payload["source"] == "database"
    assert payload["is_mock"] is False

    with TestingSessionLocal() as db:
        saved = db.query(SupportRequest).one()
        assert saved.Name == "Nguyễn An"
        assert saved.Email == "an@example.com"
        assert saved.Status == "new"


def test_contact_request_requires_email_or_phone():
    response = client.post(
        "/api/public/contact-requests",
        json=valid_request(email="", phone=""),
    )

    assert response.status_code == 422
    with TestingSessionLocal() as db:
        assert db.query(SupportRequest).count() == 0


def test_honeypot_submission_is_rejected_without_storing():
    response = client.post(
        "/api/public/contact-requests",
        json=valid_request(website="https://spam.example"),
    )

    assert response.status_code == 422
    with TestingSessionLocal() as db:
        assert db.query(SupportRequest).count() == 0


def test_sixth_request_within_fifteen_minutes_is_rate_limited():
    for index in range(5):
        response = client.post(
            "/api/public/contact-requests",
            json=valid_request(message=f"Yêu cầu hỗ trợ hợp lệ số {index + 1}."),
            headers={"CF-Connecting-IP": "203.0.113.7"},
        )
        assert response.status_code == 201

    blocked = client.post(
        "/api/public/contact-requests",
        json=valid_request(message="Yêu cầu thứ sáu trong cùng cửa sổ thời gian."),
        headers={"CF-Connecting-IP": "203.0.113.7"},
    )

    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau 15 phút."
