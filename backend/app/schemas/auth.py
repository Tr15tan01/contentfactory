from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.validators import iana_timezone


class AuthConfigOut(BaseModel):
    google_enabled: bool
    email_verification_required: bool
    password_min_length: int


class CsrfOut(BaseModel):
    csrf_token: str


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    full_name: str | None = Field(default=None, max_length=120)


class RegisterOut(BaseModel):
    verification_required: bool
    user: UserOut | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class EmailIn(BaseModel):
    email: EmailStr


class TokenIn(BaseModel):
    token: str = Field(min_length=16, max_length=256)


class ResetPasswordIn(TokenIn):
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordIn(BaseModel):
    current_password: str | None = Field(default=None, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class DeleteAccountIn(BaseModel):
    password: str | None = Field(default=None, max_length=256)
    confirm_email: EmailStr | None = None


class UpdateProfileIn(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    timezone: str | None = Field(default=None, max_length=64)

    _tz = field_validator("timezone")(iana_timezone)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None
    avatar_url: str | None
    email_verified: bool
    has_password: bool
    is_superuser: bool
    timezone: str
    created_at: datetime


class SessionOut(BaseModel):
    id: uuid.UUID
    user_agent: str | None
    ip_address: str | None
    auth_method: str
    created_at: datetime
    last_used_at: datetime
    current: bool
