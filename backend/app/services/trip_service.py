from __future__ import annotations

from datetime import date as DateType, timedelta

from app.agents.workflow.trip_workflow import run_trip_generation_workflow
from app.agents.trip_planner_agent import (
    collect_trip_context,
    generate_day_edit_draft,
    generate_planner_draft,
)
from app.config import ENABLE_AMAP_ENRICHMENT
from app.models.schemas import (
    BudgetBreakdown,
    DayPlan,
    HotelItem,
    Itinerary,
    MealItem,
    SourceRecord,
    SourceType,
    SpotItem,
    TokenUsage,
    TransportItem,
    TripEditRequest,
    TripRequest,
)
from app.services.candidate_service import attach_candidate_itineraries
from app.services.map_service import enrich_itinerary_with_map_data


TECHNICAL_TIP_KEYWORDS = (
    "LLM",
    "RAG",
    "LangChain",
    "Chroma",
    "演示",
    "测试",
    "规则",
    "模型",
    "源码",
    "trip_service",
)


def _clean_user_tips(tips: list[str], destination: str | None = None) -> list[str]:
    """过滤内部实现说明，只保留用户真正能用到的旅行建议。"""
    cleaned_tips: list[str] = []
    for tip in tips:
        normalized_tip = tip.strip()
        if not normalized_tip:
            continue
        if any(keyword in normalized_tip for keyword in TECHNICAL_TIP_KEYWORDS):
            continue
        if normalized_tip not in cleaned_tips:
            cleaned_tips.append(normalized_tip)

    if cleaned_tips:
        return cleaned_tips

    place_text = destination or "目的地"
    return [
        f"建议根据{place_text}当天实时天气准备雨具或薄外套，早晚和临水区域体感可能偏凉。",
        "古镇、生态廊道和石板路更适合慢慢走，鞋子尽量选择舒适防滑的款式。",
        "热门景点建议错峰出发，给拍照、用餐和交通预留更从容的缓冲时间。",
    ]


def _build_demo_spot_names(destination: str, rag_contexts: list[str], day_count: int) -> list[str]:
    """从攻略片段里挑出更像样的演示景点名称。"""
    candidate_names: list[str] = []
    joined_context = "\n".join(rag_contexts)
    catalog_names = _get_destination_spot_catalog(destination)

    if catalog_names:
        candidate_names.extend(catalog_names[:day_count])

    if _spot_matches_destination("大理古城", destination) and "大理古城" in joined_context:
        candidate_names.append("大理古城")
    if _spot_matches_destination("喜洲古镇", destination) and "喜洲古镇" in joined_context:
        candidate_names.append("喜洲古镇")
    if _spot_matches_destination("崇圣寺三塔", destination) and "崇圣寺三塔" in joined_context:
        candidate_names.append("崇圣寺三塔")
    if _spot_matches_destination("洱海生态廊道", destination) and "洱海生态廊道" in joined_context:
        candidate_names.append("洱海生态廊道")

    deduped_names: list[str] = []
    for name in candidate_names:
        if name not in deduped_names:
            deduped_names.append(name)
    candidate_names = deduped_names

    while len(candidate_names) < day_count:
        candidate_names.append(f"{destination} 推荐景点 {len(candidate_names) + 1}")

    return candidate_names[:day_count]


DESTINATION_SPOT_CATALOGS = {
    "上海": ["外滩", "豫园", "南京路步行街", "陆家嘴", "上海博物馆", "田子坊"],
    "大理": ["大理古城", "喜洲古镇", "崇圣寺三塔", "洱海生态廊道", "双廊古镇"],
    "成都": ["宽窄巷子", "锦里古街", "武侯祠", "杜甫草堂", "成都大熊猫繁育研究基地"],
    "杭州": ["西湖", "灵隐寺", "河坊街", "西溪湿地", "京杭大运河"],
    "北京": ["故宫博物院", "天安门广场", "颐和园", "什刹海", "国家博物馆"],
    "广州": ["陈家祠", "沙面岛", "广州塔", "越秀公园", "北京路步行街"],
    "深圳": ["莲花山公园", "深圳湾公园", "南头古城", "华侨城创意文化园", "大梅沙海滨公园"],
}

DESTINATION_ALIASES = {
    "上海": ["上海"],
    "大理": ["大理", "云南"],
    "成都": ["成都", "四川"],
    "杭州": ["杭州", "浙江"],
    "北京": ["北京"],
    "广州": ["广州", "广东"],
    "深圳": ["深圳", "广东"],
}


def _get_destination_spot_catalog(destination: str) -> list[str]:
    normalized_destination = destination.strip()
    for city, aliases in DESTINATION_ALIASES.items():
        if any(alias in normalized_destination for alias in aliases):
            return list(DESTINATION_SPOT_CATALOGS.get(city, []))
    return []


def _spot_matches_destination(spot_name: str, destination: str) -> bool:
    normalized_spot = spot_name.strip()
    normalized_destination = destination.strip()
    if not normalized_spot:
        return False
    if normalized_destination and normalized_destination in normalized_spot:
        return True

    current_catalog = _get_destination_spot_catalog(normalized_destination)
    if any(normalized_spot == name or normalized_spot in name or name in normalized_spot for name in current_catalog):
        return True

    for city, spot_names in DESTINATION_SPOT_CATALOGS.items():
        aliases = DESTINATION_ALIASES.get(city, [city])
        destination_matches_city = any(alias in normalized_destination for alias in aliases)
        if destination_matches_city:
            continue
        if any(name in normalized_spot or normalized_spot in name for name in spot_names):
            return False

    return not current_catalog


def _filter_contexts_for_destination(destination: str, rag_contexts: list[str]) -> list[str]:
    filtered_contexts: list[str] = []
    for context in rag_contexts:
        if _spot_matches_destination(context, destination):
            filtered_contexts.append(context)
    return filtered_contexts


def _destination_spot_description(destination: str, spot_name: str) -> str:
    return f"{spot_name}位于{destination}，适合作为当天的核心游览点，行程会围绕该目的地安排交通、用餐和停留时间。"


def _stable_bucket(text: str, modulo: int) -> int:
    """基于文本生成一个稳定桶值，用来做确定性的价格浮动。"""
    return sum(ord(char) for char in text) % modulo if modulo > 0 else 0


def _prorate_amounts(total: float, weights: list[float]) -> list[float]:
    """按权重拆分金额，同时保证拆分后的总和与原总额一致。"""
    if not weights:
        return []

    safe_weights = [max(weight, 0.01) for weight in weights]
    total_cents = max(int(round(total * 100)), 0)
    weight_sum = sum(safe_weights)
    raw_cents = [(total_cents * weight) / weight_sum for weight in safe_weights]
    base_cents = [int(value) for value in raw_cents]
    remainder = total_cents - sum(base_cents)

    ranked_indexes = sorted(
        range(len(raw_cents)),
        key=lambda index: (raw_cents[index] - base_cents[index], -index),
        reverse=True,
    )
    for index in ranked_indexes[:remainder]:
        base_cents[index] += 1

    return [round(value / 100, 2) for value in base_cents]


def _estimate_ticket_cost(spot_name: str, description: str | None = None) -> float:
    """根据景点关键词估算门票，更接近真实行程而不是固定数值。"""
    text = f"{spot_name} {description or ''}"
    bucket = _stable_bucket(text, 4)

    if any(keyword in text for keyword in ("古城", "古镇", "公园", "廊道", "村", "湿地", "街区")):
        return [0.0, 20.0, 30.0, 40.0][bucket]
    if any(keyword in text for keyword in ("寺", "三塔", "博物馆", "遗址", "山庄")):
        return round(60.0 + (bucket * 18.0), 2)
    if any(keyword in text for keyword in ("索道", "缆车", "游船", "演出", "雪山")):
        return round(120.0 + (bucket * 28.0), 2)
    return round(35.0 + (bucket * 12.0), 2)


def _build_hotel_weights(day_count: int, start_date: DateType) -> list[float]:
    """让住宿费用按周末、尾日等因素轻微浮动。"""
    weights: list[float] = []
    for index in range(day_count):
        current_date = start_date + timedelta(days=index)
        weight = 1.0
        if current_date.weekday() in (4, 5):
            weight += 0.18
        if index == day_count - 1:
            weight += 0.08
        if index % 2 == 1:
            weight += 0.05
        weights.append(weight)
    return weights


def _build_meal_weights(day_count: int, preferences: list[str]) -> list[float]:
    """让美食偏好的用户在部分天数获得更高餐饮预算。"""
    foodie_bonus = 0.12 if "美食" in preferences else 0.0
    return [
        1.0 + foodie_bonus + (0.08 if index == day_count // 2 else 0.0) + ((index % 3) * 0.04)
        for index in range(day_count)
    ]


def _build_transport_weights(day_count: int, pace: str | None) -> list[float]:
    """让交通预算随行程节奏和首尾日轻微浮动。"""
    pace_bonus = 0.12 if pace == "紧凑" else -0.04 if pace == "轻松" else 0.04
    return [
        1.0 + pace_bonus + (0.16 if index in (0, day_count - 1) else 0.0) + (index * 0.03)
        for index in range(day_count)
    ]


def _apply_route_based_transport_costs(itinerary: Itinerary) -> None:
    """在已有路线距离时，用路线信息修正交通花费和耗时。"""
    for day in itinerary.days:
        for transport in day.transport:
            if transport.estimated_minutes is not None:
                transport.duration = f"{transport.estimated_minutes} 分钟"

            if transport.distance_km is None:
                continue

            mode = transport.mode or ""
            if "公交" in mode:
                cost = max(2.0, 2.0 + (transport.distance_km * 0.25))
            elif "步行" in mode:
                cost = 0.0
            elif "包车" in mode:
                cost = 30.0 + (transport.distance_km * 3.8)
            else:
                cost = 10.0 + (transport.distance_km * 2.2)

            transport.estimated_cost = round(cost, 2)


def _refresh_budget_breakdown(itinerary: Itinerary, request_budget: float | None = None) -> Itinerary:
    """从具体条目回算预算汇总，避免预算明细显得过于模板化。"""
    _apply_route_based_transport_costs(itinerary)

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

    subtotal = transport_total + hotel_total + meal_total + ticket_total
    if request_budget is not None:
        other_total = round(max(0.0, min(request_budget * 0.12, request_budget - subtotal)), 2)
    else:
        other_total = round(max(subtotal * 0.06, 0.0), 2)

    total = round(subtotal + other_total, 2)
    itinerary.budget_breakdown = BudgetBreakdown(
        transport=transport_total,
        hotel=hotel_total,
        meals=meal_total,
        tickets=ticket_total,
        other=other_total,
        total=total,
        source_type=SourceType.estimate,
    )
    itinerary.estimated_budget = total
    return itinerary


def _maybe_enrich_itinerary_with_map_data(
    itinerary: Itinerary,
    city: str | None = None,
    request_budget: float | None = None,
) -> Itinerary:
    """按开关补充地图信息，并在最后统一刷新预算。"""
    if ENABLE_AMAP_ENRICHMENT:
        try:
            itinerary = enrich_itinerary_with_map_data(itinerary, city=city)
        except Exception:
            pass

    return _refresh_budget_breakdown(itinerary, request_budget=request_budget)


def _generate_trip_itinerary_legacy(request: TripRequest) -> Itinerary:
    """生成完整 itinerary，并使用更真实的预算估算方式。"""
    day_count = (request.end_date - request.start_date).days + 1
    day_count = max(day_count, 1)

    rag_contexts, rewrite_usage, rerank_usage, embedding_usage = collect_trip_context(
        destination=request.destination,
        preferences=request.preferences,
        pace=request.pace,
        special_notes=request.special_notes,
    )
    rag_contexts = _filter_contexts_for_destination(request.destination, rag_contexts)
    llm_draft, planner_usage = generate_planner_draft(request, rag_contexts, day_count)

    token_usage = TokenUsage(
        rewrite_prompt_tokens=rewrite_usage.get("prompt_tokens", 0),
        rewrite_completion_tokens=rewrite_usage.get("completion_tokens", 0),
        embedding_prompt_tokens=embedding_usage.get("prompt_tokens", 0),
        embedding_completion_tokens=embedding_usage.get("completion_tokens", 0),
        planner_prompt_tokens=planner_usage.get("prompt_tokens", 0),
        planner_completion_tokens=planner_usage.get("completion_tokens", 0),
        rerank_prompt_tokens=rerank_usage.get("prompt_tokens", 0),
        rerank_completion_tokens=rerank_usage.get("completion_tokens", 0),
    )
    print(
        "[token_usage] Query Rewrite: "
        f"prompt={token_usage.rewrite_prompt_tokens}, "
        f"completion={token_usage.rewrite_completion_tokens}"
    )
    print(
        "[token_usage] Rerank: "
        f"prompt={token_usage.rerank_prompt_tokens}, "
        f"completion={token_usage.rerank_completion_tokens}"
    )
    print(
        "[token_usage] Query Embedding: "
        f"prompt={token_usage.embedding_prompt_tokens}, "
        f"completion={token_usage.embedding_completion_tokens}"
    )
    print(
        "[token_usage] Planner: "
        f"prompt={token_usage.planner_prompt_tokens}, "
        f"completion={token_usage.planner_completion_tokens}"
    )
    print(
        "[token_usage] Total: "
        f"prompt={token_usage.total_prompt_tokens}, "
        f"completion={token_usage.total_completion_tokens}, "
        f"all={token_usage.total_tokens}"
    )
    fallback_spot_names = _build_demo_spot_names(request.destination, rag_contexts, day_count)

    raw_days: list[dict[str, object]] = []
    ticket_costs: list[float] = []
    for index in range(day_count):
        day_number = index + 1
        current_date = request.start_date + timedelta(days=index)
        llm_day = None
        if llm_draft is not None:
            llm_day = next((item for item in llm_draft.days if item.day_index == day_number), None)

        proposed_spot_name = llm_day.spot_name if llm_day is not None else fallback_spot_names[index]
        spot_name = proposed_spot_name
        replaced_off_destination_spot = False
        if not _spot_matches_destination(spot_name, request.destination):
            spot_name = fallback_spot_names[index]
            replaced_off_destination_spot = True

        theme = llm_day.theme if llm_day is not None and not replaced_off_destination_spot else f"{request.destination} 第 {day_number} 天轻松游"
        spot_description = (
            _destination_spot_description(request.destination, spot_name)
            if replaced_off_destination_spot
            else llm_day.spot_description
            if llm_day is not None
            else "根据本地攻略和旅行偏好安排，适合用半天时间慢慢游览。"
        )
        meal_name = llm_day.meal_name if llm_day is not None else f"{request.destination} 特色餐饮 {day_number}"
        meal_note = (
            llm_day.meal_notes
            if llm_day is not None
            else "根据用户偏好和本地攻略预留的一条餐饮建议。"
        )
        daily_note = (
            f"已将非{request.destination}目的地的景点替换为{spot_name}，避免行程跑偏。"
            if replaced_off_destination_spot
            else llm_day.daily_note
            if llm_day is not None
            else "今天以轻松游览为主，建议根据体力和天气灵活调整停留时间。"
        )
        ticket_cost = _estimate_ticket_cost(spot_name, spot_description)

        raw_days.append(
            {
                "day_index": day_number,
                "date": current_date,
                "theme": theme,
                "spot_name": spot_name,
                "spot_description": spot_description,
                "meal_name": meal_name,
                "meal_note": meal_note,
                "daily_note": daily_note,
                "ticket_cost": ticket_cost,
            }
        )
        ticket_costs.append(ticket_cost)

    ticket_total = round(sum(ticket_costs), 2)
    target_total = request.budget * (
        0.78 if request.pace == "轻松" else 0.92 if request.pace == "紧凑" else 0.85
    )
    other_budget = round(request.budget * (0.05 + min(day_count, 4) * 0.01), 2)
    allocatable_budget = max(target_total - ticket_total - other_budget, request.budget * 0.45)

    hotel_level = request.hotel_level or "舒适型"
    if "豪华" in hotel_level:
        hotel_ratio = 0.62
    elif "高档" in hotel_level or "高端" in hotel_level:
        hotel_ratio = 0.56
    elif "经济" in hotel_level:
        hotel_ratio = 0.40
    else:
        hotel_ratio = 0.50

    meal_ratio = 0.28 if "美食" in request.preferences else 0.22
    transport_ratio = max(0.12, 1 - hotel_ratio - meal_ratio)
    ratio_sum = hotel_ratio + meal_ratio + transport_ratio

    hotel_total = allocatable_budget * hotel_ratio / ratio_sum
    meal_total = allocatable_budget * meal_ratio / ratio_sum
    transport_total = allocatable_budget * transport_ratio / ratio_sum

    daily_hotel_costs = _prorate_amounts(
        hotel_total,
        _build_hotel_weights(day_count, request.start_date),
    )
    daily_meal_costs = _prorate_amounts(
        meal_total,
        _build_meal_weights(day_count, request.preferences),
    )
    daily_transport_costs = _prorate_amounts(
        transport_total,
        _build_transport_weights(day_count, request.pace),
    )

    days: list[DayPlan] = []
    origin_city = request.origin_city or request.destination
    for index, raw_day in enumerate(raw_days):
        spot_name = str(raw_day["spot_name"])
        day_plan = DayPlan(
            day_index=int(raw_day["day_index"]),
            date=raw_day["date"],
            theme=str(raw_day["theme"]),
            spots=[
                SpotItem(
                    name=spot_name,
                    start_time="10:00",
                    end_time="12:00",
                    description=str(raw_day["spot_description"]),
                    estimated_cost=float(raw_day["ticket_cost"]),
                    location=request.destination,
                )
            ],
            meals=[
                MealItem(
                    name=str(raw_day["meal_name"]),
                    meal_type="午餐",
                    estimated_cost=daily_meal_costs[index],
                    notes=str(raw_day["meal_note"]),
                )
            ],
            hotel=HotelItem(
                name=f"{request.destination} {hotel_level}住宿 {index + 1}",
                level=hotel_level,
                estimated_cost=daily_hotel_costs[index],
                location=f"{request.destination} 市区",
            ),
            transport=[
                TransportItem(
                    mode="打车",
                    from_place=f"{origin_city} 出发点" if index == 0 else f"{request.destination} 出发点",
                    to_place=spot_name,
                    estimated_cost=daily_transport_costs[index],
                    duration="30 分钟",
                )
            ],
            notes=[
                f"当前旅行节奏：{request.pace or '适中'}",
                str(raw_day["daily_note"]),
            ],
        )
        days.append(day_plan)

    preference_text = "、".join(request.preferences) if request.preferences else "常规旅行体验"
    source_notes = [
        "Itinerary is assembled by trip_service.py and can optionally use LangChain structured output.",
    ]
    source_notes.extend(rag_contexts[:2])
    source_records = [
        SourceRecord(
            title="Local planning rules and RAG context",
            summary="Initial itinerary structure, costs, hotel choices, meals, tickets and pacing are generated from deterministic rules plus local knowledge context.",
            source_type=SourceType.estimate,
            category="itinerary",
        )
    ]
    for index, context in enumerate(rag_contexts[:3], start=1):
        source_records.append(
            SourceRecord(
                title=f"Local travel guide snippet {index}",
                summary=context[:300],
                source_type=SourceType.demo,
                category="rag",
            )
        )

    tips = (
        llm_draft.tips
        if llm_draft is not None and llm_draft.tips
        else [
            f"建议根据{request.destination}当天实时天气准备雨具或薄外套。",
            "古镇、生态廊道和石板路更适合慢慢走，鞋子尽量选择舒适防滑的款式。",
        ]
    )
    if any("骑行" in context for context in rag_contexts):
        tips.append("本地攻略提到洱海生态廊道适合骑行，可作为第二天或第三天备选。")
    tips = _clean_user_tips(tips, request.destination)

    summary = (
        llm_draft.summary
        if llm_draft is not None
        else f"这是一份为 {request.destination} 生成的 {day_count} 日行程，偏好重点为：{preference_text}。"
    )

    itinerary = Itinerary(
        trip_id=f"trip_{request.destination}_{request.start_date.isoformat()}",
        destination=request.destination,
        summary=summary,
        days=days,
        estimated_budget=0.0,
        budget_breakdown=BudgetBreakdown(),
        tips=tips,
        source_notes=source_notes,
        source_records=source_records,
        token_usage=token_usage,
    )
    return _maybe_enrich_itinerary_with_map_data(
        itinerary,
        city=request.destination,
        request_budget=request.budget,
    )


def generate_trip_itinerary(request: TripRequest, user_id: int | None = None) -> Itinerary:
    """Generate itinerary through the Agent workflow, with legacy fallback."""
    try:
        itinerary = run_trip_generation_workflow(
            request,
            legacy_generator=_generate_trip_itinerary_legacy,
            user_id=user_id,
        )
        itinerary = _maybe_enrich_itinerary_with_map_data(
            itinerary,
            city=request.destination,
            request_budget=request.budget,
        )
        return attach_candidate_itineraries(itinerary, include_experience=True)
    except Exception:
        return attach_candidate_itineraries(_generate_trip_itinerary_legacy(request), include_experience=True)


def edit_trip_itinerary(request: TripEditRequest) -> Itinerary:
    """优先使用 LLM 编辑单日行程，失败时回退到规则编辑。"""
    updated_itinerary = request.current_itinerary.model_copy(deep=True)

    target_day = updated_itinerary.days[0] if updated_itinerary.days else None
    if request.edit_scope and request.edit_scope.startswith("day_"):
        try:
            target_day_index = int(request.edit_scope.split("_")[1])
            matched_day = next(
                (day for day in updated_itinerary.days if day.day_index == target_day_index),
                None,
            )
            if matched_day is not None:
                target_day = matched_day
        except (IndexError, ValueError):
            pass

    llm_edit_applied = False
    edit_token_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    if target_day is not None:
        day_edit_draft, edit_token_usage = generate_day_edit_draft(request, target_day)
        if day_edit_draft is not None:
            target_day.theme = day_edit_draft.theme
            if target_day.spots:
                target_day.spots[0].name = day_edit_draft.spot_name
                target_day.spots[0].description = day_edit_draft.spot_description
                target_day.spots[0].estimated_cost = _estimate_ticket_cost(
                    day_edit_draft.spot_name,
                    day_edit_draft.spot_description,
                )
                target_day.spots[0].address = None
                target_day.spots[0].latitude = None
                target_day.spots[0].longitude = None
                target_day.spots[0].poi_id = None
            if target_day.meals:
                target_day.meals[0].name = day_edit_draft.meal_name
                target_day.meals[0].notes = day_edit_draft.meal_notes

            if target_day.notes:
                target_day.notes[-1] = day_edit_draft.daily_note
            else:
                target_day.notes.append(day_edit_draft.daily_note)

            llm_edit_applied = True
        else:
            if "轻松" in request.user_instruction:
                target_day.theme = f"{target_day.theme}（已调整为更轻松）"
                target_day.notes.append("已根据用户要求把节奏调整得更轻松。")

            if "不要安排" in request.user_instruction and target_day.spots:
                target_day.spots[0].name = "自由活动 / 弹性安排"
                target_day.spots[0].description = "根据用户要求，减少固定景点安排，保留更多自由活动时间。"
                target_day.spots[0].estimated_cost = 0.0
                target_day.spots[0].address = None
                target_day.spots[0].latitude = None
                target_day.spots[0].longitude = None
                target_day.spots[0].poi_id = None

    updated_itinerary.source_notes.append(
        f"已根据用户编辑指令更新行程：{request.user_instruction}"
    )
    updated_itinerary.tips = _clean_user_tips(
        updated_itinerary.tips,
        updated_itinerary.destination,
    )
    updated_itinerary.tips.append("已根据你的修改要求更新目标日期，出发前建议再确认当天交通、天气和景点开放情况。")

    updated_itinerary.token_usage = TokenUsage(
        rewrite_prompt_tokens=0,
        rewrite_completion_tokens=0,
        planner_prompt_tokens=edit_token_usage.get("prompt_tokens", 0),
        planner_completion_tokens=edit_token_usage.get("completion_tokens", 0),
    )

    reference_budget = (
        updated_itinerary.estimated_budget
        or updated_itinerary.budget_breakdown.total
        or None
    )
    return _maybe_enrich_itinerary_with_map_data(
        updated_itinerary,
        city=updated_itinerary.destination,
        request_budget=reference_budget,
    )
