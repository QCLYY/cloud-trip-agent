from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


USERNAME_MAX_LENGTH = 50
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 72


class AuthCredentials(BaseModel):
    """注册和登录共用的用户名密码请求体。"""

    username: str = Field(
        ...,
        min_length=1,
        max_length=USERNAME_MAX_LENGTH,
        description="用户名",
    )
    password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        description="密码",
    )

    @field_validator("username", mode="before")
    @classmethod
    def strip_username(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("username")
    @classmethod
    def username_must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("username must not be empty")
        return value

    @field_validator("password")
    @classmethod
    def password_must_fit_bcrypt_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > PASSWORD_MAX_LENGTH:
            raise ValueError("password must not exceed 72 bytes")
        return value


class RegisterRequest(AuthCredentials):
    """用户注册请求。"""


class LoginRequest(AuthCredentials):
    """用户登录请求。"""


class TokenResponse(BaseModel):
    """登录成功后返回的访问令牌。"""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")


class CurrentUserResponse(BaseModel):
    """当前用户响应，不包含密码或密码哈希。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="用户 ID")
    username: str = Field(..., description="用户名")
    created_at: datetime = Field(..., description="创建时间")
