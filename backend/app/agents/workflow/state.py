from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any
from uuid import uuid4

from app.models.schemas import AgentExecutionEvent, Itinerary, SourceType, TripRequest


@dataclass
class TripWorkflowState:
    request: TripRequest
    user_id: int | None = None
    request_id: str = field(default_factory=lambda: uuid4().hex)
    trip_id: str | None = None
    structured_requirement: dict[str, Any] = field(default_factory=dict)
    task_plan: dict[str, Any] = field(default_factory=dict)
    agent_results: dict[str, Any] = field(default_factory=dict)
    candidate_itineraries: list[Itinerary] = field(default_factory=list)
    verification_issues: list[str] = field(default_factory=list)
    replan_count: int = 0
    selected_candidate: str | None = None
    locked_items: list[str] = field(default_factory=list)
    rejected_items: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    execution_events: list[AgentExecutionEvent] = field(default_factory=list)
    workflow_backend: str = "sequential_fallback"


def start_timer() -> float:
    return perf_counter()


def record_event(
    state: TripWorkflowState,
    *,
    agent: str,
    status: str,
    started_at: float,
    tool: str | None = None,
    retry_count: int = 0,
    fallback: bool = False,
    error: str | None = None,
    token_usage: dict[str, int] | None = None,
    source_type: SourceType | None = None,
) -> None:
    duration_ms = max(0, int((perf_counter() - started_at) * 1000))
    state.execution_events.append(
        AgentExecutionEvent(
            request_id=state.request_id,
            user_id=state.user_id,
            trip_id=state.trip_id,
            agent=agent,
            tool=tool,
            status=status,
            duration_ms=duration_ms,
            retry_count=retry_count,
            fallback=fallback,
            error=error[:300] if error else None,
            token_usage=token_usage or {},
            source_type=source_type,
        )
    )
