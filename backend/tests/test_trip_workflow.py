from pathlib import Path
import sys


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
