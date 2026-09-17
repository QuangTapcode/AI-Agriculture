from fastapi.testclient import TestClient

from app.main import app


def test_pages_origin_can_send_authenticated_chat_request():
    response = TestClient(app).options(
        "/api/ai-chat/message/stream",
        headers={
            "Origin": "https://agriai-demo.pages.dev",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://agriai-demo.pages.dev"
    assert "authorization" in response.headers["access-control-allow-headers"]
