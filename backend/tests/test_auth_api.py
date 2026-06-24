from datetime import timedelta
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.dependencies import get_db  # noqa: E402
from app.api.main import app  # noqa: E402
from app.config import Base  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.models.db_models import User  # noqa: E402


@pytest.fixture()
def auth_client(tmp_path):
    """使用独立 SQLite 测试库，避免污染正式运行数据。"""
    db_path = tmp_path / "auth_test.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        session = testing_session_local()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client, testing_session_local
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def register_user(client: TestClient, username: str = "test_user", password: str = "test_password"):
    return client.post(
        "/auth/register",
        json={
            "username": username,
            "password": password,
        },
    )


def login_user(client: TestClient, username: str = "test_user", password: str = "test_password"):
    return client.post(
        "/auth/login",
        json={
            "username": username,
            "password": password,
        },
    )


def build_generate_payload() -> dict:
    return {
        "destination": "大理",
        "start_date": "2026-04-10",
        "end_date": "2026-04-12",
        "travelers": 2,
        "budget": 3200,
        "preferences": ["自然风景", "拍照", "美食"],
        "pace": "轻松",
        "dietary_preferences": ["少辣"],
        "hotel_level": "舒适型",
        "special_notes": "不想太早起床，希望安排一个适合看日落的地点",
    }


def test_register_user_success(auth_client) -> None:
    client, _ = auth_client

    response = register_user(client, username="  test_user  ")

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "test_user"
    assert "id" in data
    assert "created_at" in data
    assert "password" not in data
    assert "password_hash" not in data


def test_register_duplicate_username_returns_409(auth_client) -> None:
    client, _ = auth_client
    register_user(client)

    response = register_user(client)

    assert response.status_code == 409
    assert response.json()["detail"] == "Username already exists."


def test_register_rejects_blank_username_after_strip(auth_client) -> None:
    client, _ = auth_client

    response = register_user(client, username="   ")

    assert response.status_code == 422


def test_register_rejects_password_over_bcrypt_byte_limit(auth_client) -> None:
    client, _ = auth_client
    overlong_password = "a" * 73

    response = register_user(client, password=overlong_password)

    assert response.status_code == 422
    assert overlong_password not in response.text


def test_registered_password_is_not_stored_as_plaintext(auth_client) -> None:
    client, testing_session_local = auth_client
    plain_password = "test_password"

    register_user(client, password=plain_password)

    session = testing_session_local()
    try:
        user = session.query(User).filter(User.username == "test_user").one()
        assert user.password_hash != plain_password
        assert plain_password not in user.password_hash
    finally:
        session.close()


def test_login_with_correct_password_returns_token(auth_client) -> None:
    client, _ = auth_client
    register_user(client)

    response = login_user(client)

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert data["access_token"]


def test_login_with_wrong_password_returns_401(auth_client) -> None:
    client, _ = auth_client
    register_user(client)

    response = login_user(client, password="wrong_password")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."
    assert "Traceback" not in response.text


def test_login_with_unknown_username_returns_same_401(auth_client) -> None:
    client, _ = auth_client

    response = login_user(client, username="missing_user", password="wrong_password")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."
    assert "missing_user" not in response.text
    assert "Traceback" not in response.text


def test_auth_me_returns_current_user_with_valid_token(auth_client) -> None:
    client, _ = auth_client
    register_user(client)
    token = login_user(client).json()["access_token"]

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "test_user"
    assert "id" in data
    assert "created_at" in data
    assert "password" not in data
    assert "password_hash" not in data


def test_auth_me_without_token_returns_401(auth_client) -> None:
    client, _ = auth_client

    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_auth_me_with_invalid_token_returns_401(auth_client) -> None:
    client, _ = auth_client

    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid.token.value"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_auth_me_with_expired_token_returns_401(auth_client) -> None:
    client, _ = auth_client
    expired_token = create_access_token(
        subject="1",
        expires_delta=timedelta(minutes=-1),
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_health_still_returns_ok(auth_client) -> None:
    client, _ = auth_client

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_trip_generate_requires_authentication(auth_client) -> None:
    client, _ = auth_client

    response = client.post("/trip/generate", json=build_generate_payload())

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
