import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ContactRequestCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=30)
    topic: Literal["account", "service", "technical", "data", "other"]
    message: str = Field(min_length=10, max_length=2000)
    website: str = Field(default="", max_length=200)

    @field_validator("name", "message", mode="before")
    @classmethod
    def strip_required_text(cls, value):
        return str(value or "").strip()

    @field_validator("email", "phone", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        text = str(value or "").strip()
        return text or None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Email không hợp lệ")
        return value.lower() if value else None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value):
        if value and not re.fullmatch(r"[+()0-9.\-\s]{8,30}", value):
            raise ValueError("Số điện thoại không hợp lệ")
        return value

    @model_validator(mode="after")
    def validate_contact_and_honeypot(self):
        if self.website.strip():
            raise ValueError("Dữ liệu không hợp lệ")
        if not self.email and not self.phone:
            raise ValueError("Cần cung cấp email hoặc số điện thoại")
        return self
