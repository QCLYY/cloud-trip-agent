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
from app.models.db_models import TripRecord  # noqa: E402
from app.models.schemas import TripRequest  # noqa: E402
from app.services.trip_service import generate_trip_itinerary  # noqa: E402


TEST_PASSWORD = "test_password"


@pytest.fixture()
def isolated_client(tmp_path):
    db_path = tmp_path / "user_isolation_test.db"
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


def register_and_login(client: TestClient, username: str) -> tuple[dict[str, str], int]:
    register_response = client.post(
        "/auth/register",
        json={"username": username, "password": TEST_PASSWORD},
    )
    assert register_response.status_code == 201
    user_id = register_response.json()["id"]

    login_response = client.post(
        "/auth/login",
        json={"username": username, "password": TEST_PASSWORD},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, user_id


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


def build_valid_save_payload() -> dict:
    itinerary = generate_trip_itinerary(TripRequest(**build_generate_payload()))
    itinerary_data = itinerary.model_dump(mode="json")
    return {
        "trip_id": itinerary_data["trip_id"],
        "itinerary": itinerary_data,
        "user_id": "frontend_demo_user",
    }


def save_trip_for_user(client: TestClient, headers: dict[str, str]) -> str:
    generated_response = client.post(
        "/trip/generate",
        json=build_generate_payload(),
        headers=headers,
    )
    assert generated_response.status_code == 200
    itinerary = generated_response.json()

    save_response = client.post(
        "/trip/save",
        json={
            "trip_id": itinerary["trip_id"],
            "itinerary": itinerary,
            "user_id": "frontend_demo_user",
        },
        headers=headers,
    )
    assert save_response.status_code == 200
    return save_response.json()["trip_id"]


def test_user_a_can_save_and_view_own_trip(isolated_client) -> None:
    client, _ = isolated_client
    user_a_headers, _ = register_and_login(client, "user_a")

    trip_id = save_trip_for_user(client, user_a_headers)
    response = client.get(f"/trip/{trip_id}", headers=user_a_headers)

    assert response.status_code == 200
    assert response.json()["trip_id"] == trip_id


def test_other_user_cannot_view_delete_or_export_trip(isolated_client) -> None:
    client, _ = isolated_client
    user_a_headers, _ = register_and_login(client, "user_a")
    user_b_headers, _ = register_and_login(client, "user_b")

    trip_id = save_trip_for_user(client, user_a_headers)

    view_response = client.get(f"/trip/{trip_id}", headers=user_b_headers)
    delete_response = client.delete(f"/trip/{trip_id}", headers=user_b_headers)
    export_response = client.get(
        f"/export/{trip_id}/markdown",
        headers=user_b_headers,
    )
    owner_response = client.get(f"/trip/{trip_id}", headers=user_a_headers)

    assert view_response.status_code == 404
    assert delete_response.status_code == 404
    assert export_response.status_code == 404
    assert owner_response.status_code == 200


def test_other_user_cannot_access_or_restore_trip_versions(isolated_client) -> None:
    client, _ = isolated_client
    user_a_headers, _ = register_and_login(client, "user_a")
    user_b_headers, _ = register_and_login(client, "user_b")

    trip_id = save_trip_for_user(client, user_a_headers)

    owner_versions = client.get(f"/trip/{trip_id}/versions", headers=user_a_headers)
    other_versions = client.get(f"/trip/{trip_id}/versions", headers=user_b_headers)
    other_version_detail = client.get(f"/trip/{trip_id}/versions/1", headers=user_b_headers)
    other_compare = client.get(
        f"/trip/{trip_id}/versions/compare?from_version=1&to_version=1",
        headers=user_b_headers,
    )
    other_restore = client.post(f"/trip/{trip_id}/versions/1/restore", headers=user_b_headers)

    assert owner_versions.status_code == 200
    assert owner_versions.json()["total"] == 1
    assert other_versions.status_code == 200
    assert other_versions.json()["total"] == 0
    assert other_version_detail.status_code == 404
    assert other_compare.status_code == 404
    assert other_restore.status_code == 404


def test_protected_trip_routes_require_token(isolated_client) -> None:
    client, _ = isolated_client
    save_payload = build_valid_save_payload()

    responses = [
        client.get("/trip"),
        client.post("/trip/generate", json=build_generate_payload()),
        client.post("/trip/save", json=save_payload),
        client.get("/trip/trip_missing"),
        client.delete("/trip/trip_missing"),
        client.get("/export/trip_missing/markdown"),
    ]

    assert all(response.status_code == 401 for response in responses)
    assert all(response.headers["www-authenticate"] == "Bearer" for response in responses)


def test_health_remains_public(isolated_client) -> None:
    client, _ = isolated_client

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_save_ignores_frontend_user_id_and_uses_token_user(isolated_client) -> None:
    client, testing_session_local = isolated_client
    user_a_headers, user_a_id = register_and_login(client, "user_a")

    trip_id = save_trip_for_user(client, user_a_headers)

    session = testing_session_local()
    try:
        record = session.query(TripRecord).filter(TripRecord.trip_id == trip_id).one()
        assert record.user_id == user_a_id
    finally:
        session.close()


def test_same_generated_trip_id_can_be_saved_by_different_users(isolated_client) -> None:
    client, _ = isolated_client
    user_a_headers, _ = register_and_login(client, "user_a")
    user_b_headers, _ = register_and_login(client, "user_b")

    user_a_trip_id = save_trip_for_user(client, user_a_headers)
    user_b_trip_id = save_trip_for_user(client, user_b_headers)

    assert user_b_trip_id != user_a_trip_id
    assert client.get(f"/trip/{user_a_trip_id}", headers=user_a_headers).status_code == 200
    assert client.get(f"/trip/{user_b_trip_id}", headers=user_b_headers).status_code == 200
    assert client.get(f"/trip/{user_a_trip_id}", headers=user_b_headers).status_code == 404
