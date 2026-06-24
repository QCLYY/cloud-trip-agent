from __future__ import annotations

from app.models.schemas import BudgetBreakdown, CandidateItinerary, Itinerary, SourceType


def _sum_candidate_budget(candidate: CandidateItinerary) -> CandidateItinerary:
    transport_total = round(
        sum(item.estimated_cost for day in candidate.days for item in day.transport),
        2,
    )
    hotel_total = round(
        sum(day.hotel.estimated_cost for day in candidate.days if day.hotel is not None),
        2,
    )
    meal_total = round(
        sum(item.estimated_cost for day in candidate.days for item in day.meals),
        2,
    )
    ticket_total = round(
        sum(item.estimated_cost for day in candidate.days for item in day.spots),
        2,
    )
    other_total = round(max(0.0, (transport_total + hotel_total + meal_total + ticket_total) * 0.06), 2)
    total = round(transport_total + hotel_total + meal_total + ticket_total + other_total, 2)
    candidate.budget_breakdown = BudgetBreakdown(
        transport=transport_total,
        hotel=hotel_total,
        meals=meal_total,
        tickets=ticket_total,
        other=other_total,
        total=total,
        source_type=SourceType.estimate,
    )
    candidate.estimated_budget = total
    return candidate


def _build_candidate_from_itinerary(
    itinerary: Itinerary,
    candidate_id: str,
    title: str,
    strategy: str,
    summary_suffix: str,
    differences: list[str],
) -> CandidateItinerary:
    return CandidateItinerary(
        candidate_id=candidate_id,
        title=title,
        strategy=strategy,
        summary=f"{itinerary.summary} {summary_suffix}".strip(),
        days=[day.model_copy(deep=True) for day in itinerary.days],
        estimated_budget=itinerary.estimated_budget,
        budget_breakdown=itinerary.budget_breakdown.model_copy(deep=True),
        differences=differences,
    )


def _apply_economy_adjustments(candidate: CandidateItinerary) -> None:
    for day in candidate.days:
        day.notes.append("经济优先：减少打车频率，优先选择公交、步行或短距离组合。")
        for transport in day.transport:
            transport.mode = "公交/步行"
            transport.estimated_cost = round(transport.estimated_cost * 0.55, 2)
            transport.cost_source_type = SourceType.estimate
        if day.hotel is not None:
            day.hotel.level = "经济型"
            day.hotel.name = day.hotel.name.replace("舒适型", "经济型")
            day.hotel.estimated_cost = round(day.hotel.estimated_cost * 0.78, 2)
            day.hotel.cost_source_type = SourceType.estimate
        for meal in day.meals:
            meal.estimated_cost = round(meal.estimated_cost * 0.85, 2)
            meal.cost_source_type = SourceType.estimate


def _apply_balanced_adjustments(candidate: CandidateItinerary) -> None:
    for day in candidate.days:
        day.notes.append("均衡推荐：保留当前景点顺序和舒适度，在预算与体验之间取中。")
        for transport in day.transport:
            transport.cost_source_type = SourceType.estimate
        if day.hotel is not None:
            day.hotel.cost_source_type = SourceType.estimate
        for meal in day.meals:
            meal.cost_source_type = SourceType.estimate


def _apply_experience_adjustments(candidate: CandidateItinerary) -> None:
    if len(candidate.days) > 1:
        candidate.days[0].spots, candidate.days[-1].spots = candidate.days[-1].spots, candidate.days[0].spots
    for day in candidate.days:
        day.notes.append("体验优先：提高餐饮和体验预算，景点顺序更偏向拍照与停留时长。")
        for meal in day.meals:
            meal.estimated_cost = round(meal.estimated_cost * 1.18, 2)
            meal.cost_source_type = SourceType.estimate
        if day.hotel is not None:
            day.hotel.estimated_cost = round(day.hotel.estimated_cost * 1.12, 2)
            day.hotel.cost_source_type = SourceType.estimate


def attach_candidate_itineraries(
    itinerary: Itinerary,
    include_experience: bool = False,
) -> Itinerary:
    """Attach deterministic candidates while preserving the main response shape."""
    economy = _build_candidate_from_itinerary(
        itinerary,
        candidate_id="economy",
        title="经济优先",
        strategy="economy",
        summary_suffix="此候选更重视控制交通、住宿和餐饮预算。",
        differences=[
            "交通：优先公交/步行，减少打车预算。",
            "酒店区域/档次：住宿调整为经济型。",
            "预算分配：餐饮和住宿预算下调。",
        ],
    )
    _apply_economy_adjustments(economy)
    _sum_candidate_budget(economy)

    balanced = _build_candidate_from_itinerary(
        itinerary,
        candidate_id="balanced",
        title="均衡推荐",
        strategy="balanced",
        summary_suffix="此候选保持当前舒适度和节奏。",
        differences=[
            "节奏：保持当前轻松或适中安排。",
            "景点顺序：沿用主行程顺序，减少额外移动。",
            "预算分配：维持住宿、餐饮和交通的均衡比例。",
        ],
    )
    _apply_balanced_adjustments(balanced)
    _sum_candidate_budget(balanced)

    candidates = [economy, balanced]
    if include_experience:
        experience = _build_candidate_from_itinerary(
            itinerary,
            candidate_id="experience",
            title="体验优先",
            strategy="experience",
            summary_suffix="此候选更重视体验、拍照和餐饮质量。",
            differences=[
                "景点顺序：调整首尾景点顺序，偏向体验停留。",
                "餐饮预算：提高特色餐饮预算。",
                "酒店预算：提高住宿舒适度预算。",
            ],
        )
        _apply_experience_adjustments(experience)
        _sum_candidate_budget(experience)
        candidates.append(experience)

    return itinerary.model_copy(update={"candidate_itineraries": candidates})
