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
from app.models.schemas import Itinerary  # noqa: E402
import app.services.assistant_service as assistant_service  # noqa: E402


TEST_PASSWORD = "test_password"


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "assistant_api_test.db"
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


def register_and_login(client: TestClient, username: str) -> dict[str, str]:
    assert client.post(
        "/auth/register",
        json={"username": username, "password": TEST_PASSWORD},
    ).status_code == 201
    response = client.post(
        "/auth/login",
        json={"username": username, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def build_itinerary(trip_id: str = "trip_assistant_demo") -> dict:
    return {
        "trip_id": trip_id,
        "destination": "大理",
        "summary": "适合轻松游览的大理三日行程。",
        "days": [
            {
                "day_index": 1,
                "date": "2026-04-10",
                "theme": "古城慢游",
                "spots": [
                    {
                        "name": "大理古城",
                        "description": "慢慢逛古城。",
                        "estimated_cost": 0,
                        "location": "大理",
                        "source_type": "estimate",
                        "cost_source_type": "estimate",
                    }
                ],
                "meals": [
                    {
                        "name": "大理白族餐厅",
                        "meal_type": "午餐",
                        "estimated_cost": 120,
                        "notes": "清淡口味。",
                        "source_type": "estimate",
                        "cost_source_type": "estimate",
                    }
                ],
                "hotel": {
                    "name": "大理舒适型住宿",
                    "level": "舒适型",
                    "estimated_cost": 500,
                    "location": "大理古城附近",
                    "source_type": "estimate",
                    "cost_source_type": "estimate",
                },
                "transport": [
                    {
                        "mode": "打车",
                        "from_place": "酒店",
                        "to_place": "大理古城",
                        "estimated_cost": 40,
                        "duration": "20 分钟",
                        "source_type": "estimate",
                        "cost_source_type": "estimate",
                    }
                ],
                "notes": ["节奏轻松。"],
            },
            {
                "day_index": 2,
                "date": "2026-04-11",
                "theme": "博物馆与街区",
                "spots": [
                    {
                        "name": "大理博物馆",
                        "description": "了解地方历史。",
                        "estimated_cost": 30,
                        "location": "大理",
                        "source_type": "estimate",
                        "cost_source_type": "estimate",
                    }
                ],
                "meals": [
                    {
                        "name": "古城米线",
                        "meal_type": "午餐",
                        "estimated_cost": 100,
                        "notes": "地方小吃。",
                        "source_type": "estimate",
                        "cost_source_type": "estimate",
                    }
                ],
                "hotel": {
                    "name": "大理舒适型住宿",
                    "level": "舒适型",
                    "estimated_cost": 500,
                    "location": "大理古城附近",
                    "source_type": "estimate",
                    "cost_source_type": "estimate",
                },
                "transport": [
                    {
                        "mode": "打车",
                        "from_place": "酒店",
                        "to_place": "大理博物馆",
                        "estimated_cost": 50,
                        "duration": "25 分钟",
                        "source_type": "estimate",
                        "cost_source_type": "estimate",
                    }
                ],
                "notes": ["上午慢行。"],
            },
        ],
        "estimated_budget": 1340,
        "budget_breakdown": {
            "transport": 90,
            "hotel": 1000,
            "meals": 220,
            "tickets": 30,
            "other": 0,
            "total": 1340,
            "source_type": "estimate",
        },
        "tips": ["本地演示数据、规则估算和 Tavily 外部检索不代表实时价格。"],
        "source_notes": [],
        "source_records": [
            {
                "title": "Local planning rules",
                "summary": "Budget and route are estimated by deterministic rules.",
                "source_type": "estimate",
                "category": "itinerary",
            },
            {
                "title": "Tavily public guide",
                "url": "https://example.com/dali",
                "summary": "Public guide snippet for testing source display.",
                "source_type": "tavily",
                "category": "travel_tip",
            },
        ],
        "execution_events": [],
        "candidate_itineraries": [
            {
                "candidate_id": "economy",
                "title": "经济优先",
                "strategy": "economy",
                "summary": "减少交通和住宿预算。",
                "days": [],
                "estimated_budget": 1100,
                "budget_breakdown": {
                    "transport": 70,
                    "hotel": 850,
                    "meals": 160,
                    "tickets": 20,
                    "other": 0,
                    "total": 1100,
                    "source_type": "estimate",
                },
                "differences": ["交通更多使用公交", "酒店区域更靠近交通站点"],
            },
            {
                "candidate_id": "balanced",
                "title": "均衡推荐",
                "strategy": "balanced",
                "summary": "在预算和体验之间保持平衡。",
                "days": [],
                "estimated_budget": 1340,
                "budget_breakdown": {
                    "transport": 90,
                    "hotel": 1000,
                    "meals": 220,
                    "tickets": 30,
                    "other": 0,
                    "total": 1340,
                    "source_type": "estimate",
                },
                "differences": ["酒店区域更便利", "每日节奏更均衡"],
            },
        ],
    }


def save_trip(client: TestClient, headers: dict[str, str], trip_id: str = "trip_assistant_demo") -> str:
    itinerary = build_itinerary(trip_id)
    response = client.post(
        "/trip/save",
        json={"trip_id": itinerary["trip_id"], "itinerary": itinerary},
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()["trip_id"]


def send_message(
    client: TestClient,
    headers: dict[str, str],
    trip_id: str,
    message: str,
    **extra,
):
    payload = {"trip_id": trip_id, "message": message, **extra}
    return client.post("/assistant/message", json=payload, headers=headers)


def test_user_can_send_message_and_history_is_persisted(client: TestClient) -> None:
    headers = register_and_login(client, "assistant_user")
    trip_id = save_trip(client, headers)

    response = send_message(client, headers, trip_id, "当前总预算是多少？")

    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "query_trip"
    assert "预算" in data["reply"]

    history = client.get(f"/assistant/trips/{trip_id}/messages", headers=headers)
    assert history.status_code == 200
    assert history.json()["total"] == 2
    assert [item["role"] for item in history.json()["items"]] == ["user", "assistant"]


def test_conversation_is_bound_to_user_and_trip(client: TestClient) -> None:
    owner_headers = register_and_login(client, "assistant_owner")
    other_headers = register_and_login(client, "assistant_other")
    trip_id = save_trip(client, owner_headers)
    send_message(client, owner_headers, trip_id, "当前总预算是多少？")

    owner_history = client.get(f"/assistant/trips/{trip_id}/messages", headers=owner_headers)
    other_history = client.get(f"/assistant/trips/{trip_id}/messages", headers=other_headers)

    assert owner_history.status_code == 200
    assert owner_history.json()["total"] == 2
    assert other_history.status_code == 404


def test_modify_trip_creates_new_version(client: TestClient, monkeypatch) -> None:
    headers = register_and_login(client, "assistant_modify")
    trip_id = save_trip(client, headers)

    def fake_edit_trip(request):
        itinerary = request.current_itinerary.model_copy(deep=True)
        itinerary.days[1].theme = "自然景点轻松游"
        itinerary.days[1].spots[0].name = "洱海生态廊道"
        return itinerary

    monkeypatch.setattr(assistant_service, "edit_trip_itinerary", fake_edit_trip)

    response = send_message(client, headers, trip_id, "第二天不要安排博物馆，换成自然景点")

    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "modify_trip"
    assert data["trip_changed"] is True
    assert data["new_version_number"] == 2
    assert data["itinerary"]["days"][1]["spots"][0]["name"] == "洱海生态廊道"


def test_query_budget_does_not_create_version(client: TestClient) -> None:
    headers = register_and_login(client, "assistant_budget")
    trip_id = save_trip(client, headers)

    response = send_message(client, headers, trip_id, "当前总预算是多少？")
    versions = client.get(f"/trip/{trip_id}/versions", headers=headers)

    assert response.status_code == 200
    assert response.json()["trip_changed"] is False
    assert versions.json()["total"] == 1


def test_explain_plan_does_not_create_version(client: TestClient) -> None:
    headers = register_and_login(client, "assistant_explain")
    trip_id = save_trip(client, headers)

    response = send_message(client, headers, trip_id, "为什么推荐均衡方案？", candidate_id="balanced")
    versions = client.get(f"/trip/{trip_id}/versions", headers=headers)

    assert response.status_code == 200
    assert response.json()["intent"] == "explain_plan"
    assert response.json()["trip_changed"] is False
    assert versions.json()["total"] == 1


def test_confirmation_action_uses_confirmation_service(client: TestClient) -> None:
    headers = register_and_login(client, "assistant_confirm")
    trip_id = save_trip(client, headers)

    pending = send_message(client, headers, trip_id, "请恢复到版本 1")
    assert pending.status_code == 200
    payload = pending.json()["message"]["structured_payload"]
    assert pending.json()["confirmation_required"] is True
    assert payload["confirmation_id"]

    confirmed = send_message(
        client,
        headers,
        trip_id,
        "确认恢复",
        confirmation_id=payload["confirmation_id"],
        action="confirmed",
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["intent"] == "confirm_action"
    assert confirmed.json()["trip_changed"] is True
    assert confirmed.json()["new_version_number"] == 2


def test_invalid_trip_id_returns_404(client: TestClient) -> None:
    headers = register_and_login(client, "assistant_missing")

    response = send_message(client, headers, "trip_missing", "当前总预算是多少？")

    assert response.status_code == 404


def test_assistant_requires_token(client: TestClient) -> None:
    response = client.post(
        "/assistant/message",
        json={"trip_id": "trip_demo", "message": "当前总预算是多少？"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_conversation_history_is_time_ordered(client: TestClient) -> None:
    headers = register_and_login(client, "assistant_order")
    trip_id = save_trip(client, headers)

    send_message(client, headers, trip_id, "当前总预算是多少？")
    send_message(client, headers, trip_id, "第二天有哪些安排？")

    history = client.get(f"/assistant/trips/{trip_id}/messages", headers=headers).json()

    assert history["total"] == 4
    assert history["items"][0]["role"] == "user"
    assert history["items"][0]["content"] == "当前总预算是多少？"
    assert history["items"][2]["content"] == "第二天有哪些安排？"


def test_messages_do_not_store_sensitive_content(client: TestClient) -> None:
    headers = register_and_login(client, "assistant_sensitive")
    trip_id = save_trip(client, headers)

    response = send_message(client, headers, trip_id, "我的密码是 abc123")
    history = client.get(f"/assistant/trips/{trip_id}/messages", headers=headers).json()

    assert response.status_code == 200
    assert "abc123" not in response.text
    assert history["items"][0]["content"] == "[敏感信息已隐藏]"
    assert "abc123" not in str(history)


def test_unsupported_intent_returns_safe_message(client: TestClient) -> None:
    headers = register_and_login(client, "assistant_unsupported")
    trip_id = save_trip(client, headers)

    response = send_message(client, headers, trip_id, "帮我自动预订并支付酒店")

    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "unsupported"
    assert "不能进行预订" in data["reply"]


def test_clear_messages_does_not_delete_trip(client: TestClient) -> None:
    headers = register_and_login(client, "assistant_clear")
    trip_id = save_trip(client, headers)
    send_message(client, headers, trip_id, "当前总预算是多少？")

    clear_response = client.delete(f"/assistant/trips/{trip_id}/messages", headers=headers)
    trip_response = client.get(f"/trip/{trip_id}", headers=headers)
    history = client.get(f"/assistant/trips/{trip_id}/messages", headers=headers)

    assert clear_response.status_code == 200
    assert clear_response.json()["deleted_count"] == 2
    assert trip_response.status_code == 200
    assert history.json()["total"] == 0


def test_stable_preference_requires_confirmation_before_memory_save(client: TestClient) -> None:
    headers = register_and_login(client, "assistant_memory")
    trip_id = save_trip(client, headers)
    assert client.put("/memory", json={"enabled": True}, headers=headers).status_code == 200

    pending = send_message(client, headers, trip_id, "以后旅行都不要安排早班飞机")
    assert pending.status_code == 200
    pending_data = pending.json()
    assert pending_data["intent"] == "confirm_action"
    assert pending_data["confirmation_required"] is True
    confirmation_id = pending_data["message"]["structured_payload"]["confirmation_id"]

    before_confirm = client.get("/memory", headers=headers).json()
    assert before_confirm["items"] == []

    confirmed = send_message(
        client,
        headers,
        trip_id,
        "确认保存",
        confirmation_id=confirmation_id,
        action="confirmed",
    )
    assert confirmed.status_code == 200
    assert "长期" in confirmed.json()["reply"]

    after_confirm = client.get("/memory", headers=headers).json()
    assert after_confirm["items"][0]["content"] == "以后旅行都不要安排早班飞机"
