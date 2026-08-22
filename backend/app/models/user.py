from sqlalchemy import Boolean, Column, DateTime, Integer, Unicode
from sqlalchemy.orm import synonym
from sqlalchemy.sql import func

from ..core.database import Base


class User(Base):
    __tablename__ = "Users"

    UserID = Column("UserID", Integer, primary_key=True, index=True)
    FullName = Column("FullName", Unicode(100), nullable=False)
    Email = Column("Email", Unicode(100), unique=True, nullable=True)
    PhoneNumber = Column("PhoneNumber", Unicode(20), nullable=True)
    ZaloID = Column("ZaloID", Unicode(100), nullable=True)
    PasswordHash = Column("PasswordHash", Unicode(255), nullable=False, default="")
    Role = Column("Role", Unicode(20), nullable=False, default="farmer")
    Region = Column("Region", Unicode(100), nullable=True)
    IsActive = Column("IsActive", Boolean, nullable=False, default=True)
    IsVerified = Column("IsVerified", Boolean, nullable=False, default=False)
    CreatedAt = Column("CreatedAt", DateTime, server_default=func.now(), nullable=False)
    UpdatedAt = Column("UpdatedAt", DateTime, server_default=func.now(), nullable=False)

    id = synonym("UserID")
    full_name = synonym("FullName")
    email = synonym("Email")
    phone_number = synonym("PhoneNumber")
    zalo_id = synonym("ZaloID")
    password_hash = synonym("PasswordHash")
    role = synonym("Role")
    region = synonym("Region")
    is_active = synonym("IsActive")
    is_verified = synonym("IsVerified")
    created_at = synonym("CreatedAt")
    updated_at = synonym("UpdatedAt")
