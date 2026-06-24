from pathlib import Path
import sys

import httpx


CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.agents.tools.tavily_search_tool as tavily_tool  # noqa: E402
from app.models.schemas import SourceType  # noqa: E402


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.request = httpx.Request("POST", "https://api.tavily.com/search")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "bad status",
                request=self.request,
                response=httpx.Response(self.status_code, request=self.request),
            )

    def json(self) -> dict:
        return self._payload


class FakeClient:
    def __init__(self, responses: list[FakeResponse | Exception]) -> None:
        self.responses = responses
        self.calls = 0

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def post(self, *args, **kwargs) -> FakeResponse:
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_tavily_missing_key_returns_fallback(monkeypatch) -> None:
    monkeypatch.setattr(tavily_tool, "TAVILY_API_KEY", "")

    outcome = tavily_tool.search_tavily("大理 开放时间", "opening_hours")

    assert outcome.results == []
    assert outcome.fallback_reason == "missing_api_key"
    assert outcome.fallback_order == ("amap", "local_rag", "demo")


def test_tavily_rejects_disallowed_category(monkeypatch) -> None:
    monkeypatch.setattr(tavily_tool, "TAVILY_API_KEY", "test-key")

    outcome = tavily_tool.search_tavily("大理 酒店价格", "realtime_price")

    assert outcome.results == []
    assert outcome.fallback_reason == "category_not_allowed"


def test_tavily_rejects_url_shaped_query(monkeypatch) -> None:
    monkeypatch.setattr(tavily_tool, "TAVILY_API_KEY", "test-key")

    outcome = tavily_tool.search_tavily("https://example.com", "public_guide")

    assert outcome.results == []
    assert outcome.fallback_reason == "url_query_not_allowed"


def test_tavily_success_parses_source_records(monkeypatch) -> None:
    fake_client = FakeClient(
        [
            FakeResponse(
                {
                    "results": [
                        {
                            "title": "大理古城游玩攻略",
                            "url": "https://example.com/dali-guide",
                            "content": "公开攻略摘要",
                        }
                    ]
                }
            )
        ]
    )
    monkeypatch.setattr(tavily_tool, "TAVILY_API_KEY", "test-key")
    monkeypatch.setattr(tavily_tool, "_build_client", lambda: fake_client)

    outcome = tavily_tool.search_tavily("大理 古城 攻略", "public_guide")

    assert outcome.fallback_reason is None
    assert len(outcome.results) == 1
    assert outcome.results[0].title == "大理古城游玩攻略"
    assert outcome.results[0].url == "https://example.com/dali-guide"
    assert outcome.results[0].summary == "公开攻略摘要"
    assert outcome.results[0].source_type == SourceType.tavily
    assert outcome.results[0].category == "public_guide"
    assert fake_client.calls == 1


def test_tavily_retries_once_then_succeeds(monkeypatch) -> None:
    fake_client = FakeClient(
        [
            httpx.TimeoutException("timeout"),
            FakeResponse(
                {
                    "results": [
                        {
                            "title": "大理餐饮提示",
                            "url": "https://example.com/dali-food",
                            "content": "餐饮公开信息摘要",
                        }
                    ]
                }
            ),
        ]
    )
    monkeypatch.setattr(tavily_tool, "TAVILY_API_KEY", "test-key")
    monkeypatch.setattr(tavily_tool, "TAVILY_MAX_RETRIES", 1)
    monkeypatch.setattr(tavily_tool, "_build_client", lambda: fake_client)

    outcome = tavily_tool.search_tavily("大理 餐饮 推荐", "food")

    assert len(outcome.results) == 1
    assert fake_client.calls == 2


def test_tavily_network_failure_returns_fallback(monkeypatch) -> None:
    fake_client = FakeClient([httpx.ConnectError("network down")])
    monkeypatch.setattr(tavily_tool, "TAVILY_API_KEY", "test-key")
    monkeypatch.setattr(tavily_tool, "TAVILY_MAX_RETRIES", 0)
    monkeypatch.setattr(tavily_tool, "_build_client", lambda: fake_client)

    outcome = tavily_tool.search_tavily("大理 临时政策", "temporary_policy")

    assert outcome.results == []
    assert outcome.fallback_reason == "network_error"
    assert outcome.should_fallback is True
