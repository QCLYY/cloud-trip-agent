from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, TypedDict

from app.agents.workflow.professional_agents import (
    run_browser_price_agent,
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
ProfessionalAgentNode = Callable[[TripWorkflowState], TripWorkflowState]


class _GraphState(TypedDict):
    state: TripWorkflowState


@dataclass(frozen=True)
class _ProfessionalAgentResult:
    key: str
    state: TripWorkflowState
    error: str | None = None


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
        "origin_city": request.origin_city,
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
                "browser_price",
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
                    "browser_price",
                ]
            },
            "parallel_tasks": [
                "transport",
                "hotel",
                "poi",
                "ticket",
                "food",
                "weather",
                "budget",
                "browser_price",
            ],
            "execution_mode": "parallel_fanout_fanin",
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


def _clone_state_for_parallel_agent(state: TripWorkflowState) -> TripWorkflowState:
    return TripWorkflowState(
        request=state.request,
        user_id=state.user_id,
        request_id=state.request_id,
        trip_id=state.trip_id,
        structured_requirement=dict(state.structured_requirement),
        task_plan=dict(state.task_plan),
        replan_count=state.replan_count,
        selected_candidate=state.selected_candidate,
        locked_items=list(state.locked_items),
        rejected_items=list(state.rejected_items),
        workflow_backend=state.workflow_backend,
    )


def _run_professional_agent_node(
    *,
    key: str,
    label: str,
    node: ProfessionalAgentNode,
    parent_state: TripWorkflowState,
) -> _ProfessionalAgentResult:
    agent_state = _clone_state_for_parallel_agent(parent_state)
    started_at = start_timer()
    try:
        return _ProfessionalAgentResult(key=key, state=node(agent_state))
    except Exception as exc:
        error_message = str(exc) or exc.__class__.__name__
        agent_state.errors.append(f"{key}:{error_message}")
        record_event(
            agent_state,
            agent=label,
            status="failed",
            started_at=started_at,
            fallback=True,
            error=error_message,
        )
        return _ProfessionalAgentResult(
            key=key,
            state=agent_state,
            error=error_message,
        )


def run_professional_agents(state: TripWorkflowState) -> TripWorkflowState:
    started_at = start_timer()
    nodes: tuple[tuple[str, str, ProfessionalAgentNode], ...] = (
        ("transport", "Transport Agent", run_transport_agent),
        ("hotel", "Hotel Agent", run_hotel_agent),
        ("poi", "POI Agent", run_poi_agent),
        ("ticket", "Ticket Agent", run_ticket_agent),
        ("food", "Food Agent", run_food_agent),
        ("weather", "Weather Agent", run_weather_agent),
        ("budget", "Budget Engine", run_budget_engine),
        ("browser_price", "Browser Price Agent", run_browser_price_agent),
    )
    results: dict[str, _ProfessionalAgentResult] = {}
    max_workers = max(1, len(nodes))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _run_professional_agent_node,
                key=key,
                label=label,
                node=node,
                parent_state=state,
            ): key
            for key, label, node in nodes
        }
        for future in as_completed(futures):
            key = futures[future]
            results[key] = future.result()

    for key, _, _ in nodes:
        result = results[key]
        state.agent_results.update(result.state.agent_results)
        state.execution_events.extend(result.state.execution_events)
        state.errors.extend(result.state.errors)

    failed_agents = [key for key, result in results.items() if result.error]
    record_event(
        state,
        agent="Professional Agents",
        status="partial_success" if failed_agents else "success",
        started_at=started_at,
        fallback=bool(failed_agents),
        error=";".join(failed_agents) if failed_agents else None,
    )
    return state


def _cost_source_types_from_days(itinerary: Itinerary) -> list[SourceType]:
    source_types: list[SourceType] = []
    for day in itinerary.days:
        source_types.extend(spot.cost_source_type for spot in day.spots)
        source_types.extend(meal.cost_source_type for meal in day.meals)
        source_types.extend(transport.cost_source_type for transport in day.transport)
        if day.hotel is not None:
            source_types.append(day.hotel.cost_source_type)
    return source_types


def _refresh_budget_from_days(itinerary: Itinerary) -> None:
    transport_total = round(
        sum(item.estimated_cost for day in itinerary.days for item in day.transport),
        2,
    )
    hotel_total = round(
        sum(day.hotel.estimated_cost for day in itinerary.days if day.hotel is not None),
        2,
    )
    meal_total = round(
        sum(item.estimated_cost for day in itinerary.days for item in day.meals),
        2,
    )
    ticket_total = round(
        sum(item.estimated_cost for day in itinerary.days for item in day.spots),
        2,
    )
    other_total = itinerary.budget_breakdown.other
    itinerary.budget_breakdown.transport = transport_total
    itinerary.budget_breakdown.hotel = hotel_total
    itinerary.budget_breakdown.meals = meal_total
    itinerary.budget_breakdown.tickets = ticket_total
    itinerary.budget_breakdown.total = round(
        transport_total + hotel_total + meal_total + ticket_total + other_total,
        2,
    )
    if SourceType.browser_observed in _cost_source_types_from_days(itinerary):
        itinerary.budget_breakdown.source_type = SourceType.browser_observed
    itinerary.estimated_budget = itinerary.budget_breakdown.total


def _apply_browser_price_observations(
    state: TripWorkflowState,
    itinerary: Itinerary,
) -> None:
    result = state.agent_results.get("browser_price", {})
    source_records = result.get("source_records", []) or []
    for record in source_records:
        if isinstance(record, SourceRecord):
            itinerary.source_records.append(record)

    items = result.get("items", []) or []
    if not items:
        if result.get("requires_human"):
            itinerary.tips.append(
                "Browser price observation requires manual login or verification; "
                "the itinerary keeps estimated prices for now."
            )
        return

    applied: list[str] = []
    applied_categories: set[str] = set()
    first_day = itinerary.days[0] if itinerary.days else None
    for item in items:
        amount = item.get("amount")
        if not isinstance(amount, (int, float)):
            continue

        category = item.get("category")
        if category in applied_categories:
            continue
        price_text = item.get("price_text", str(amount))
        if category == "hotel" and first_day and first_day.hotel is not None:
            first_day.hotel.estimated_cost = float(amount)
            first_day.hotel.source_type = SourceType.browser_observed
            first_day.hotel.cost_source_type = SourceType.browser_observed
            applied.append(f"hotel={price_text}")
            applied_categories.add("hotel")
        elif category == "transport" and first_day and first_day.transport:
            first_day.transport[0].estimated_cost = float(amount)
            first_day.transport[0].source_type = SourceType.browser_observed
            first_day.transport[0].cost_source_type = SourceType.browser_observed
            applied.append(f"transport={price_text}")
            applied_categories.add("transport")
        elif category == "ticket" and first_day and first_day.spots:
            first_day.spots[0].estimated_cost = float(amount)
            first_day.spots[0].source_type = SourceType.browser_observed
            first_day.spots[0].cost_source_type = SourceType.browser_observed
            applied.append(f"ticket={price_text}")
            applied_categories.add("ticket")

    if applied:
        _refresh_budget_from_days(itinerary)
        itinerary.source_notes.append(
            "Browser observed prices were applied to itinerary cost fields: "
            + ", ".join(applied[:5])
        )
    else:
        itinerary.source_notes.append(
            "Browser observed visible prices were captured as source records but were not mapped "
            "to a specific itinerary cost field."
        )

    first_url = items[0].get("url") if items else None
    if first_day is not None:
        first_day.notes.append(
            "Browser price observation added visible page prices to this plan; "
            f"source: {first_url or 'submitted page'}."
        )
    itinerary.tips.append(result.get("notice") or "Browser observed prices are visible-page references only.")


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

    _apply_browser_price_observations(state, itinerary)

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
