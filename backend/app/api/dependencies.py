from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import SessionLocal
from app.core.security import TokenValidationError, decode_access_token
from app.models.db_models import User
from app.services.auth_service import get_user_by_id


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db() -> Generator[Session, None, None]:
    """提供数据库 session。"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_db),
) -> User:
    """从 Bearer Token 解析并返回当前用户。"""
    try:
        subject = decode_access_token(token)
        user_id = int(subject)
    except (TokenValidationError, ValueError) as exc:
        raise _credentials_exception() from exc

    user = get_user_by_id(session, user_id)
    if user is None:
        raise _credentials_exception()
    return user
