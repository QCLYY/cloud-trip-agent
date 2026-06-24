from __future__ import annotations

from typing import Any

from app.agents.tools.rag_tool import get_destination_guide_context
from app.agents.tools.tavily_search_tool import search_tavily
from app.models.schemas import SourceType, TripRequest


def tavily_search_tool(query: str, category: str) -> dict[str, Any]:
    outcome = search_tavily(query=query, category=category)
    return {
        "results": outcome.results,
        "fallback_reason": outcome.fallback_reason,
        "fallback_order": list(outcome.fallback_order),
        "source_type": SourceType.tavily if outcome.results else None,
    }


def local_rag_tool(request: TripRequest) -> dict[str, Any]:
    contexts, rewrite_usage, rerank_usage, embedding_usage = get_destination_guide_context(
        destination=request.destination,
        preferences=request.preferences,
        pace=request.pace,
        special_notes=request.special_notes,
        top_k=3,
    )
    return {
        "contexts": contexts,
        "token_usage": {
            "rewrite_prompt_tokens": rewrite_usage.get("prompt_tokens", 0),
            "rewrite_completion_tokens": rewrite_usage.get("completion_tokens", 0),
            "rerank_prompt_tokens": rerank_usage.get("prompt_tokens", 0),
            "rerank_completion_tokens": rerank_usage.get("completion_tokens", 0),
            "embedding_prompt_tokens": embedding_usage.get("prompt_tokens", 0),
            "embedding_completion_tokens": embedding_usage.get("completion_tokens", 0),
        },
        "source_type": SourceType.demo,
    }


def demo_transport_tool(request: TripRequest) -> dict[str, Any]:
    return {
        "options": ["train_or_flight_estimate", "local_taxi_estimate"],
        "source_type": SourceType.estimate,
    }


def demo_hotel_tool(request: TripRequest) -> dict[str, Any]:
    return {
        "hotel_level": request.hotel_level or "舒适型",
        "source_type": SourceType.estimate,
    }


def demo_ticket_tool(request: TripRequest) -> dict[str, Any]:
    return {
        "pricing": "deterministic_ticket_estimate",
        "source_type": SourceType.estimate,
    }


def budget_tool(request: TripRequest) -> dict[str, Any]:
    return {
        "budget": request.budget,
        "source_type": SourceType.estimate,
    }


WHITELISTED_TOOL_NAMES = {
    "TavilySearchTool",
    "AmapPOITool",
    "RouteTool",
    "WeatherTool",
    "LocalRAGTool",
    "DemoTransportTool",
    "DemoHotelTool",
    "DemoTicketTool",
    "BudgetTool",
}
