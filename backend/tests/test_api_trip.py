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
import app.api.routes.export as export_route  # noqa: E402
import app.services.trip_service as trip_service  # noqa: E402


TEST_PASSWORD = "test_password"


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "trip_api_test.db"
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
            token = register_and_login(test_client, "trip_api_user")
            test_client.headers.update({"Authorization": f"Bearer {token}"})
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
        "end_date": "2026-04-12",
        "travelers": 2,
        "budget": 3200,
        "preferences": ["自然风景", "拍照", "美食"],
        "pace": "轻松",
        "dietary_preferences": ["少辣"],
        "hotel_level": "舒适型",
        "special_notes": "不想太早起床，希望安排一个适合看日落的地点",
    }


def save_generated_itinerary(client: TestClient) -> dict:
    generated_response = client.post("/trip/generate", json=build_generate_payload())
    assert generated_response.status_code == 200
    generated_itinerary = generated_response.json()

    save_response = client.post(
        "/trip/save",
        json={
            "trip_id": generated_itinerary["trip_id"],
            "itinerary": generated_itinerary,
            "user_id": "frontend_demo_user",
        },
    )
    assert save_response.status_code == 200
    generated_itinerary["saved_trip_id"] = save_response.json()["trip_id"]
    return generated_itinerary


def test_generate_trip_returns_itinerary_successfully(client: TestClient) -> None:
    response = client.post("/trip/generate", json=build_generate_payload())

    assert response.status_code == 200
    data = response.json()
    assert data["destination"] == "大理"
    assert "trip_id" in data
    assert "summary" in data
    assert "days" in data
    assert isinstance(data["days"], list)
    assert len(data["days"]) == 3
    assert "budget_breakdown" in data
    assert data["budget_breakdown"]["total"] >= 0
    assert data["budget_breakdown"]["source_type"] == "estimate"
    assert data["days"][0]["spots"][0]["source_type"] in {"estimate", "official_api"}
    assert data["days"][0]["spots"][0]["cost_source_type"] == "estimate"
    assert data["source_records"]
    assert len(data["candidate_itineraries"]) == 3
    candidate_ids = {candidate["candidate_id"] for candidate in data["candidate_itineraries"]}
    assert candidate_ids == {"economy", "balanced", "experience"}
    economy = next(candidate for candidate in data["candidate_itineraries"] if candidate["candidate_id"] == "economy")
    balanced = next(candidate for candidate in data["candidate_itineraries"] if candidate["candidate_id"] == "balanced")
    assert economy["estimated_budget"] <= balanced["estimated_budget"]
    assert economy["days"][0]["transport"][0]["mode"] != balanced["days"][0]["transport"][0]["mode"]
    assert economy["days"][0]["hotel"]["level"] != balanced["days"][0]["hotel"]["level"]
    assert len(economy["differences"]) >= 2


def test_generate_trip_rejects_invalid_request(client: TestClient) -> None:
    payload = build_generate_payload()
    payload["travelers"] = 0

    response = client.post("/trip/generate", json=payload)

    assert response.status_code == 422


def test_root_endpoint_returns_running_message(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "Trip Planner Demo backend is running."}


def test_health_endpoint_returns_ok_status(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_edit_trip_returns_updated_itinerary_successfully(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        trip_service,
        "generate_day_edit_draft",
        lambda request, target_day: (
            None,
            {"prompt_tokens": 0, "completion_tokens": 0},
        ),
    )

    generated_response = client.post("/trip/generate", json=build_generate_payload())
    generated_itinerary = generated_response.json()

    edit_payload = {
        "trip_id": generated_itinerary["trip_id"],
        "current_itinerary": generated_itinerary,
        "user_instruction": "第二天改得更轻松一点",
        "edit_scope": "day_2",
        "preserve_constraints": ["保留预算结构"],
    }

    response = client.post("/trip/edit", json=edit_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["trip_id"] == generated_itinerary["trip_id"]
    assert data["days"][1]["theme"].endswith("（已调整为更轻松）")


def test_edit_trip_rejects_invalid_request(client: TestClient) -> None:
    response = client.post(
        "/trip/edit",
        json={
            "trip_id": "trip_demo",
            "user_instruction": "第二天轻松一点",
        },
    )

    assert response.status_code == 422


def test_save_trip_returns_trip_id_successfully(client: TestClient) -> None:
    generated_itinerary = save_generated_itinerary(client)

    assert generated_itinerary["saved_trip_id"] == generated_itinerary["trip_id"]


def test_get_trip_detail_returns_saved_itinerary(client: TestClient) -> None:
    generated_itinerary = save_generated_itinerary(client)

    response = client.get(f"/trip/{generated_itinerary['saved_trip_id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["trip_id"] == generated_itinerary["saved_trip_id"]
    assert data["itinerary"]["destination"] == "大理"


def test_get_trip_detail_returns_404_for_missing_trip(client: TestClient) -> None:
    response = client.get("/trip/trip_not_exists")

    assert response.status_code == 404


def test_trip_version_routes_and_edit_version_creation(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        trip_service,
        "generate_day_edit_draft",
        lambda request, target_day: (
            None,
            {"prompt_tokens": 0, "completion_tokens": 0},
        ),
    )
    generated_itinerary = save_generated_itinerary(client)
    saved_trip_id = generated_itinerary["saved_trip_id"]

    edit_payload = {
        "trip_id": saved_trip_id,
        "current_itinerary": {**generated_itinerary, "trip_id": saved_trip_id},
        "user_instruction": "第二天改得更轻松一点",
        "edit_scope": "day_2",
        "preserve_constraints": ["保留预算结构"],
    }
    edit_response = client.post("/trip/edit", json=edit_payload)
    assert edit_response.status_code == 200

    list_response = client.get(f"/trip/{saved_trip_id}/versions")
    assert list_response.status_code == 200
    versions = list_response.json()
    assert versions["total"] == 2
    assert [item["version_number"] for item in versions["items"]] == [2, 1]

    detail_response = client.get(f"/trip/{saved_trip_id}/versions/1")
    assert detail_response.status_code == 200
    assert detail_response.json()["version_number"] == 1

    compare_response = client.get(
        f"/trip/{saved_trip_id}/versions/compare",
        params={"from_version": 1, "to_version": 2},
    )
    assert compare_response.status_code == 200
    assert compare_response.json()["differences"]

    restore_response = client.post(f"/trip/{saved_trip_id}/versions/1/restore")
    assert restore_response.status_code == 200
    restored = restore_response.json()
    assert restored["restored_from_version"] == 1
    assert restored["new_version_number"] == 3


def test_list_trips_returns_saved_trip_summaries(client: TestClient) -> None:
    generated_itinerary = save_generated_itinerary(client)

    response = client.get("/trip")

    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)
    assert any(
        item["trip_id"] == generated_itinerary["saved_trip_id"]
        for item in data["items"]
    )


def test_export_trip_markdown_returns_markdown_text(client: TestClient) -> None:
    generated_itinerary = save_generated_itinerary(client)

    response = client.get(f"/export/{generated_itinerary['saved_trip_id']}/markdown")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert generated_itinerary["destination"] in response.text
    assert generated_itinerary["summary"] in response.text


def test_export_trip_pdf_returns_pdf_bytes(
    client: TestClient,
    monkeypatch,
) -> None:
    generated_itinerary = save_generated_itinerary(client)

    monkeypatch.setattr(
        export_route,
        "itinerary_to_pdf_bytes",
        lambda trip_detail: b"%PDF-1.4\n%mock pdf\n",
    )

    response = client.get(f"/export/{generated_itinerary['saved_trip_id']}/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")


def test_generate_trip_response_includes_rag_context(client: TestClient) -> None:
    response = client.post("/trip/generate", json=build_generate_payload())

    assert response.status_code == 200
    data = response.json()
    joined_notes = "\n".join(data["source_notes"])

    assert len(data["source_notes"]) >= 2
    assert "大理" in joined_notes
