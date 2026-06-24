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


TEST_PASSWORD = "test_password"


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "memory_api_test.db"
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
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def register_and_login(client: TestClient, username: str) -> str:
    register_response = client.post(
        "/auth/register",
        json={"username": username, "password": TEST_PASSWORD},
    )
    assert register_response.status_code == 201
    login_response = client.post(
        "/auth/login",
        json={"username": username, "password": TEST_PASSWORD},
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]


def build_generate_payload() -> dict:
    return {
        "destination": "大理",
        "start_date": "2026-04-10",
        "end_date": "2026-04-11",
        "travelers": 2,
        "budget": 3200,
        "preferences": ["自然风景", "拍照"],
        "pace": "轻松",
        "dietary_preferences": ["少辣"],
        "hotel_level": "舒适型",
        "special_notes": "我喜欢古镇和清淡饮食",
    }


def test_memory_default_disabled_and_requires_auth(client: TestClient) -> None:
    response = client.get("/memory")
    assert response.status_code == 401

    token = register_and_login(client, "memory_user")
    client.headers.update({"Authorization": f"Bearer {token}"})

    response = client.get("/memory")
    assert response.status_code == 200
    assert response.json() == {"enabled": False, "items": []}


def test_enabled_memory_saves_explicit_preferences(client: TestClient) -> None:
    token = register_and_login(client, "memory_enabled_user")
    client.headers.update({"Authorization": f"Bearer {token}"})

    setting_response = client.put("/memory", json={"enabled": True})
    assert setting_response.status_code == 200
    assert setting_response.json()["enabled"] is True

    generate_response = client.post("/trip/generate", json=build_generate_payload())
    assert generate_response.status_code == 200

    memory_response = client.get("/memory")
    assert memory_response.status_code == 200
    data = memory_response.json()
    contents = {item["content"] for item in data["items"]}

    assert "自然风景" in contents
    assert "拍照" in contents
    assert "少辣" in contents
    assert "轻松" in contents
    assert "舒适型" in contents
    assert "我喜欢古镇和清淡饮食" in contents


def test_disabled_memory_does_not_save_new_items(client: TestClient) -> None:
    token = register_and_login(client, "memory_disabled_user")
    client.headers.update({"Authorization": f"Bearer {token}"})

    response = client.post("/trip/generate", json=build_generate_payload())
    assert response.status_code == 200

    memory_response = client.get("/memory")
    assert memory_response.status_code == 200
    assert memory_response.json() == {"enabled": False, "items": []}


def test_memory_delete_and_clear(client: TestClient) -> None:
    token = register_and_login(client, "memory_delete_user")
    client.headers.update({"Authorization": f"Bearer {token}"})
    client.put("/memory", json={"enabled": True})
    client.post("/trip/generate", json=build_generate_payload())

    data = client.get("/memory").json()
    first_id = data["items"][0]["id"]

    delete_response = client.delete(f"/memory/{first_id}")
    assert delete_response.status_code == 200

    clear_response = client.delete("/memory")
    assert clear_response.status_code == 200
    assert clear_response.json()["deleted_count"] >= 1
    assert client.get("/memory").json()["items"] == []
