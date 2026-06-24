from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import (
    TAVILY_API_KEY,
    TAVILY_API_URL,
    TAVILY_MAX_RETRIES,
    TAVILY_TIMEOUT_SECONDS,
)
from app.models.schemas import SourceRecord, SourceType


ALLOWED_TAVILY_CATEGORIES = {
    "scenic_spot",
    "opening_hours",
    "food",
    "public_guide",
    "travel_tip",
    "temporary_policy",
}

FALLBACK_ORDER = ("amap", "local_rag", "demo")


@dataclass
class TavilySearchOutcome:
    """Result wrapper that keeps failures explicit without breaking fallback paths."""

    query: str
    category: str
    results: list[SourceRecord] = field(default_factory=list)
    fallback_reason: str | None = None
    fallback_order: tuple[str, ...] = FALLBACK_ORDER

    @property
    def should_fallback(self) -> bool:
        return not self.results


def _normalize_query(query: str) -> str:
    return " ".join(query.strip().split())


def _contains_url(text: str) -> bool:
    lowered = text.lower()
    return "http://" in lowered or "https://" in lowered or "www." in lowered


def _is_allowed_tavily_endpoint(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.netloc == "api.tavily.com"


def _build_client() -> httpx.Client:
    return httpx.Client(timeout=TAVILY_TIMEOUT_SECONDS)


def _build_failure(query: str, category: str, reason: str) -> TavilySearchOutcome:
    return TavilySearchOutcome(
        query=query,
        category=category,
        results=[],
        fallback_reason=reason,
    )


def _parse_tavily_results(
    query: str,
    category: str,
    payload: dict[str, Any],
    max_results: int,
) -> TavilySearchOutcome:
    queried_at = datetime.utcnow()
    raw_results = payload.get("results", [])
    if not isinstance(raw_results, list):
        return _build_failure(query, category, "invalid_response")

    records: list[SourceRecord] = []
    seen_keys: set[str] = set()
    for item in raw_results:
        if not isinstance(item, dict):
            continue

        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        summary = str(item.get("content") or item.get("summary") or "").strip()
        if not title or not summary:
            continue

        dedupe_key = (url or title).lower()
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        records.append(
            SourceRecord(
                title=title,
                url=url or None,
                summary=summary[:800],
                queried_at=queried_at,
                source_type=SourceType.tavily,
                category=category,
            )
        )
        if len(records) >= max_results:
            break

    return TavilySearchOutcome(
        query=query,
        category=category,
        results=records,
        fallback_reason=None if records else "empty_results",
    )


def search_tavily(
    query: str,
    category: str,
    max_results: int = 5,
) -> TavilySearchOutcome:
    """Search Tavily through a narrow whitelist tool.

    This tool is intentionally not a general HTTP client. It accepts only
    approved travel categories and refuses URL-shaped queries.
    """

    normalized_query = _normalize_query(query)
    if category not in ALLOWED_TAVILY_CATEGORIES:
        return _build_failure(normalized_query, category, "category_not_allowed")
    if not normalized_query:
        return _build_failure(normalized_query, category, "empty_query")
    if len(normalized_query) > 240:
        return _build_failure(normalized_query, category, "query_too_long")
    if _contains_url(normalized_query):
        return _build_failure(normalized_query, category, "url_query_not_allowed")
    if not TAVILY_API_KEY:
        return _build_failure(normalized_query, category, "missing_api_key")
    if not _is_allowed_tavily_endpoint(TAVILY_API_URL):
        return _build_failure(normalized_query, category, "endpoint_not_allowed")

    safe_max_results = max(1, min(max_results, 8))
    attempts = 1 + min(max(TAVILY_MAX_RETRIES, 0), 1)
    last_error = "request_failed"

    for _attempt in range(attempts):
        try:
            with _build_client() as client:
                response = client.post(
                    TAVILY_API_URL,
                    headers={
                        "Authorization": f"Bearer {TAVILY_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "query": normalized_query,
                        "search_depth": "basic",
                        "include_answer": False,
                        "include_raw_content": False,
                        "max_results": safe_max_results,
                    },
                )
                response.raise_for_status()
                payload = response.json()
            return _parse_tavily_results(
                query=normalized_query,
                category=category,
                payload=payload,
                max_results=safe_max_results,
            )
        except httpx.TimeoutException:
            last_error = "timeout"
        except httpx.HTTPStatusError:
            last_error = "bad_status"
        except httpx.HTTPError:
            last_error = "network_error"
        except ValueError:
            last_error = "invalid_json"

    return _build_failure(normalized_query, category, last_error)
