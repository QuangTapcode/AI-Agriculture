from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from unicodedata import normalize as uni_normalize
import unicodedata

from app.models.crop import Crop
from app.models.user import User


GRADE_API_TO_DB = {
    "grade_1": "Loại 1",
    "grade_2": "Loại 2",
    "grade_3": "Loại 3",
    "loai_1": "Loại 1",
    "loai_2": "Loại 2",
    "loai_3": "Loại 3",
    "loại 1": "Loại 1",
    "loại 2": "Loại 2",
    "loại 3": "Loại 3",
    "loai 1": "Loại 1",
    "loai 2": "Loại 2",
    "loai 3": "Loại 3",
}

GRADE_DB_TO_API = {
    "Loại 1": "grade_1",
    "Loại 2": "grade_2",
    "Loại 3": "grade_3",
    "Loai 1": "grade_1",
    "Loai 2": "grade_2",
    "Loai 3": "grade_3",
}

ALERT_API_TO_DB = {
    "above": "Trên",
    "below": "Dưới",
    "change": "Thay đổi",
    "Tren": "Trên",
    "Duoi": "Dưới",
    "Thay doi": "Thay đổi",
    "Trên": "Trên",
    "Dưới": "Dưới",
    "Thay đổi": "Thay đổi",
}

ALERT_DB_TO_API = {
    "Tren": "above",
    "Duoi": "below",
    "Thay doi": "change",
    "Trên": "above",
    "Dưới": "below",
    "Thay đổi": "change",
}

CHANNEL_API_TO_DB = {
    "retail": "Thương lái",
    "wholesale": "Chợ đầu mối",
    "supermarket": "Chợ đầu mối",
    "processor": "Thương lái",
    "export": "Xuất khẩu",
}


def to_db_grade(value: str | None) -> str:
    if not value:
        return "Loai 1"
    return GRADE_API_TO_DB.get(value.strip().lower(), value)


def to_api_grade(value: str | None) -> str:
    if not value:
        return "grade_1"
    return GRADE_DB_TO_API.get(value, value)


def to_db_alert_condition(value: str | None) -> str:
    if not value:
        return "Trên"
    return ALERT_API_TO_DB.get(value, value)


def to_api_alert_condition(value: str | None) -> str:
    if not value:
        return "above"
    return ALERT_DB_TO_API.get(value, value)


def to_db_channel(value: str | None) -> str:
    if not value:
        return "Thương lái"
    return CHANNEL_API_TO_DB.get(value, value)


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return " ".join(text.replace("đ", "d").replace("Đ", "d").split())


def ensure_crop(db: Session, crop_name: str) -> Crop:
    try:
        normalized = normalize_text(crop_name)
        crops = db.query(Crop).order_by(Crop.CropID).all()
        ung_vien = [c for c in crops if normalize_text(c.CropName) == normalized]
        if ung_vien:
            # Khớp chính xác TRƯỚC là sai khi DB có hàng trùng không dấu. Thời
            # CropTypes còn lưu VARCHAR, 'Cà phê' bị hỏng thành mojibake nên
            # ensure_crop("ca phe") không nhận ra và tạo hàng mới (CropID 107).
            # Sau khi sửa mã hoá, hàng rác vẫn thắng ở nhánh khớp chính xác và
            # mọi truy vấn giá cà phê không dấu tra vào hàng rỗng.
            #
            # CropID nhỏ nhất là hàng gốc từ script khởi tạo — cũng là hàng
            # đang giữ dữ liệu giá và được các bảng khác tham chiếu.
            trung_khop = next((c for c in ung_vien if c.CropName == crop_name), None)
            return min(ung_vien, key=lambda c: c.CropID) if len(ung_vien) > 1 else (
                trung_khop or ung_vien[0]
            )
        crop = Crop(
            CropName=crop_name,
            Category="Khác",
            GrowthDurationDays=70,
            TypicalPriceMin=10000,
            TypicalPriceMax=30000,
        )
        db.add(crop)
        db.commit()
        db.refresh(crop)
        return crop
    except SQLAlchemyError:
        db.rollback()
        crop = Crop(CropName=crop_name, Category="Khác", GrowthDurationDays=70)
        crop.CropID = 1
        return crop


def ensure_user(db: Session, receiver: str | None = None, region: str | None = None) -> User:
    try:
        query = db.query(User)
        if receiver:
            query = query.filter(
                or_(
                    User.Email == receiver,
                    User.PhoneNumber == receiver,
                    User.ZaloID == receiver,
                )
            )
            user = query.first()
            if user:
                return user
        if not receiver:
            user = db.query(User).order_by(User.UserID).first()
            if user:
                return user
        user = User(
            FullName="API User",
            Email=receiver if receiver and "@" in receiver else None,
            PhoneNumber=receiver if receiver and "@" not in receiver else None,
            PasswordHash="mock-password",
            Role="farmer",
            Region=region,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except SQLAlchemyError:
        db.rollback()
        user = User(
            FullName="API User",
            Email=receiver if receiver and "@" in receiver else None,
            PhoneNumber=receiver if receiver and "@" not in receiver else None,
            PasswordHash="mock-password",
            Role="farmer",
            Region=region,
        )
        user.UserID = 1
        return user
