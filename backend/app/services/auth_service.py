from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Base
from app.core.security import create_access_token, hash_password, verify_password
from app.models.db_models import User


class DuplicateUsernameError(Exception):
    """用户名已存在。"""


def _ensure_tables(session: Session) -> None:
    """在当前 session 绑定的数据库上创建缺失表。"""
    Base.metadata.create_all(bind=session.get_bind())


def _normalize_username(username: str) -> str:
    return username.strip()


def get_user_by_username(session: Session, username: str) -> User | None:
    """按用户名查询用户。"""
    _ensure_tables(session)
    normalized_username = _normalize_username(username)
    return (
        session.query(User)
        .filter(User.username == normalized_username)
        .first()
    )


def get_user_by_id(session: Session, user_id: int) -> User | None:
    """按稳定用户 ID 查询用户。"""
    _ensure_tables(session)
    return session.get(User, user_id)


def create_user(session: Session, username: str, password: str) -> User:
    """创建用户并保存密码哈希。"""
    _ensure_tables(session)
    normalized_username = _normalize_username(username)
    if get_user_by_username(session, normalized_username) is not None:
        raise DuplicateUsernameError

    user = User(
        username=normalized_username,
        password_hash=hash_password(password),
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DuplicateUsernameError from exc

    session.refresh(user)
    return user


def authenticate_user(
    session: Session,
    username: str,
    password: str,
) -> User | None:
    """用户名密码认证，失败时统一返回 None。"""
    user = get_user_by_username(session, username)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_user_access_token(user: User) -> str:
    """使用稳定用户 ID 作为 JWT subject。"""
    return create_access_token(subject=str(user.id))
