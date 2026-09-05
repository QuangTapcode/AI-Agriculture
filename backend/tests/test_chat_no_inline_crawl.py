"""
TDD: hỏi đáp AI đọc DB cache, không cào web đồng bộ.

Đo thực tế /api/chat: 18.9s tổng, trong đó 17.2s là 6 lượt HTTP ra
thitruongnongsan.gov.vn, chỉ 1.7s cho LLM + DB. Tức 91% thời gian người
dùng chờ là để cào lại thứ crawler nền đã cào mỗi 2 giờ.

TOD0 §4: dữ liệu nặng phải đọc từ cache, không chặn request người dùng.

Đếm ở tầng httpx thay vì monkeypatch resilient_request — các module đã
`from ... import resilient_request` nên vá thuộc tính module không chạm tới.
"""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app

NOI_BO = ("127.0.0.1", "localhost", "testserver")


@pytest.fixture
def http_ra_ngoai(monkeypatch):
    """Ghi lại mọi lượt HTTP ra Internet (bỏ qua Ollama/API nội bộ)."""
    goi = []

    for lop in (httpx.Client, httpx.AsyncClient):
        that = lop.send

        def lam(self, request, *a, __that=that, **kw):
            host = request.url.host or ""
            if not any(n in host for n in NOI_BO):
                goi.append(str(request.url)[:70])
            return __that(self, request, *a, **kw)

        monkeypatch.setattr(lop, "send", lam)
    return goi


def test_chat_khong_cao_web_dong_bo(http_ra_ngoai):
    """Một câu hỏi không được kéo theo nhiều lượt cào web."""
    r = TestClient(app).post("/api/chat", json={"question": "Giá cà phê Đắk Lắk hôm nay?"})
    assert r.status_code == 200

    assert not http_ra_ngoai, (
        f"Cào web đồng bộ {len(http_ra_ngoai)} lượt khi trả lời:\n  "
        + "\n  ".join(http_ra_ngoai[:4])
    )
