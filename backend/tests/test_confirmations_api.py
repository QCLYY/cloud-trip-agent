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
    db_path = tmp_path / "confirmations_test.db"
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
    assert client.post(
        "/auth/register",
        json={"username": username, "password": TEST_PASSWORD},
    ).status_code == 201
    response = client.post(
        "/auth/login",
        json={"username": username, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_create_list_and_confirm_allowed_confirmation(client: TestClient) -> None:
    token = register_and_login(client, "confirm_user")
    client.headers.update({"Authorization": f"Bearer {token}"})

    create_response = client.post(
        "/confirmations",
        json={
            "trip_id": "trip_demo",
            "confirmation_type": "restore_version",
            "payload": {"version_number": 1},
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["status"] == "pending"

    list_response = client.get("/confirmations", params={"trip_id": "trip_demo"})
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    confirm_response = client.post(
        f"/confirmations/{created['id']}",
        json={"action": "confirmed"},
    )
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "confirmed"


def test_confirmation_rejects_disallowed_type_and_action(client: TestClient) -> None:
    token = register_and_login(client, "confirm_reject_user")
    client.headers.update({"Authorization": f"Bearer {token}"})

    bad_type_response = client.post(
        "/confirmations",
        json={
            "trip_id": "trip_demo",
            "confirmation_type": "book_ticket",
            "payload": {},
        },
    )
    assert bad_type_response.status_code == 422

    create_response = client.post(
        "/confirmations",
        json={
            "confirmation_type": "budget_over_limit",
            "payload": {"over_by": 100},
        },
    )
    confirmation_id = create_response.json()["id"]
    bad_action_response = client.post(
        f"/confirmations/{confirmation_id}",
        json={"action": "paid"},
    )
    assert bad_action_response.status_code == 422


def test_confirmation_is_user_isolated(client: TestClient) -> None:
    token_one = register_and_login(client, "confirm_owner")
    client.headers.update({"Authorization": f"Bearer {token_one}"})
    create_response = client.post(
        "/confirmations",
        json={
            "confirmation_type": "lock_item",
            "payload": {"item_id": "day_1_spot_1"},
        },
    )
    confirmation_id = create_response.json()["id"]

    token_two = register_and_login(client, "confirm_other")
    client.headers.update({"Authorization": f"Bearer {token_two}"})

    assert client.get("/confirmations").json()["total"] == 0
    response = client.post(
        f"/confirmations/{confirmation_id}",
        json={"action": "confirmed"},
    )
    assert response.status_code == 404
