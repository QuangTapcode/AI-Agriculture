"""
Cảnh báo giá: kiểm tra kĩ từng nhánh quyết định.

Cảnh báo giá là thứ nông dân dựa vào để quyết định bán. Sai một lần là mất
tiền thật, nên mỗi nhánh dưới đây đều phải chốt bằng test:

  1. Ngưỡng "above" chỉ bắn khi giá >= ngưỡng, "below" khi giá <= ngưỡng.
  2. Đúng bằng ngưỡng cũng tính là chạm.
  3. Cooldown 30 phút chặn bắn lặp.
  4. Cảnh báo đã tắt không bắn.
  5. Không lẫn giá của vùng khác hay cây khác.
  6. KHÔNG bắn theo giá đã quá hạn — _current_price_for_alert lấy hàng
     MarketPrices mới nhất mà không hề xét tuổi. Giá trong DB hiện cũ 13 ngày;
     bắn "cà phê vừa vượt 95.000" dựa trên số đo hai tuần trước là sai lệch
     nguy hiểm nhất trong nhóm này.
"""
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.alert import PriceAlert
from app.models.crop import CropType
from app.models.user import User
from app.models.price import MarketPrice
from app.repositories.common import ALERT_API_TO_DB
from app.services.alert_service import alert_service

NGUONG = 95000.0


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add(User(UserID=1, FullName="Nông dân", Email="a@b.c", PasswordHash="x"))
    s.add(CropType(CropID=1, CropName="Cà phê"))
    s.commit()
    yield s
    s.close()


def _gia(db, *, gia, vung="Đắk Lắk", crop_id=1, tuoi_gio=0.0):
    luc = datetime.now() - timedelta(hours=tuoi_gio)
    db.add(MarketPrice(CropID=crop_id, Region=vung, PricePerKg=gia,
                       PriceDate=luc.date(), UpdatedAt=luc, FetchedAt=luc,
                       SourceName="Thông tin thị trường nông sản"))
    db.commit()


def _canh_bao(db, *, loai="above", nguong=NGUONG, vung="Đắk Lắk",
              crop_id=1, bat=True, lan_cuoi=None):
    a = PriceAlert(UserID=1, CropID=crop_id, Region=vung, TargetPrice=nguong,
                   AlertType=ALERT_API_TO_DB[loai], IsActive=bat,
                   LastTriggered=lan_cuoi, NotifyMethod="app")
    db.add(a)
    db.commit()
    return a


# ── Ngưỡng ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("gia,loai,mong_doi", [
    (96000.0, "above", True),   # vượt ngưỡng
    (94000.0, "above", False),  # chưa tới
    (95000.0, "above", True),   # đúng bằng ngưỡng
    (94000.0, "below", True),   # rơi xuống dưới
    (96000.0, "below", False),  # còn cao
    (95000.0, "below", True),   # đúng bằng ngưỡng
])
def test_nguong_bat_dung_chieu(db, gia, loai, mong_doi):
    _gia(db, gia=gia)
    a = _canh_bao(db, loai=loai)

    kq = alert_service._evaluate_alert(db, a)

    assert (kq is not None) is mong_doi, (
        f"giá {gia:,.0f} với ngưỡng {loai} {NGUONG:,.0f} — "
        f"{'phải bắn' if mong_doi else 'không được bắn'}"
    )


# ── Chống bắn lặp ───────────────────────────────────────────────────────────

def test_cooldown_chan_ban_lap(db):
    _gia(db, gia=96000.0)
    a = _canh_bao(db, lan_cuoi=datetime.now() - timedelta(minutes=5))

    assert alert_service._evaluate_alert(db, a) is None


def test_het_cooldown_thi_ban_lai(db):
    _gia(db, gia=96000.0)
    a = _canh_bao(db, lan_cuoi=datetime.now() - timedelta(minutes=45))

    assert alert_service._evaluate_alert(db, a) is not None


# ── Không lẫn dữ liệu ───────────────────────────────────────────────────────

def test_khong_lay_gia_cay_khac(db):
    db.add(CropType(CropID=2, CropName="Hồ tiêu"))
    db.commit()
    _gia(db, gia=96000.0, crop_id=2)      # tiêu vượt ngưỡng
    a = _canh_bao(db, crop_id=1)          # cảnh báo cho cà phê

    assert alert_service._evaluate_alert(db, a) is None, "Bắn cảnh báo cà phê bằng giá hồ tiêu"


def test_khong_lay_gia_vung_khac_khi_vung_minh_co_gia(db):
    _gia(db, gia=90000.0, vung="Đắk Lắk")
    _gia(db, gia=99000.0, vung="Gia Lai")
    a = _canh_bao(db, vung="Đắk Lắk")

    assert alert_service._evaluate_alert(db, a) is None, "Dùng giá Gia Lai cho cảnh báo Đắk Lắk"


# ── Tuổi dữ liệu ────────────────────────────────────────────────────────────

def test_khong_ban_theo_gia_qua_han(db):
    """Giá cũ 13 ngày không phải căn cứ để báo 'vừa vượt ngưỡng'."""
    _gia(db, gia=96000.0, tuoi_gio=13 * 24)
    a = _canh_bao(db)

    assert alert_service._evaluate_alert(db, a) is None, (
        "Bắn cảnh báo dựa trên giá đã 13 ngày tuổi"
    )


def test_gia_moi_van_ban_binh_thuong(db):
    """Không siết nhầm: giá trong ngày vẫn phải bắn."""
    _gia(db, gia=96000.0, tuoi_gio=2.0)
    a = _canh_bao(db)

    assert alert_service._evaluate_alert(db, a) is not None
