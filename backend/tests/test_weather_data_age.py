"""
Thời tiết hiện tại phải là số ĐO ĐƯỢC, và tuổi dữ liệu phải so được.

Đối chiếu thật lúc 23:36 ngày 09/09/2026, khu vực Hà Nội:

    Open-Meteo (23:30) : 24.1 C, 96%, mưa 0.2mm, gió 7.7, code 81
    App hiển thị       : 28.5 C, 96%, mưa 0.2mm, gió 7.7, rain_showers

Độ ẩm/mưa/gió/trạng thái khớp tuyệt đối — dữ liệu là thật và mới. Riêng
nhiệt độ lệch 4.4 độ vì bảng WeatherData không có cột nhiệt độ hiện tại:
luồng realtime nhận 24.1 rồi vứt đi, chỉ lưu TempMin/TempMax. Khi đọc lại
từ cache, hàm dựng lại nhiệt độ bằng (24.2 + 32.8)/2 = 28.5 — trung bình
cả ngày, gắn nhãn "hiện tại". Đêm mưa bị báo thành trời oi.

Lỗi thứ hai, cùng bảng: cột SourceUpdatedAt chứa hai múi giờ lẫn lộn.
Open-Meteo gọi với timezone=auto nên trả giờ ĐỊA PHƯƠNG của toạ độ
(23:30), trong khi FetchedAt do container ghi bằng giờ UTC (16:34). Lấy
hiệu với datetime.now() ra -412 phút. Phải quy về cùng đồng hồ tại nguồn.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.integrations.weather_client import WeatherClient
from app.services.weather_service import weather_service

OFFSET_BANGKOK = 25200  # +07:00, Open-Meteo tra ve kem payload


def _row(*, temperature=None, temp_min=24.2, temp_max=32.8,
         source_updated_at=None, fetched_at=None):
    """Bản ghi thời tiết tối thiểu, giống hàng lấy từ DB."""
    return SimpleNamespace(
        Temperature=temperature, TempMin=temp_min, TempMax=temp_max,
        Rainfall=0.2, Humidity=96.0, WeatherDesc="rain_showers",
        WindSpeed=7.7, UVIndex=1.65, Pressure=None, WeatherCode=81,
        Latitude=None, Longitude=None, Region="Hà Nội",
        RecordDate=datetime.now().date(),
        SourceName="Open-Meteo", SourceURL="https://api.open-meteo.com",
        SourceUpdatedAt=source_updated_at,
        FetchedAt=fetched_at,
        CreatedAt=source_updated_at,
    )


# ── Nhiệt độ hiện tại ────────────────────────────────────────────────────────

def test_dung_nhiet_do_do_duoc_khong_lay_trung_binh_ngay():
    bay_gio = datetime.now()
    row = _row(temperature=24.1, temp_min=24.2, temp_max=32.8,
               source_updated_at=bay_gio, fetched_at=bay_gio)

    kq = weather_service._weather_row_to_current(row, fallback_used=False)

    assert kq["temperature"] == 24.1, (
        f'Báo {kq["temperature"]} độ trong khi số đo là 24.1 — '
        f"đây là trung bình (24.2+32.8)/2 của cả ngày"
    )


def test_hang_cu_chua_co_nhiet_do_thi_lui_ve_trung_binh():
    """Không làm vỡ các hàng đã lưu trước khi có cột Temperature."""
    bay_gio = datetime.now()
    row = _row(temperature=None, source_updated_at=bay_gio, fetched_at=bay_gio)

    kq = weather_service._weather_row_to_current(row, fallback_used=False)

    assert kq["temperature"] == 28.5


# ── Múi giờ của mốc thời gian nguồn ──────────────────────────────────────────

def test_moc_thoi_gian_nguon_quy_ve_dong_ho_he_thong():
    """current.time là giờ địa phương của toạ độ; phải quy về giờ máy chủ."""
    payload = {
        "timezone": "Asia/Bangkok",
        "utc_offset_seconds": OFFSET_BANGKOK,
        "current": {
            "time": "2026-09-09T23:30",
            "temperature_2m": 24.1,
            "relative_humidity_2m": 96,
            "rain": 0.2,
            "wind_speed_10m": 7.7,
            "weather_code": 81,
        },
        "daily": {
            "temperature_2m_min": [24.2],
            "temperature_2m_max": [32.8],
            "uv_index_max": [6.0],
        },
    }
    mong_doi = (
        datetime(2026, 9, 9, 23, 30, tzinfo=timezone(timedelta(seconds=OFFSET_BANGKOK)))
        .astimezone()
        .replace(tzinfo=None)
    )

    client = WeatherClient()
    with patch.object(WeatherClient, "_get_json", return_value=payload):
        kq = client.get_current("Hà Nội")

    assert kq["source_updated_at"] == mong_doi, (
        f'Trả về {kq["source_updated_at"]}, đáng lẽ {mong_doi} — '
        f"lệch đúng bằng {OFFSET_BANGKOK // 3600} tiếng của múi giờ nguồn"
    )


# ── Tuổi dữ liệu ────────────────────────────────────────────────────────────

def test_tuoi_tinh_tu_luc_do_khong_phai_luc_hoi():
    """Số liệu đo 7 tiếng trước, vừa fetch lại 2 phút => tuổi là 7 tiếng."""
    bay_gio = datetime.now()
    row = _row(temperature=24.1,
               source_updated_at=bay_gio - timedelta(hours=7),
               fetched_at=bay_gio - timedelta(minutes=2))

    kq = weather_service._weather_row_to_current(row, fallback_used=False)

    assert kq["data_age_minutes"] >= 400
    assert kq["cache_status"] != "fresh_cache"


def test_khong_bao_gio_bao_tuoi_am():
    """Mốc nguồn lỡ nằm ở tương lai thì kẹp về 0, không hiện số âm."""
    bay_gio = datetime.now()
    row = _row(temperature=24.1,
               source_updated_at=bay_gio + timedelta(hours=7),
               fetched_at=bay_gio)

    kq = weather_service._weather_row_to_current(row, fallback_used=False)

    assert kq["data_age_minutes"] >= 0, "Tuổi dữ liệu âm — lộ lỗi lệch múi giờ"


def test_du_lieu_moi_do_van_duoc_coi_la_fresh():
    """Không siết nhầm: vừa đo xong thì đúng là mới."""
    bay_gio = datetime.now()
    row = _row(temperature=24.1,
               source_updated_at=bay_gio - timedelta(minutes=3),
               fetched_at=bay_gio - timedelta(minutes=2))

    kq = weather_service._weather_row_to_current(row, fallback_used=False)

    assert kq["data_age_minutes"] <= 5
    assert kq["cache_status"] == "fresh_cache"


def test_thieu_gio_do_thi_lui_ve_gio_fetch():
    """Nguồn không cho giờ đo => dùng FetchedAt, còn hơn không có gì."""
    bay_gio = datetime.now()
    row = _row(temperature=24.1, source_updated_at=None,
               fetched_at=bay_gio - timedelta(minutes=10))

    kq = weather_service._weather_row_to_current(row, fallback_used=False)

    assert 8 <= kq["data_age_minutes"] <= 12


# ── Ghi cache không được xoá mất số đo ──────────────────────────────────────

def test_ghi_du_bao_khong_xoa_nhiet_do_da_do(tmp_path):
    """Crawler dự báo ngày ghi đè lên cùng hàng — Temperature phải còn nguyên.

    upsert_weather_cache có ba nơi gọi: luồng realtime (có nhiệt độ đo được),
    luồng hourly và luồng dự báo 7 ngày (không có). Nếu gán thẳng
    row.Temperature = temperature thì hai luồng sau sẽ xoá trắng số đo, và
    trang thời tiết lại rơi về trung bình ngày sau vài phút.
    """
    from datetime import date

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.models.weather import Base, WeatherData
    from app.repositories.weather_repository import upsert_weather_cache

    engine = create_engine(f"sqlite:///{tmp_path}/w.db")
    Base.metadata.create_all(engine, tables=[WeatherData.__table__])
    db = sessionmaker(bind=engine)()

    upsert_weather_cache(db, region="Hà Nội", record_date=date.today(),
                         temperature=23.7, temp_min=24.2, temp_max=32.8)
    # Luồng dự báo chạy sau, không mang theo nhiệt độ hiện tại
    upsert_weather_cache(db, region="Hà Nội", record_date=date.today(),
                         temp_min=24.0, temp_max=33.0)

    row = db.query(WeatherData).filter(WeatherData.Region == "Hà Nội").one()
    assert row.Temperature == 23.7, "Dự báo ngày đã xoá mất nhiệt độ đo được"
    db.close()


def test_luong_realtime_khong_gan_cung_tuoi_bang_khong():
    """Open-Meteo phát theo lưới 15 phút — vừa gọi xong không có nghĩa là 0 phút."""
    from unittest.mock import MagicMock, patch

    # app.services xuat ra INSTANCE cung ten, phai lay dung MODULE de patch
    import importlib
    mod = importlib.import_module("app.services.weather_service")

    bay_gio = datetime.now()
    live = {
        "region": "Hà Nội", "temperature": 23.7, "temp_min": 24.2, "temp_max": 32.8,
        "rainfall": 0.2, "humidity": 96.0, "condition": "rain_showers",
        "wind_speed": 7.6, "uv_index": 6.0, "weather_code": 81,
        "source_name": "Open-Meteo", "source_url": "https://api.open-meteo.com",
        "source_updated_at": bay_gio - timedelta(minutes=12),
    }

    with patch.object(mod._weather_client, "get_current", return_value=live), \
         patch.object(mod, "upsert_weather_cache", return_value=None):
        kq = weather_service.get_current_weather(MagicMock(), "Hà Nội", force_refresh=True)

    assert kq["is_realtime"] is True
    assert 10 <= kq["data_age_minutes"] <= 14, (
        f'Báo {kq["data_age_minutes"]} phút cho số đo cách đây 12 phút'
    )


def test_crawler_du_bao_khong_ghi_de_moc_quan_trac(tmp_path):
    """Crawler dự báo ngày chạy sau không được nhận vơ mốc quan trắc.

    Hàng của hôm nay giữ số đo realtime (Temperature) cùng mốc quan trắc thật.
    Crawler dự báo chạy mỗi vài phút; nếu nó ghi SourceUpdatedAt = giờ chạy thì
    số đo đã cũ vẫn được báo là "vừa cập nhật".
    """
    from datetime import date

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.models.weather import Base, WeatherData
    from app.tasks.crawler_tasks import _save_weather_data_force

    engine = create_engine(f"sqlite:///{tmp_path}/c.db")
    Base.metadata.create_all(engine, tables=[WeatherData.__table__])
    Session = sessionmaker(bind=engine)

    quan_trac = datetime.now() - timedelta(hours=3)
    db = Session()
    db.add(WeatherData(Region="Hà Nội", RecordDate=date.today(), Temperature=23.5,
                       TempMin=23.3, TempMax=30.8, SourceUpdatedAt=quan_trac,
                       FetchedAt=quan_trac))
    db.commit()
    db.close()

    # Ham import SessionLocal ngay trong than ham => patch tai nguon
    with patch("app.core.database.SessionLocal", Session):
        _save_weather_data_force([{
            "region": "Hà Nội", "date": date.today().isoformat(),
            "temp_min": 23.0, "temp_max": 31.0, "humidity": 90,
        }])

    db = Session()
    row = db.query(WeatherData).filter(WeatherData.Region == "Hà Nội").one()
    assert row.SourceUpdatedAt == quan_trac, (
        "Crawler dự báo đã ghi đè mốc quan trắc — số đo 3 tiếng trước "
        "sẽ được báo là vừa cập nhật"
    )
    assert row.Temperature == 23.5
    db.close()


def test_ham_nong_du_bao_khong_ghi_de_moc_quan_trac(tmp_path):
    """Crawler ghi quan trắc trước, hâm nóng dự báo sau — thứ tự này làm mất mốc.

    crawl_weather_realtime ghi quan trắc hiện tại (có Temperature và
    SourceUpdatedAt thật của lưới 15 phút), rồi gọi get_forecast(force_refresh)
    để hâm nóng cache dự báo. Dự báo cũng upsert vào hàng CỦA HÔM NAY nhưng
    không mang theo nhiệt độ, và ghi SourceUpdatedAt = mốc dự báo — xoá mất
    mốc quan trắc vừa lưu.

    Đo thật sau khi bật TZ: SourceUpdatedAt = FetchedAt = 12:20:06.090 (có
    phần lẻ giây, tức datetime.now()), thay vì 12:15:00 của lưới Open-Meteo.
    """
    from datetime import date

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.models.weather import Base, WeatherData
    from app.repositories.weather_repository import upsert_weather_cache

    engine = create_engine(f"sqlite:///{tmp_path}/f.db")
    Base.metadata.create_all(engine, tables=[WeatherData.__table__])
    db = sessionmaker(bind=engine)()

    quan_trac = datetime.now().replace(minute=15, second=0, microsecond=0)
    upsert_weather_cache(db, region="Hà Nội", record_date=date.today(),
                         temperature=30.5, temp_min=24.0, temp_max=33.0,
                         source_updated_at=quan_trac, fetched_at=datetime.now())

    # Hâm nóng dự báo: không có nhiệt độ đo được, mốc là giờ chạy.
    upsert_weather_cache(db, region="Hà Nội", record_date=date.today(),
                         temp_min=24.2, temp_max=33.5,
                         source_updated_at=datetime.now(), fetched_at=datetime.now())

    row = db.query(WeatherData).filter(WeatherData.Region == "Hà Nội").one()
    assert row.SourceUpdatedAt == quan_trac, (
        "Dự báo đã xoá mốc quan trắc — tuổi dữ liệu sẽ luôn báo 0 phút"
    )
    assert row.Temperature == 30.5
    db.close()
