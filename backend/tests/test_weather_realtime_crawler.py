"""
Thời tiết phải được cào theo lịch riêng, gần thời gian thực.

Hiện trạng trước khi có file này:

  * beat_schedule chỉ có giá (2h sáng), cảnh báo (đầu giờ), dọn file (CN).
    Không có mục nào cho thời tiết.
  * Thời tiết chỉ được làm mới như TÁC DỤNG PHỤ của run_price_crawler — và
    hàm đó `return` sớm khi cào giá thất bại, nên thời tiết đi theo luôn.
  * Worker chạy bằng `celery ... worker`, không có `--beat` và cũng không có
    service beat riêng. Nên cả ba lịch trên thực tế chưa bao giờ chạy.

Kết quả: bảng WeatherData chỉ được cập nhật khi có người mở trang và cache
đã quá hạn — việc gọi Open-Meteo xảy ra ngay trong request của người dùng,
đó là lý do trang hiện "Dữ liệu realtime đang chậm (timeout)".
"""
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.tasks.celery_app import celery_app

GOC_DU_AN = Path(__file__).resolve().parents[2]


def _lich_thoi_tiet():
    for ten, cau_hinh in celery_app.conf.beat_schedule.items():
        if "weather" in cau_hinh["task"] or "thoi_tiet" in cau_hinh["task"]:
            return ten, cau_hinh
    return None, None


def test_co_lich_cao_thoi_tiet_rieng():
    ten, cau_hinh = _lich_thoi_tiet()
    assert cau_hinh is not None, (
        "beat_schedule không có mục nào cào thời tiết — dữ liệu chỉ được làm "
        "mới khi người dùng mở trang và cache đã hết hạn"
    )


def test_cao_it_nhat_moi_15_phut():
    """Open-Meteo phát theo lưới 15 phút; cào thưa hơn là bỏ lỡ quan trắc."""
    _, cau_hinh = _lich_thoi_tiet()
    assert cau_hinh is not None
    lich = cau_hinh["schedule"]
    giay = lich.total_seconds() if hasattr(lich, "total_seconds") else float(lich)
    assert giay <= 15 * 60, f"Cào mỗi {giay / 60:.0f} phút — thưa hơn lưới 15 phút của nguồn"


def test_khong_phu_thuoc_ket_qua_cao_gia():
    """Task thời tiết phải độc lập, không nằm trong nhánh thành công của giá."""
    _, cau_hinh = _lich_thoi_tiet()
    assert cau_hinh is not None
    assert "price" not in cau_hinh["task"], (
        "Thời tiết vẫn đi ké crawler giá — cào giá hỏng là thời tiết đứng theo"
    )


def test_beat_thuc_su_duoc_bat_trong_compose():
    """Có lịch mà không ai chạy lịch thì vẫn bằng không."""
    compose = (GOC_DU_AN / "docker-compose.yml").read_text(encoding="utf-8")
    assert "beat" in compose, (
        "docker-compose không khởi động Celery Beat — mọi beat_schedule đều nằm im"
    )


# ── Hành vi của task ────────────────────────────────────────────────────────

def _live(temp):
    return {
        "region": "Hà Nội", "temperature": temp, "temp_min": 23.3, "temp_max": 30.8,
        "rainfall": 0.2, "humidity": 98.0, "condition": "rain_showers",
        "wind_speed": 7.4, "uv_index": 6.0, "pressure": 1006.0, "weather_code": 81,
        "latitude": 21.0285, "longitude": 105.8542,
        "source_name": "Open-Meteo", "source_url": "https://api.open-meteo.com",
        "source_updated_at": datetime.now(),
    }


def test_task_luu_nhiet_do_do_duoc():
    """Cào xong phải ghi nhiệt độ quan trắc, không chỉ min/max."""
    from app.tasks import crawler_tasks

    ghi = []
    with patch.object(crawler_tasks, "_weather_client_realtime") as client, \
         patch.object(crawler_tasks, "upsert_weather_cache",
                      side_effect=lambda db, **kw: ghi.append(kw)), \
         patch("app.core.database.SessionLocal", MagicMock()):
        client.get_current.side_effect = lambda r: _live(23.5)
        crawler_tasks.crawl_weather_realtime()

    assert ghi, "Task không ghi bản ghi nào"
    assert all(k.get("temperature") == 23.5 for k in ghi), (
        "Không lưu nhiệt độ đo được — trang sẽ lại rơi về trung bình ngày"
    )


def test_khong_goi_trung_vung_cung_toa_do():
    """Cấu hình có cả 'Ha Noi' và 'Hà Nội' cùng toạ độ — chỉ gọi nguồn một lần."""
    from app.tasks import crawler_tasks

    da_goi = []
    with patch.object(crawler_tasks, "_weather_client_realtime") as client, \
         patch.object(crawler_tasks, "upsert_weather_cache", return_value=None), \
         patch("app.core.database.SessionLocal", MagicMock()):
        client.get_current.side_effect = lambda r: (da_goi.append(r), _live(23.5))[1]
        crawler_tasks.crawl_weather_realtime()

    assert len(da_goi) == len(set(da_goi))
    assert len(da_goi) <= 6, (
        f"Gọi Open-Meteo {len(da_goi)} lần cho 6 toạ độ — bí danh có dấu và "
        f"không dấu bị cào trùng"
    )


def test_mot_vung_hong_khong_lam_dung_ca_me():
    """Một tỉnh lỗi mạng không được kéo theo các tỉnh còn lại."""
    from app.tasks import crawler_tasks

    ghi = []

    def hong_mot_vung(region):
        if "Cần Thơ" in region:
            raise TimeoutError("Open-Meteo timeout")
        return _live(23.5)

    with patch.object(crawler_tasks, "_weather_client_realtime") as client, \
         patch.object(crawler_tasks, "upsert_weather_cache",
                      side_effect=lambda db, **kw: ghi.append(kw)), \
         patch("app.core.database.SessionLocal", MagicMock()):
        client.get_current.side_effect = hong_mot_vung
        kq = crawler_tasks.crawl_weather_realtime()

    assert len(ghi) >= 4, "Một vùng hỏng đã làm dừng cả mẻ"
    assert kq["failed"] >= 1


def test_moi_task_trong_lich_deu_duoc_dang_ky():
    """Beat gửi task theo TÊN; worker không import module thì task rơi vào hư không.

    `celery -A ... inspect registered` trên container trả về "- empty -":
    celery_app.py không import app.tasks.* nên không decorator nào chạy. Beat
    vẫn phát lịch đều đặn còn worker trả lời "Received unregistered task".
    """
    import importlib

    # Worker nạp đúng danh sách này lúc khởi động; làm y hệt để so registry.
    for ten_module in celery_app.conf.include:
        importlib.import_module(ten_module)

    dang_ky = set(celery_app.tasks.keys())
    thieu = [c["task"] for c in celery_app.conf.beat_schedule.values()
             if c["task"] not in dang_ky]
    assert not thieu, f"Có lịch nhưng chưa đăng ký task: {thieu}"
