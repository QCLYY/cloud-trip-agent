"""LLM-powered primary assistant with tool-call delegation to sub-agents.

When an LLM API key is configured, this module uses ChatOpenAI with bound
delegation tools to understand user intent and dispatch to sub-agents.
When no LLM is available, AssistantLLMNotAvailable is raised so the caller
can fall back to rule-based intent handling.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from app.agents.assistant.prompts import (
    PRIMARY_ASSISTANT_PROMPT,
    TRAVEL_INFO_PROMPT,
    TRIP_EXPLAINER_PROMPT,
    TRIP_MODIFIER_PROMPT,
    TRIP_QUERY_PROMPT,
)
from app.agents.assistant.tool_models import (
    CompleteOrEscalate,
    ConfirmActionRequest,
    ExplainPlanRequest,
    ModifyTripRequest,
    QueryTripRequest,
    TravelInfoRequest,
)
from app.agents.tools.rag_tool import get_destination_guide_context
from app.agents.tools.tavily_search_tool import search_tavily
from app.config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MAX_RETRIES,
    LLM_MODEL,
    LLM_TIMEOUT_SECONDS,
)
from app.models.schemas import (
    AgentExecutionEvent,
    AssistantIntent,
    Itinerary,
    SourceRecord,
    SourceType,
    TripDetailResponse,
)

logger = logging.getLogger(__name__)

# ── Public exception ──────────────────────────────────────────────────────


class AssistantLLMNotAvailable(Exception):
    """Raised when the LLM is not configured or not reachable."""


# ── Helper: build an LLM client ───────────────────────────────────────────


def _build_llm():
    """Build a ChatOpenAI client from project config. Returns None if not configured."""
    if not LLM_API_KEY:
        return None
    try:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=LLM_MODEL,
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL or None,
            temperature=0.3,
            timeout=LLM_TIMEOUT_SECONDS,
            max_retries=LLM_MAX_RETRIES,
        )
    except Exception as exc:
        logger.warning("Failed to build LLM client: %s", exc)
        return None


# ── Context builders ──────────────────────────────────────────────────────


def _build_itinerary_context(detail: TripDetailResponse) -> str:
    """Render a concise itinerary summary for the LLM context."""
    it = detail.itinerary
    lines = [
        f"目的地：{it.destination}",
        f"行程 ID：{it.trip_id}",
        f"总预算：{it.estimated_budget:.0f} 元",
        f"天数：{len(it.days)} 天",
    ]
    for day in it.days:
        spots = "、".join(s.name for s in day.spots) or "无景点"
        hotel = day.hotel.name if day.hotel else "未安排"
        meals = "、".join(m.name for m in day.meals) or "无餐饮"
        lines.append(
            f"第{day.day_index}天（{day.theme or '无主题'}）："
            f"景点[{spots}]，餐饮[{meals}]，住宿[{hotel}]"
        )
    budget = it.budget_breakdown
    lines.append(
        f"预算明细：交通{budget.transport:.0f} + 住宿{budget.hotel:.0f} + "
        f"餐饮{budget.meals:.0f} + 门票{budget.tickets:.0f} + 其他{budget.other:.0f}"
    )
    if it.candidate_itineraries:
        lines.append("候选方案：")
        for c in it.candidate_itineraries:
            lines.append(f"  - {c.title}：{c.summary[:100]}，预算{c.estimated_budget:.0f}")
    source_count = len(it.source_records)
    if source_count:
        lines.append(f"来源记录：{source_count} 条")
    return "\n".join(lines)


def _build_conversation_summary(history: list[dict[str, str]], max_turns: int = 6) -> str:
    """Build a brief conversation history summary."""
    if not history:
        return "（无历史对话）"
    recent = history[-max_turns:]
    lines = []
    for turn in recent:
        role = "用户" if turn.get("role") == "user" else "顾问"
        content = turn.get("content", "")[:200]
        lines.append(f"{role}：{content}")
    return "\n".join(lines)


# ── Sub-agent executors ──────────────────────────────────────────────────


def _execute_modify(
    instruction: str,
    day_scope: str | None,
    detail: TripDetailResponse,
) -> dict[str, Any]:
    """Handle a ModifyTripRequest tool call.

    Returns structured result that the caller uses to perform the actual edit.
    """
    it = detail.itinerary
    day_info = ""
    if day_scope:
        day_num = int(day_scope.split("_")[1]) if "_" in day_scope else 0
        day = next((d for d in it.days if d.day_index == day_num), None)
        if day:
            day_info = f"第{day.day_index}天：{day.theme or '无主题'}，景点{len(day.spots)}个，餐饮{len(day.meals)}个"

    lines = [
        f"用户要求：{instruction}",
        f"目标范围：{day_scope or '全行程'}",
    ]
    if day_info:
        lines.append(f"当前该天内容：{day_info}")

    return {
        "type": "modify",
        "instruction": instruction,
        "day_scope": day_scope or "day_1",
        "summary": "\n".join(lines),
        "intent": AssistantIntent.modify_trip,
    }


def _execute_query(
    question: str,
    topic: str | None,
    detail: TripDetailResponse,
) -> dict[str, Any]:
    """Handle a QueryTripRequest tool call with deterministic data lookup."""
    it = detail.itinerary
    topic = (topic or "").lower()

    if "预算" in question or "费用" in question or topic == "budget":
        b = it.budget_breakdown
        answer = (
            f"当前行程预估总预算为 {b.total:.0f} 元。"
            f"其中交通 {b.transport:.0f} 元、住宿 {b.hotel:.0f} 元、"
            f"餐饮 {b.meals:.0f} 元、门票 {b.tickets:.0f} 元、其他 {b.other:.0f} 元。"
            "以上为预估参考价，非实时价格。"
        )
    elif "酒店" in question or "住宿" in question or topic == "hotel":
        hotels = [f"{d.hotel.name}（{d.hotel.level or '未标注'}）" for d in it.days if d.hotel]
        answer = "当前住宿安排：" + "；".join(hotels) if hotels else "当前行程暂未安排酒店。"
    elif "交通" in question or topic == "transport":
        items = []
        for d in it.days:
            for t in d.transport:
                items.append(f"第{d.day_index}天：{t.mode} {t.from_place or ''}→{t.to_place or ''}")
        answer = "交通安排：" + "；".join(items) if items else "暂无交通安排。"
    elif "来源" in question or "source" in topic:
        sources = it.source_records[:5]
        answer = (
            "数据来源：" + "；".join(f"{s.title}（{s.source_type.value}）" for s in sources)
            if sources
            else "暂无来源记录。"
        )
    elif "第" in question and "天" in question:
        import re
        match = re.search(r"第\s*(\d+)\s*天", question) or re.search(r"第\s*([一二两三四五六七八九十])\s*天", question)
        if match:
            digits = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
            day_num = int(match.group(1)) if match.group(1).isdigit() else digits.get(match.group(1), 1)
            day = next((d for d in it.days if d.day_index == day_num), None)
            if day:
                spots = "、".join(s.name for s in day.spots) or "无景点"
                meals = "、".join(m.name for m in day.meals) or "无餐饮"
                hotel = day.hotel.name if day.hotel else "未安排"
                answer = (
                    f"第{day.day_index}天（{day.theme or '无主题'}）："
                    f"景点：{spots}；餐饮：{meals}；住宿：{hotel}。"
                )
            else:
                answer = f"第{day_num}天不存在，当前行程共 {len(it.days)} 天。"
        else:
            answer = f"目的地：{it.destination}，共{len(it.days)}天行程，预估总预算{it.estimated_budget:.0f}元。"
    else:
        answer = f"当前行程目的地是 {it.destination}，共 {len(it.days)} 天，预估预算 {it.estimated_budget:.0f} 元。概要：{it.summary}"

    return {
        "type": "query",
        "answer": answer,
        "topic": topic,
        "intent": AssistantIntent.query_trip,
    }


def _execute_explain(
    aspect: str | None,
    candidate_id: str | None,
    detail: TripDetailResponse,
) -> dict[str, Any]:
    """Handle an ExplainPlanRequest tool call."""
    it = detail.itinerary
    candidates = it.candidate_itineraries

    if candidate_id:
        candidate = next((c for c in candidates if c.candidate_id == candidate_id), None)
    else:
        candidate = candidates[0] if candidates else None

    if candidate:
        answer = (
            f"「{candidate.title}」方案说明：{candidate.summary}\n"
            f"预算约 {candidate.estimated_budget:.0f} 元（规则估算，仅供参考）。"
        )
        if candidate.differences:
            answer += "\n与其他方案的主要差异：" + "；".join(candidate.differences[:5])
    else:
        answer = (
            f"当前行程的设计思路是：{it.summary}\n"
            f"预算基于规则估算，共 {it.estimated_budget:.0f} 元。"
            f"你可以说'推荐更经济的方案'来切换候选方案。"
        )

    return {
        "type": "explain",
        "answer": answer,
        "intent": AssistantIntent.explain_plan,
    }


def _execute_travel_info(
    query: str,
    category: str | None,
    detail: TripDetailResponse,
) -> dict[str, Any]:
    """Handle a TravelInfoRequest tool call — Tavily search + local RAG fallback."""
    destination = detail.itinerary.destination
    source_records: list[SourceRecord] = []

    # Try Tavily first
    tavily = search_tavily(query=f"{destination} {query}", category="travel_tip", max_results=3)
    if tavily.results:
        source_records = tavily.results
        answer = (
            f"根据公开旅行信息查询结果：" + "；".join(
                f"{r.title}：{r.summary[:100]}" for r in tavily.results
            )
        )
        answer += "\n\n以上信息为外部检索摘要，请以现场公告或官方发布为准。"
        used_tavily = True
    else:
        # Fallback to local RAG
        contexts, _, _, _ = get_destination_guide_context(
            destination=destination,
            preferences=[query],
            top_k=3,
        )
        if contexts:
            answer = "根据本地旅行攻略：" + "；".join(
                f"{c.get('title', '攻略片段')}：{c.get('text', '')[:100]}" for c in contexts
            )
        else:
            answer = (
                f"关于「{query}」，当前没有检索到足够可靠的公开信息。"
                f"建议查询 {destination} 官方旅游网站或现场游客中心获取最新信息。"
            )
        used_tavily = False

    return {
        "type": "travel_info",
        "answer": answer,
        "source_records": source_records,
        "used_tavily": used_tavily,
        "intent": AssistantIntent.general_travel_question,
    }


def _execute_confirm(
    action: str,
    detail: TripDetailResponse,
) -> dict[str, Any]:
    """Handle a ConfirmActionRequest tool call."""
    is_confirmed = action.lower() in ("confirmed", "confirm", "确认", "同意", "y", "yes")
    answer = (
        "好的，已确认执行该操作。"
        if is_confirmed
        else "好的，已取消该操作。你还可以继续提出其他修改或查询。"
    )
    return {
        "type": "confirm",
        "answer": answer,
        "action": "confirmed" if is_confirmed else "rejected",
        "intent": AssistantIntent.confirm_action if is_confirmed else AssistantIntent.cancel_action,
    }


# ── Primary assistant entry point ─────────────────────────────────────────


def run_primary_assistant(
    user_message: str,
    trip_detail: TripDetailResponse,
    confirmation_id: int | None = None,
    action: str | None = None,
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Run the LLM-powered primary assistant with tool-call delegation.

    Args:
        user_message: The user's latest message.
        trip_detail: The bound trip with full itinerary.
        confirmation_id: Optional pending confirmation ID if user is responding to one.
        action: Optional 'confirmed' or 'rejected' if responding to confirmation.
        conversation_history: List of {role, content} dicts for recent turns.

    Returns:
        A dict with keys: reply, intent, tool_called, sub_result, trip_changed.

    Raises:
        AssistantLLMNotAvailable: If no LLM is configured or reachable.
    """
    llm = _build_llm()
    if llm is None:
        raise AssistantLLMNotAvailable("LLM API key not configured.")

    # Build context
    itinerary_context = _build_itinerary_context(trip_detail)
    history_text = _build_conversation_summary(conversation_history or [])
    current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    system_prompt = PRIMARY_ASSISTANT_PROMPT.format(
        itinerary_context=itinerary_context,
        conversation_history=history_text,
        current_time=current_time,
    )

    # Bind delegation tools
    tools = [
        ModifyTripRequest,
        QueryTripRequest,
        ExplainPlanRequest,
        TravelInfoRequest,
        ConfirmActionRequest,
    ]
    llm_with_tools = llm.bind_tools(tools)

    try:
        response = llm_with_tools.invoke(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}]
        )
    except Exception as exc:
        logger.warning("LLM invocation failed: %s", exc)
        raise AssistantLLMNotAvailable(f"LLM call failed: {exc}") from exc

    # Check for tool calls
    tool_calls = getattr(response, "tool_calls", None)
    if not tool_calls:
        # LLM replied directly (no tool call) — friendly chat or simple answer
        return {
            "reply": response.content or "请问有什么可以帮您？",
            "intent": AssistantIntent.general_travel_question,
            "tool_called": None,
            "sub_result": None,
            "trip_changed": False,
            "source_records": [],
        }

    # Process the first tool call
    first_call = tool_calls[0]
    tool_name = first_call.get("name", "")
    tool_args = first_call.get("args", {})
    sub_result: dict[str, Any] | None = None
    reply = ""

    try:
        if tool_name == "ModifyTripRequest":
            sub_result = _execute_modify(
                instruction=tool_args.get("instruction", user_message),
                day_scope=tool_args.get("day_scope"),
                detail=trip_detail,
            )
            # Modification needs the external edit service — caller handles this
            sub_result["needs_external_edit"] = True
            reply = f"好的，我来帮你调整：{tool_args.get('instruction', '行程')}"

        elif tool_name == "QueryTripRequest":
            sub_result = _execute_query(
                question=tool_args.get("question", user_message),
                topic=tool_args.get("topic"),
                detail=trip_detail,
            )
            reply = sub_result["answer"]

        elif tool_name == "ExplainPlanRequest":
            sub_result = _execute_explain(
                aspect=tool_args.get("aspect"),
                candidate_id=tool_args.get("candidate_id"),
                detail=trip_detail,
            )
            reply = sub_result["answer"]

        elif tool_name == "TravelInfoRequest":
            sub_result = _execute_travel_info(
                query=tool_args.get("query", user_message),
                category=tool_args.get("category"),
                detail=trip_detail,
            )
            reply = sub_result["answer"]

        elif tool_name == "ConfirmActionRequest":
            sub_result = _execute_confirm(
                action=tool_args.get("action", action or "confirmed"),
                detail=trip_detail,
            )
            reply = sub_result["answer"]

        else:
            # Unknown or CompleteOrEscalate — just respond naturally
            reply = response.content or "请问还有什么可以帮您的？"

    except Exception as exc:
        logger.exception("Sub-agent execution failed: %s", exc)
        reply = "抱歉，处理您的请求时遇到了问题。请稍后再试或换一种方式描述您的需求。"
        sub_result = {"type": "error", "error": str(exc)}

    return {
        "reply": reply,
        "intent": sub_result.get("intent", AssistantIntent.general_travel_question) if sub_result else AssistantIntent.general_travel_question,
        "tool_called": tool_name,
        "sub_result": sub_result,
        "trip_changed": False,  # Caller sets this after external edit
        "source_records": sub_result.get("source_records", []) if sub_result else [],
    }
