from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypedDict

from app.agents.workflow.professional_agents import (
    run_budget_engine,
    run_food_agent,
    run_hotel_agent,
    run_poi_agent,
    run_ticket_agent,
    run_transport_agent,
    run_weather_agent,
)
from app.agents.workflow.state import TripWorkflowState, record_event, start_timer
from app.models.schemas import Itinerary, SourceRecord, SourceType, TripRequest


LegacyGenerator = Callable[[TripRequest], Itinerary]


class _GraphState(TypedDict):
    state: TripWorkflowState


def supervisor_entry(state: TripWorkflowState) -> TripWorkflowState:
    started_at = start_timer()
    state.task_plan.setdefault("workflow_entry", "trip_generate")
    record_event(
        state,
        agent="Supervisor Agent",
        status="success",
        started_at=started_at,
    )
    return state


def requirement_agent(state: TripWorkflowState) -> TripWorkflowState:
    started_at = start_timer()
    request = state.request
    state.structured_requirement = {
        "destination": request.destination,
        "start_date": request.start_date.isoformat(),
        "end_date": request.end_date.isoformat(),
        "travelers": request.travelers,
        "budget": request.budget,
        "preferences": list(request.preferences),
        "pace": request.pace,
        "dietary_preferences": list(request.dietary_preferences),
        "hotel_level": request.hotel_level,
        "special_notes": request.special_notes,
    }
    record_event(
        state,
        agent="Requirement Agent",
        status="success",
        started_at=started_at,
        source_type=SourceType.user_input,
    )
    return state


def planner_agent(state: TripWorkflowState) -> TripWorkflowState:
    started_at = start_timer()
    state.task_plan.update(
        {
            "tasks": [
                "transport",
                "hotel",
                "poi",
                "ticket",
                "food",
                "weather",
                "budget",
            ],
            "dependencies": {
                "itinerary_builder": [
                    "transport",
                    "hotel",
                    "poi",
                    "ticket",
                    "food",
                    "weather",
                    "budget",
                ]
            },
            "parallel_tasks": [
                "transport",
                "hotel",
                "poi",
                "ticket",
                "food",
                "weather",
            ],
            "candidate_strategy": ["economy", "balanced"],
        }
    )
    record_event(
        state,
        agent="Planner Agent",
        status="success",
        started_at=started_at,
    )
    return state


def run_professional_agents(state: TripWorkflowState) -> TripWorkflowState:
    for node in (
        run_transport_agent,
        run_hotel_agent,
        run_poi_agent,
        run_ticket_agent,
        run_food_agent,
        run_weather_agent,
        run_budget_engine,
    ):
        state = node(state)
    return state


def itinerary_builder(
    state: TripWorkflowState,
    legacy_generator: LegacyGenerator,
) -> TripWorkflowState:
    started_at = start_timer()
    itinerary = legacy_generator(state.request)
    state.trip_id = itinerary.trip_id

    for key in ("poi", "food"):
        result = state.agent_results.get(key, {})
        for record in result.get("records", []) or []:
            if isinstance(record, SourceRecord):
                itinerary.source_records.append(record)

    itinerary.source_records.append(
        SourceRecord(
            title="LangGraph workflow",
            summary="The itinerary was generated through the internal Supervisor, Requirement, Planner, professional Agent, Builder and Verification workflow.",
            source_type=SourceType.estimate,
            category="agent_workflow",
        )
    )
    state.candidate_itineraries = [itinerary]
    record_event(
        state,
        agent="Itinerary Builder",
        status="success",
        started_at=started_at,
        source_type=SourceType.estimate,
    )
    return state


def verification_agent(state: TripWorkflowState) -> TripWorkflowState:
    started_at = start_timer()
    issues: list[str] = []
    itinerary = state.candidate_itineraries[0] if state.candidate_itineraries else None
    if itinerary is None:
        issues.append("missing_itinerary")
    else:
        if itinerary.estimated_budget > state.request.budget * 1.15:
            issues.append("budget_over_limit")
        if not itinerary.days:
            issues.append("missing_days")
        seen_spots: set[str] = set()
        for day in itinerary.days:
            for spot in day.spots:
                if spot.name in seen_spots:
                    issues.append(f"duplicate_spot:{spot.name}")
                seen_spots.add(spot.name)
                if not spot.source_type:
                    issues.append(f"missing_source:{spot.name}")
            for meal in day.meals:
                if not meal.source_type:
                    issues.append(f"missing_source:{meal.name}")
            if day.hotel and not day.hotel.source_type:
                issues.append(f"missing_source:{day.hotel.name}")
            for transport in day.transport:
                if not transport.source_type:
                    issues.append("missing_source:transport")
    state.verification_issues = issues
    record_event(
        state,
        agent="Verification Agent",
        status="success" if not issues else "needs_replan",
        started_at=started_at,
        error=";".join(issues[:3]) if issues else None,
    )
    return state


def replanner_agent(state: TripWorkflowState) -> TripWorkflowState:
    started_at = start_timer()
    if state.verification_issues and state.replan_count < 2:
        state.replan_count += 1
        state.errors.extend(state.verification_issues)
        status = "fallback"
        fallback = True
    else:
        status = "skipped"
        fallback = False
    record_event(
        state,
        agent="Replanner Agent",
        status=status,
        started_at=started_at,
        fallback=fallback,
        error=";".join(state.verification_issues[:3]) if fallback else None,
    )
    return state


def finalizer_agent(state: TripWorkflowState) -> TripWorkflowState:
    started_at = start_timer()
    state.selected_candidate = "balanced"
    record_event(
        state,
        agent="Finalizer",
        status="success",
        started_at=started_at,
    )
    return state


def _state_to_itinerary(state: TripWorkflowState) -> Itinerary:
    itinerary = state.candidate_itineraries[0]
    itinerary.execution_events = state.execution_events
    return itinerary


def _run_sequential(
    request: TripRequest,
    legacy_generator: LegacyGenerator,
    user_id: int | None,
    backend_name: str,
) -> Itinerary:
    state = TripWorkflowState(request=request, user_id=user_id, workflow_backend=backend_name)
    state = supervisor_entry(state)
    if backend_name != "langgraph":
        started_at = start_timer()
        record_event(
            state,
            agent="Supervisor Agent",
            status="fallback",
            started_at=started_at,
            fallback=True,
            error="langgraph_unavailable",
        )
    state = requirement_agent(state)
    state = planner_agent(state)
    state = run_professional_agents(state)
    state = itinerary_builder(state, legacy_generator)
    state = verification_agent(state)
    state = replanner_agent(state)
    state = finalizer_agent(state)
    return _state_to_itinerary(state)


def _try_run_langgraph(
    request: TripRequest,
    legacy_generator: LegacyGenerator,
    user_id: int | None,
) -> Itinerary | None:
    try:
        from langgraph.graph import END, StateGraph
    except Exception:
        return None

    try:
        def wrap_node(node: Callable[[TripWorkflowState], TripWorkflowState]):
            def wrapped(graph_state: _GraphState) -> _GraphState:
                return {"state": node(graph_state["state"])}

            return wrapped

        def builder_node(graph_state: _GraphState) -> _GraphState:
            return {
                "state": itinerary_builder(
                    graph_state["state"],
                    legacy_generator,
                )
            }

        graph = StateGraph(_GraphState)
        graph.add_node("supervisor", wrap_node(supervisor_entry))
        graph.add_node("requirement", wrap_node(requirement_agent))
        graph.add_node("planner", wrap_node(planner_agent))
        graph.add_node("professional_agents", wrap_node(run_professional_agents))
        graph.add_node("builder", builder_node)
        graph.add_node("verification", wrap_node(verification_agent))
        graph.add_node("replanner", wrap_node(replanner_agent))
        graph.add_node("finalizer", wrap_node(finalizer_agent))
        graph.set_entry_point("supervisor")
        graph.add_edge("supervisor", "requirement")
        graph.add_edge("requirement", "planner")
        graph.add_edge("planner", "professional_agents")
        graph.add_edge("professional_agents", "builder")
        graph.add_edge("builder", "verification")
        graph.add_edge("verification", "replanner")
        graph.add_edge("replanner", "finalizer")
        graph.add_edge("finalizer", END)
        app = graph.compile()
        final_state = app.invoke(
            {
                "state": TripWorkflowState(
                    request=request,
                    user_id=user_id,
                    workflow_backend="langgraph",
                )
            }
        )
        state = final_state["state"]
        return _state_to_itinerary(state)
    except Exception:
        return None


def run_trip_generation_workflow(
    request: TripRequest,
    legacy_generator: LegacyGenerator,
    user_id: int | None = None,
) -> Itinerary:
    itinerary = _try_run_langgraph(request, legacy_generator, user_id=user_id)
    if itinerary is not None:
        return itinerary
    return _run_sequential(
        request,
        legacy_generator,
        user_id=user_id,
        backend_name="sequential_fallback",
    )
