"""
Tra cây trồng phải về đúng hàng đang giữ dữ liệu.

Trong DB thật có hai hàng cùng là cà phê:

    CropID   3  'Cà phê'   tạo 10/06  — giữ 22 bản ghi giá
    CropID 107  'ca phe'   tạo 22/08  — rỗng

Hàng 107 sinh ra hồi bảng CropTypes còn lưu VARCHAR làm hỏng tiếng Việt:
'Cà phê' khi đó là chuỗi mojibake nên normalize_text không khớp được với
'ca phe', và ensure_crop tạo hàng mới. Sau khi sửa mã hoá, tên đã đúng lại
nhưng hàng rác vẫn còn — và ensure_crop khớp CHÍNH XÁC trước:

    crop = db.query(Crop).filter(Crop.CropName == crop_name).first()

nên gọi ensure_crop("ca phe") trả về 107 rỗng thay vì 3. Mọi truy vấn giá
cà phê bằng tên không dấu đều tra vào hàng không có dữ liệu.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.crop import CropType
from app.repositories.common import ensure_crop


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def test_uu_tien_hang_co_dau_khi_bi_trung(db):
    """Có cả 'Cà phê' và 'ca phe' thì phải chọn hàng chuẩn."""
    db.add(CropType(CropID=3, CropName="Cà phê"))
    db.add(CropType(CropID=107, CropName="ca phe"))
    db.commit()

    assert ensure_crop(db, "ca phe").CropID == 3, (
        "Tra vào hàng rác không dấu thay vì hàng đang giữ dữ liệu giá"
    )


def test_khong_tao_them_hang_khi_da_co_ban_co_dau(db):
    db.add(CropType(CropID=3, CropName="Cà phê"))
    db.commit()

    crop = ensure_crop(db, "ca phe")

    assert crop.CropID == 3
    assert db.query(CropType).count() == 1, "Đã tạo thêm hàng trùng"


def test_van_tao_moi_khi_that_su_chua_co(db):
    """Không siết nhầm: cây mới hoàn toàn vẫn phải được tạo."""
    db.add(CropType(CropID=3, CropName="Cà phê"))
    db.commit()

    crop = ensure_crop(db, "măng cụt")

    assert crop.CropID != 3
    assert db.query(CropType).count() == 2


def test_ten_co_dau_van_khop_chinh_no(db):
    db.add(CropType(CropID=3, CropName="Cà phê"))
    db.add(CropType(CropID=107, CropName="ca phe"))
    db.commit()

    assert ensure_crop(db, "Cà phê").CropID == 3
