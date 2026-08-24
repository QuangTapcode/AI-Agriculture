"""
TDD: một quy ước cổng duy nhất cho backend.

Từng có hai quy ước lẫn lộn: start.bat chạy 5000 còn docker-compose + docs
dùng 8000, khiến người mới clone về bị frontend gọi nhầm cổng. Đã thống nhất
về 8000; test này giữ cho nó không lệch lại.
"""
import re
from pathlib import Path

import yaml

GOC = Path(__file__).resolve().parent.parent.parent
CONG = "8000"


def test_start_bat_dung_cong_chuan():
    bat = (GOC / "backend" / "start.bat").read_text(encoding="utf-8", errors="ignore")
    cong = re.search(r"--port\s+(\d+)", bat)
    assert cong, "start.bat không nêu --port"
    assert cong.group(1) == CONG, f"start.bat chạy cổng {cong.group(1)}, lệch chuẩn {CONG}"


def test_frontend_mac_dinh_dung_cong_chuan():
    """Chạy local không set biến môi trường thì vẫn phải gọi đúng backend."""
    api = (GOC / "frontend" / "src" / "services" / "api.js").read_text(encoding="utf-8")
    mac_dinh = re.search(r"VITE_API_URL\s*\|\|\s*'([^']+)'", api)
    assert mac_dinh, "api.js không có URL mặc định"
    assert f":{CONG}" in mac_dinh.group(1), (
        f"Frontend mặc định gọi {mac_dinh.group(1)}, không khớp cổng {CONG}"
    )


def test_docker_expose_cong_chuan():
    dv = yaml.safe_load((GOC / "docker-compose.yml").read_text(encoding="utf-8"))["services"]
    assert any(str(p).startswith(f"{CONG}:") for p in dv["backend"].get("ports", []))
