from pathlib import Path
import sys


CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.tools import browser_price_tool  # noqa: E402
from app.models.schemas import SourceType, TripRequest  # noqa: E402


def test_extract_price_items_from_visible_text() -> None:
    items = browser_price_tool._extract_price_items(
        text="Dali hotel room from ¥588 per night. Scenic ticket 120元起.",
        url="https://example.test/hotel",
        page_title="Hotel page",
        observed_at="2026-06-25T00:00:00",
        max_items=5,
    )

    assert len(items) >= 2
    assert items[0]["amount"] == 588.0
    assert items[0]["currency"] == "CNY"
    assert items[0]["source_type"] == SourceType.browser_observed


def test_observe_browser_prices_skips_when_not_requested() -> None:
    request = TripRequest(
        destination="Dali",
        start_date="2026-06-25",
        end_date="2026-06-26",
        travelers=2,
        budget=3000,
        price_observation_urls=["https://example.test/hotel"],
    )

    result = browser_price_tool.observe_browser_prices(request)

    assert result["status"] == "skipped"
    assert result["fallback_reason"] == "browser_price_not_requested"
    assert result["items"] == []


def test_collect_observation_urls_generates_ctrip_entries_from_trip_request(monkeypatch) -> None:
    monkeypatch.setattr(browser_price_tool.config, "BROWSER_MAX_URLS", 4)
    request = TripRequest(
        origin_city="上海",
        destination="大理",
        start_date="2026-06-25",
        end_date="2026-06-27",
        travelers=2,
        budget=3000,
        browser_price_enabled=True,
    )

    urls, generated_urls = browser_price_tool._collect_observation_urls(request)

    assert len(urls) == 4
    assert urls == generated_urls
    assert urls[0].startswith("https://trains.ctrip.com/webapp/train/list")
    assert "dStation=%E4%B8%8A%E6%B5%B7" in urls[0]
    assert "aStation=%E5%A4%A7%E7%90%86" in urls[0]
    assert urls[1] == "https://flights.ctrip.com/online/channel/domestic"
    assert urls[2].startswith("https://vacations.ctrip.com/")
    assert urls[3] == "https://www.ctrip.com/"


def test_browser_attempt_record_is_created_when_no_price_found() -> None:
    records = browser_price_tool._build_attempt_source_records(
        urls=["https://trains.ctrip.com/"],
        status="no_price",
        fallback_reason="no_visible_price_found",
        prepared_actions=["https://trains.ctrip.com/:train_origin"],
    )

    assert len(records) == 1
    assert records[0].source_type == SourceType.browser_observed
    assert records[0].category == "browser_attempt"
    assert "no_price" in records[0].summary
    assert "no_visible_price_found" in records[0].summary
