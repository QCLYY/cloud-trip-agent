from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.auth_schemas import (
    CurrentUserResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from app.models.db_models import User
from app.services.auth_service import (
    DuplicateUsernameError,
    authenticate_user,
    create_user,
    create_user_access_token,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def _invalid_credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post(
    "/register",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    request: RegisterRequest,
    session: Session = Depends(get_db),
) -> User:
    """使用用户名和密码注册用户。"""
    try:
        return create_user(session, request.username, request.password)
    except DuplicateUsernameError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists.",
        ) from exc


@router.post("/login", response_model=TokenResponse)
def login_user(
    request: LoginRequest,
    session: Session = Depends(get_db),
) -> TokenResponse:
    """使用用户名和密码登录，成功时返回 Bearer Token。"""
    user = authenticate_user(session, request.username, request.password)
    if user is None:
        raise _invalid_credentials_exception()

    return TokenResponse(access_token=create_user_access_token(user))


@router.get("/me", response_model=CurrentUserResponse)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    """返回当前登录用户信息。"""
    return current_user
