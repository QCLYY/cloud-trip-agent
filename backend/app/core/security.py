from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import (
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
)


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenValidationError(Exception):
    """访问令牌无效或已过期。"""


def hash_password(password: str) -> str:
    """返回安全哈希后的密码。"""
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码是否匹配哈希。"""
    return password_context.verify(password, password_hash)


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    """创建包含稳定 subject 和过期时间的 JWT。"""
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(subject),
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    """解析 JWT 并返回 subject。"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise TokenValidationError("invalid token") from exc

    subject = payload.get("sub")
    if not subject:
        raise TokenValidationError("missing subject")
    return str(subject)
