from pathlib import Path
import sys
import threading
import time


CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.workflow.trip_workflow import run_trip_generation_workflow  # noqa: E402
from app.models.schemas import (  # noqa: E402
    BudgetBreakdown,
    DayPlan,
    HotelItem,
    Itinerary,
    MealItem,
    SourceType,
    SourceRecord,
    SpotItem,
    TransportItem,
    TripRequest,
)


def build_trip_request() -> TripRequest:
    return TripRequest(
        destination="大理",
        start_date="2026-04-10",
        end_date="2026-04-11",
        travelers=2,
        budget=3200,
        preferences=["自然风景", "拍照"],
        pace="轻松",
        dietary_preferences=["少辣"],
        hotel_level="舒适型",
        special_notes="想看日落",
    )


def fake_legacy_generator(request: TripRequest) -> Itinerary:
    return Itinerary(
        trip_id="trip_workflow_demo",
        destination=request.destination,
        summary="workflow demo",
        days=[
            DayPlan(
                day_index=1,
                date=request.start_date,
                theme="古城慢游",
                spots=[
                    SpotItem(
                        name="大理古城",
                        estimated_cost=20,
                        source_type=SourceType.estimate,
                    )
                ],
                meals=[
                    MealItem(
                        name="本地餐饮",
                        meal_type="午餐",
                        estimated_cost=80,
                        source_type=SourceType.estimate,
                    )
                ],
                hotel=HotelItem(
                    name="舒适型住宿",
                    estimated_cost=300,
                    source_type=SourceType.estimate,
                ),
                transport=[
                    TransportItem(
                        mode="打车",
                        estimated_cost=50,
                        source_type=SourceType.estimate,
                    )
                ],
            )
        ],
        estimated_budget=450,
        budget_breakdown=BudgetBreakdown(
            transport=50,
            hotel=300,
            meals=80,
            tickets=20,
            other=0,
            total=450,
        ),
        tips=[],
        source_notes=[],
    )


def test_trip_workflow_returns_compatible_itinerary_with_events(monkeypatch) -> None:
    import app.agents.tools.tavily_search_tool as tavily_tool

    monkeypatch.setattr(tavily_tool, "TAVILY_API_KEY", "")

    itinerary = run_trip_generation_workflow(
        build_trip_request(),
        legacy_generator=fake_legacy_generator,
        user_id=7,
    )

    assert itinerary.trip_id == "trip_workflow_demo"
    assert itinerary.destination == "大理"
    assert itinerary.execution_events

    agents = [event.agent for event in itinerary.execution_events]
    assert "Supervisor Agent" in agents
    assert "Requirement Agent" in agents
    assert "Planner Agent" in agents
    assert "Transport Agent" in agents
    assert "Hotel Agent" in agents
    assert "POI Agent" in agents
    assert "Ticket Agent" in agents
    assert "Food Agent" in agents
    assert "Weather Agent" in agents
    assert "Browser Price Agent" in agents
    assert "Verification Agent" in agents
    assert "Finalizer" in agents

    supervisor_events = [event for event in itinerary.execution_events if event.agent == "Supervisor Agent"]
    assert all(event.tool is None for event in supervisor_events)
    assert any(event.agent == "Planner Agent" and event.status == "success" for event in itinerary.execution_events)
    assert any(event.fallback for event in itinerary.execution_events)
    assert all(event.user_id == 7 for event in itinerary.execution_events)


def test_trip_workflow_appends_workflow_source_record() -> None:
    itinerary = run_trip_generation_workflow(
        build_trip_request(),
        legacy_generator=fake_legacy_generator,
        user_id=3,
    )

    assert any(
        record.category == "agent_workflow"
        for record in itinerary.source_records
    )


def test_professional_agents_run_in_parallel(monkeypatch) -> None:
    import app.agents.workflow.trip_workflow as trip_workflow
    from app.agents.workflow.state import TripWorkflowState, record_event, start_timer

    active_agents = 0
    max_active_agents = 0
    lock = threading.Lock()

    def make_agent(key: str, label: str):
        def agent(state: TripWorkflowState) -> TripWorkflowState:
            nonlocal active_agents, max_active_agents

            started_at = start_timer()
            with lock:
                active_agents += 1
                max_active_agents = max(max_active_agents, active_agents)

            time.sleep(0.05)
            state.agent_results[key] = {"source_type": SourceType.estimate}
            record_event(
                state,
                agent=label,
                status="success",
                started_at=started_at,
                source_type=SourceType.estimate,
            )

            with lock:
                active_agents -= 1
            return state

        return agent

    monkeypatch.setattr(
        trip_workflow,
        "run_transport_agent",
        make_agent("transport", "Transport Agent"),
    )
    monkeypatch.setattr(
        trip_workflow,
        "run_hotel_agent",
        make_agent("hotel", "Hotel Agent"),
    )
    monkeypatch.setattr(
        trip_workflow,
        "run_poi_agent",
        make_agent("poi", "POI Agent"),
    )
    monkeypatch.setattr(
        trip_workflow,
        "run_ticket_agent",
        make_agent("ticket", "Ticket Agent"),
    )
    monkeypatch.setattr(
        trip_workflow,
        "run_food_agent",
        make_agent("food", "Food Agent"),
    )
    monkeypatch.setattr(
        trip_workflow,
        "run_weather_agent",
        make_agent("weather", "Weather Agent"),
    )
    monkeypatch.setattr(
        trip_workflow,
        "run_budget_engine",
        make_agent("budget", "Budget Engine"),
    )
    monkeypatch.setattr(
        trip_workflow,
        "run_browser_price_agent",
        make_agent("browser_price", "Browser Price Agent"),
    )

    state = trip_workflow.run_professional_agents(
        TripWorkflowState(request=build_trip_request(), user_id=9)
    )

    assert max_active_agents > 1
    assert set(state.agent_results) == {
        "transport",
        "hotel",
        "poi",
        "ticket",
        "food",
        "weather",
        "budget",
        "browser_price",
    }
    assert any(
        event.agent == "Professional Agents" and event.status == "success"
        for event in state.execution_events
    )


def test_browser_price_result_is_applied_to_itinerary(monkeypatch) -> None:
    import app.agents.workflow.professional_agents as professional_agents

    def fake_browser_price_tool(request: TripRequest) -> dict[str, object]:
        return {
            "status": "success",
            "items": [
                {
                    "title": "Hotel page",
                    "url": "https://example.test/hotel",
                    "price_text": "¥588",
                    "amount": 588.0,
                    "currency": "CNY",
                    "category": "hotel",
                    "confidence": 0.8,
                    "raw_context": "Hotel visible price ¥588",
                    "observed_at": "2026-06-25T00:00:00",
                    "source_type": SourceType.browser_observed,
                }
            ],
            "source_records": [
                SourceRecord(
                    title="Browser observed price: ¥588",
                    url="https://example.test/hotel",
                    summary="Visible page price was observed.",
                    source_type=SourceType.browser_observed,
                    category="hotel",
                )
            ],
            "requires_human": False,
            "fallback_reason": None,
            "notice": "Visible-page price only.",
            "source_type": SourceType.browser_observed,
        }

    monkeypatch.setattr(professional_agents, "browser_price_tool", fake_browser_price_tool)
    request = build_trip_request().model_copy(
        update={
            "browser_price_enabled": True,
            "price_observation_urls": ["https://example.test/hotel"],
        }
    )

    itinerary = run_trip_generation_workflow(
        request,
        legacy_generator=fake_legacy_generator,
        user_id=11,
    )

    assert itinerary.days[0].hotel is not None
    assert itinerary.days[0].hotel.estimated_cost == 588.0
    assert itinerary.days[0].hotel.source_type == SourceType.browser_observed
    assert itinerary.budget_breakdown.source_type == SourceType.browser_observed
    assert any(
        record.source_type == SourceType.browser_observed
        for record in itinerary.source_records
    )
