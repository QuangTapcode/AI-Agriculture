"""
TDD: cấu hình Docker phải trỏ AI sang Ollama chạy trên máy host.

Trong container, "localhost" là chính container đó — Ollama chạy ngoài host
nên bản Docker hiện KHÔNG có AI. Docker Desktop cung cấp tên
`host.docker.internal` để container gọi ngược ra máy thật.
"""
from pathlib import Path

import yaml

GOC = Path(__file__).resolve().parent.parent.parent
COMPOSE = GOC / "docker-compose.yml"


def _dich_vu():
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8")).get("services", {})


def test_backend_tro_ai_ra_host():
    env = _dich_vu()["backend"].get("environment", {})
    url = env.get("AI_BASE_URL", "")
    assert url, "backend chưa có AI_BASE_URL — container sẽ không gọi được Ollama"
    assert "localhost" not in url and "127.0.0.1" not in url, (
        f"AI_BASE_URL={url!r} trỏ vào chính container, không phải Ollama trên host"
    )
    assert "host.docker.internal" in url


def test_worker_cung_tro_ai_ra_host():
    """Worker cũng chạy tác vụ cần AI — thiếu là lỗi lặng lẽ."""
    env = _dich_vu()["worker"].get("environment", {})
    assert "host.docker.internal" in env.get("AI_BASE_URL", "")


def test_khong_con_thuoc_tinh_version_loi_thoi():
    """Docker cảnh báo mỗi lần chạy: `version` is obsolete."""
    raw = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    assert "version" not in raw, "docker-compose.yml còn thuộc tính `version` lỗi thời"
