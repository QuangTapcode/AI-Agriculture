"""
TDD: nguồn RSS chết không được kéo chậm cả hệ thống.

price_client và news_client đều có circuit breaker; rss_client thì không.
Nguồn RSS hỏng sẽ bị gọi lại mãi, mỗi lượt tốn trọn thời gian timeout —
đúng kiểu đã đo ở /api/chat (mỗi lượt 3.18s).

Circuit breaker: đủ số lần hỏng thì ngừng gọi trong một khoảng, thay vì
hành nguồn đã chết.
"""
from unittest.mock import patch

import pytest

from app.core.real_data import CircuitOpenError, external_circuit_breaker
from app.integrations.rss_client import rss_client


@pytest.fixture(autouse=True)
def reset_breaker():
    external_circuit_breaker._states.clear()
    yield
    external_circuit_breaker._states.clear()


def test_nguon_chet_thi_ngung_goi_sau_vai_lan():
    """Sau ngưỡng hỏng, không gọi mạng nữa — không hành nguồn đã chết."""
    so_lan_goi = []

    def luon_hong(*a, **kw):
        so_lan_goi.append(1)
        raise RuntimeError("nguon RSS chet")

    with patch("app.integrations.rss_client.resilient_request", side_effect=luon_hong):
        for _ in range(8):
            try:
                rss_client._fetch_feed("https://vnexpress.net/rss/nong-nghiep.rss")
            except Exception:
                pass

    nguong = external_circuit_breaker.failure_threshold
    assert len(so_lan_goi) <= nguong, (
        f"Gọi mạng {len(so_lan_goi)} lần dù nguồn đã chết — "
        f"circuit breaker phải chặn sau {nguong} lần"
    )


def test_circuit_mo_thi_bao_loi_ngay_khong_cho_timeout():
    """Circuit đang mở => trả lỗi tức thì, không tốn thời gian chờ mạng."""
    key = "rss_feed"
    for _ in range(external_circuit_breaker.failure_threshold):
        external_circuit_breaker.record_failure(key, "chet")

    with pytest.raises((CircuitOpenError, RuntimeError)):
        external_circuit_breaker.before_call(key)
