from __future__ import annotations

from app.agents.workflow.state import TripWorkflowState, record_event, start_timer
from app.agents.workflow.tools import (
    browser_price_tool,
    budget_tool,
    demo_hotel_tool,
    demo_ticket_tool,
    demo_transport_tool,
    local_rag_tool,
    tavily_search_tool,
)
from app.models.schemas import SourceType


def run_transport_agent(state: TripWorkflowState) -> TripWorkflowState:
    started_at = start_timer()
    query_parts = [state.request.destination, "交通", "高铁", "航班"]
    if state.request.origin_city:
        query_parts.append(state.request.origin_city)
    tavily_result = tavily_search_tool(
        query=" ".join(query_parts),
        category="travel_tip",
    )
    fallback = not tavily_result["results"]
    if fallback:
        result = demo_transport_tool(state.request)
        state.agent_results["transport"] = result
    else:
        state.agent_results["transport"] = {
            "records": tavily_result["results"],
            "fallback_reason": None,
            "source_type": SourceType.tavily,
        }
    record_event(
        state,
        agent="Transport Agent",
        tool="TavilySearchTool" if not fallback else "DemoTransportTool",
        status="fallback" if fallback else "success",
        started_at=started_at,
        fallback=fallback,
        error=tavily_result["fallback_reason"] if fallback else None,
        source_type=SourceType.demo if fallback else SourceType.tavily,
    )
    return state


def run_hotel_agent(state: TripWorkflowState) -> TripWorkflowState:
    started_at = start_timer()
    hotel_level = state.request.hotel_level or "舒适型"
    tavily_result = tavily_search_tool(
        query=f"{state.request.destination} {hotel_level} 酒店 住宿 推荐",
        category="travel_tip",
    )
    fallback = not tavily_result["results"]
    if fallback:
        result = demo_hotel_tool(state.request)
        state.agent_results["hotel"] = result
    else:
        state.agent_results["hotel"] = {
            "records": tavily_result["results"],
            "hotel_level": hotel_level,
            "fallback_reason": None,
            "source_type": SourceType.tavily,
        }
    record_event(
        state,
        agent="Hotel Agent",
        tool="TavilySearchTool" if not fallback else "DemoHotelTool",
        status="fallback" if fallback else "success",
        started_at=started_at,
        fallback=fallback,
        error=tavily_result["fallback_reason"] if fallback else None,
        source_type=SourceType.demo if fallback else SourceType.tavily,
    )
    return state


def run_poi_agent(state: TripWorkflowState) -> TripWorkflowState:
    started_at = start_timer()
    tavily_result = tavily_search_tool(
        query=f"{state.request.destination} 景点 开放时间 旅行提示",
        category="scenic_spot",
    )
    fallback = not tavily_result["results"]
    if fallback:
        rag_result = local_rag_tool(state.request)
        state.agent_results["poi"] = {
            "records": [],
            "contexts": rag_result["contexts"],
            "fallback_reason": tavily_result["fallback_reason"],
            "source_type": SourceType.demo,
        }
    else:
        state.agent_results["poi"] = {
            "records": tavily_result["results"],
            "contexts": [],
            "fallback_reason": None,
            "source_type": SourceType.tavily,
        }
    record_event(
        state,
        agent="POI Agent",
        tool="TavilySearchTool" if not fallback else "LocalRAGTool",
        status="fallback" if fallback else "success",
        started_at=started_at,
        fallback=fallback,
        error=tavily_result["fallback_reason"] if fallback else None,
        source_type=SourceType.demo if fallback else SourceType.tavily,
    )
    return state


def run_ticket_agent(state: TripWorkflowState) -> TripWorkflowState:
    started_at = start_timer()
    result = demo_ticket_tool(state.request)
    state.agent_results["ticket"] = result
    record_event(
        state,
        agent="Ticket Agent",
        tool="DemoTicketTool",
        status="success",
        started_at=started_at,
        source_type=result["source_type"],
    )
    return state


def run_food_agent(state: TripWorkflowState) -> TripWorkflowState:
    started_at = start_timer()
    tavily_result = tavily_search_tool(
        query=f"{state.request.destination} 餐饮 推荐 公开攻略",
        category="food",
    )
    fallback = not tavily_result["results"]
    state.agent_results["food"] = {
        "records": tavily_result["results"],
        "fallback_reason": tavily_result["fallback_reason"],
        "source_type": SourceType.demo if fallback else SourceType.tavily,
    }
    record_event(
        state,
        agent="Food Agent",
        tool="TavilySearchTool" if not fallback else "LocalRAGTool",
        status="fallback" if fallback else "success",
        started_at=started_at,
        fallback=fallback,
        error=tavily_result["fallback_reason"] if fallback else None,
        source_type=SourceType.demo if fallback else SourceType.tavily,
    )
    return state


def run_weather_agent(state: TripWorkflowState) -> TripWorkflowState:
    started_at = start_timer()
    state.agent_results["weather"] = {
        "destination": state.request.destination,
        "source_type": SourceType.official_api,
        "note": "Weather is fetched through the backend WeatherTool endpoint when the result page loads.",
    }
    record_event(
        state,
        agent="Weather Agent",
        tool="WeatherTool",
        status="planned",
        started_at=started_at,
        source_type=SourceType.official_api,
    )
    return state


def run_budget_engine(state: TripWorkflowState) -> TripWorkflowState:
    started_at = start_timer()
    result = budget_tool(state.request)
    state.agent_results["budget"] = result
    record_event(
        state,
        agent="Budget Engine",
        tool="BudgetTool",
        status="success",
        started_at=started_at,
        source_type=result["source_type"],
    )
    return state


def run_browser_price_agent(state: TripWorkflowState) -> TripWorkflowState:
    started_at = start_timer()
    result = browser_price_tool(state.request)
    state.agent_results["browser_price"] = result
    status = result.get("status", "failed")
    fallback = status not in {"success", "skipped"}
    record_event(
        state,
        agent="Browser Price Agent",
        tool="BrowserPriceObservationTool",
        status=status,
        started_at=started_at,
        fallback=fallback,
        error=result.get("fallback_reason"),
        source_type=SourceType.browser_observed,
    )
    return state
