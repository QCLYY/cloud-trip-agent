from pathlib import Path
import sys


CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models.schemas import (  # noqa: E402
    BudgetBreakdown,
    DayPlan,
    HotelItem,
    Itinerary,
    MealItem,
    SpotItem,
    TransportItem,
)
from app.services.candidate_service import attach_candidate_itineraries  # noqa: E402


def build_itinerary() -> Itinerary:
    return Itinerary(
        trip_id="trip_candidate_demo",
        destination="大理",
        summary="候选测试",
        days=[
            DayPlan(
                day_index=1,
                theme="古城慢游",
                spots=[SpotItem(name="大理古城", estimated_cost=20)],
                meals=[MealItem(name="本地餐饮", meal_type="午餐", estimated_cost=100)],
                hotel=HotelItem(name="大理 舒适型住宿", level="舒适型", estimated_cost=400),
                transport=[TransportItem(mode="打车", estimated_cost=80)],
            )
        ],
        estimated_budget=600,
        budget_breakdown=BudgetBreakdown(
            transport=80,
            hotel=400,
            meals=100,
            tickets=20,
            other=0,
            total=600,
        ),
        tips=[],
        source_notes=[],
    )


def test_attach_candidate_itineraries_defaults_to_two_options() -> None:
    itinerary = attach_candidate_itineraries(build_itinerary())

    assert len(itinerary.candidate_itineraries) == 2
    economy, balanced = itinerary.candidate_itineraries

    assert economy.candidate_id == "economy"
    assert balanced.candidate_id == "balanced"
    assert economy.estimated_budget < balanced.estimated_budget
    assert economy.days[0].transport[0].mode == "公交/步行"
    assert economy.days[0].hotel.level == "经济型"
    assert len(economy.differences) >= 2


def test_attach_candidate_itineraries_can_include_experience_option() -> None:
    itinerary = attach_candidate_itineraries(build_itinerary(), include_experience=True)

    assert [candidate.candidate_id for candidate in itinerary.candidate_itineraries] == [
        "economy",
        "balanced",
        "experience",
    ]
