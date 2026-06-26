from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, TypedDict

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.agents.assistant import AssistantLLMNotAvailable, run_primary_assistant
from app.agents.tools.tavily_search_tool import search_tavily
from app.models.db_models import Conversation, ConversationMessage
from app.models.schemas import (
    AgentExecutionEvent,
    AssistantIntent,
    AssistantMessageRequest,
    AssistantMessageResponse,
    ConversationClearResponse,
    ConversationMessageItem,
    ConversationMessagesResponse,
    ConversationMessageType,
    ConversationRole,
    HumanConfirmationItem,
    Itinerary,
    SourceRecord,
    SourceType,
    TripDetailResponse,
    TripEditRequest,
)
from app.rag.vector_db import search_guide_chunks
from app.services.confirmation_service import (
    InvalidConfirmationActionError,
    create_confirmation,
    update_confirmation_status,
)
from app.services.memory_service import add_confirmed_memory
from app.services.storage_service import (
    get_itinerary_by_trip_id,
    init_db,
    list_trip_versions,
    restore_trip_version,
    save_itinerary,
)
from app.services.trip_service import edit_trip_itinerary


SENSITIVE_KEYWORDS = (
    "password",
    "password_hash",
    "token",
    "jwt",
    "api key",
    "apikey",
    "secret",
    "密码",
    "密钥",
    "令牌",
)

UNSUPPORTED_REPLY = (
    "我只能围绕当前行程提供规划、解释、查询、受控修改和确认操作。"
    "我不能进行预订、支付、退改签、第三方登录或任意网站查询。"
)


@dataclass
class AssistantWorkflowState:
    user_id: int
    request: AssistantMessageRequest
    session: Session
    request_id: str = field(default_factory=lambda: f"assistant_{uuid.uuid4().hex[:12]}")
    trip_detail: TripDetailResponse | None = None
    conversation: Conversation | None = None
    intent: AssistantIntent = AssistantIntent.unsupported
    reply: str = ""
    message_type: ConversationMessageType = ConversationMessageType.text
    structured_payload: dict[str, object] = field(default_factory=dict)
    trip_changed: bool = False
    updated_itinerary: Itinerary | None = None
    new_version_number: int | None = None
    confirmation_required: bool = False
    source_records: list[SourceRecord] = field(default_factory=list)
    execution_events: list[AgentExecutionEvent] = field(default_factory=list)
    assistant_message: ConversationMessageItem | None = None
    # LLM-powered assistant integration
    llm_result: dict[str, Any] | None = None
    llm_used: bool = False
    conversation_history: list[dict[str, str]] = field(default_factory=list)


class _GraphState(TypedDict):
    state: AssistantWorkflowState


def _sanitize_text(value: str) -> str:
    lowered = value.lower()
    if any(keyword in lowered for keyword in SENSITIVE_KEYWORDS):
        return "[敏感信息已隐藏]"
    return value.strip()


def _sanitize_payload(payload: dict[str, object]) -> dict[str, object]:
    text = json.dumps(payload, ensure_ascii=False, default=str).lower()
    if any(keyword in text for keyword in SENSITIVE_KEYWORDS):
        return {"redacted": True}
    return payload


def _event(
    state: AssistantWorkflowState,
    agent: str,
    status_value: str,
    started_at: float,
    *,
    tool: str | None = None,
    fallback: bool = False,
    error: str | None = None,
    source_type: SourceType | None = None,
) -> None:
    state.execution_events.append(
        AgentExecutionEvent(
            request_id=state.request_id,
            user_id=state.user_id,
            trip_id=state.request.trip_id,
            agent=agent,
            tool=tool,
            status=status_value,
            duration_ms=max(0, int((time.perf_counter() - started_at) * 1000)),
            fallback=fallback,
            error=error,
            token_usage={},
            source_type=source_type,
        )
    )


def _new_public_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _message_to_item(record: ConversationMessage, public_conversation_id: str) -> ConversationMessageItem:
    try:
        payload = json.loads(record.structured_payload)
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return ConversationMessageItem(
        id=record.message_id,
        conversation_id=public_conversation_id,
        role=ConversationRole(record.role),
        message_type=ConversationMessageType(record.message_type),
        content=record.content,
        structured_payload=payload,
        created_at=record.created_at,
    )


def _get_or_create_conversation(
    session: Session,
    user_id: int,
    trip_detail: TripDetailResponse,
) -> Conversation:
    conversation = (
        session.query(Conversation)
        .filter(
            Conversation.user_id == user_id,
            Conversation.trip_id == trip_detail.trip_id,
        )
        .first()
    )
    if conversation is not None:
        return conversation

    title = f"{trip_detail.itinerary.destination} AI 旅行顾问"
    conversation = Conversation(
        conversation_id=_new_public_id("conversation"),
        user_id=user_id,
        trip_id=trip_detail.trip_id,
        title=title[:120],
    )
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


def _persist_message(
    session: Session,
    conversation: Conversation,
    user_id: int,
    role: ConversationRole,
    message_type: ConversationMessageType,
    content: str,
    payload: dict[str, object] | None = None,
) -> ConversationMessageItem:
    record = ConversationMessage(
        message_id=_new_public_id("message"),
        conversation_id=conversation.id,
        user_id=user_id,
        role=role.value,
        message_type=message_type.value,
        content=_sanitize_text(content),
        structured_payload=json.dumps(_sanitize_payload(payload or {}), ensure_ascii=False, default=str),
    )
    conversation.updated_at = datetime.utcnow()
    session.add(record)
    session.commit()
    session.refresh(record)
    return _message_to_item(record, conversation.conversation_id)


def _detect_intent(message: str) -> AssistantIntent:
    normalized = message.strip().lower()
    if not normalized:
        return AssistantIntent.unsupported
    if any(keyword in normalized for keyword in ("自动预订", "预订", "支付", "退票", "改签", "取消订单", "登录第三方")):
        return AssistantIntent.unsupported
    if _extract_stable_memory_preference(message):
        return AssistantIntent.confirm_action
    if "恢复" in normalized and "版本" in normalized:
        return AssistantIntent.confirm_action
    if any(keyword in normalized for keyword in ("确认", "同意", "继续", "执行")):
        return AssistantIntent.confirm_action
    if any(keyword in normalized for keyword in ("取消", "不要执行", "先不")):
        return AssistantIntent.cancel_action
    if any(keyword in normalized for keyword in ("改", "换", "不要", "轻松", "预算改", "调整", "安排")):
        return AssistantIntent.modify_trip
    if any(keyword in normalized for keyword in ("为什么", "区别", "推荐", "方案", "候选", "解释")):
        return AssistantIntent.explain_plan
    if any(keyword in normalized for keyword in ("预算", "第", "酒店", "来源", "tavily", "外部检索", "总费用", "有哪些")):
        return AssistantIntent.query_trip
    if any(keyword in normalized for keyword in ("注意", "开放", "餐饮", "景点", "天气", "攻略", "提示")):
        return AssistantIntent.general_travel_question
    return AssistantIntent.unsupported


def _parse_day_scope(message: str, itinerary: Itinerary) -> str | None:
    match = re.search(r"第\s*(\d+)\s*天", message)
    if match:
        day_number = int(match.group(1))
        if any(day.day_index == day_number for day in itinerary.days):
            return f"day_{day_number}"

    chinese_digits = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    match = re.search(r"第\s*([一二两三四五六七八九十])\s*天", message)
    if match:
        day_number = chinese_digits[match.group(1)]
        if any(day.day_index == day_number for day in itinerary.days):
            return f"day_{day_number}"
    return "day_1" if itinerary.days else None


def _latest_version_number(session: Session, trip_id: str, user_id: int) -> int | None:
    versions = list_trip_versions(trip_id, user_id=user_id, session=session)
    if not versions.items:
        return None
    return versions.items[0].version_number


def _execute_modify_trip(state: AssistantWorkflowState) -> None:
    assert state.trip_detail is not None
    started_at = time.perf_counter()
    current_itinerary = state.trip_detail.itinerary
    edit_request = TripEditRequest(
        trip_id=state.trip_detail.trip_id,
        current_itinerary=current_itinerary,
        user_instruction=state.request.message,
        edit_scope=_parse_day_scope(state.request.message, current_itinerary),
        preserve_constraints=["保留目的地、日期、预算结构和已锁定行程项"],
    )
    updated = edit_trip_itinerary(edit_request)
    saved_trip_id = save_itinerary(
        updated,
        user_id=state.user_id,
        session=state.session,
        change_type="assistant_modify",
    )
    if saved_trip_id != updated.trip_id:
        updated = updated.model_copy(update={"trip_id": saved_trip_id})

    state.trip_changed = True
    state.updated_itinerary = updated
    state.new_version_number = _latest_version_number(state.session, saved_trip_id, state.user_id)
    state.reply = (
        "已根据你的要求调整当前行程，并重新计算预算。"
        f"这次修改已保存为版本 {state.new_version_number}。"
    )
    state.message_type = ConversationMessageType.trip_update
    state.structured_payload = {
        "change_summary": state.request.message,
        "new_version_number": state.new_version_number,
        "trip_id": saved_trip_id,
    }
    _event(
        state,
        "AI Travel Consultant",
        "success",
        started_at,
        tool="TripEditService",
        source_type=SourceType.estimate,
    )


def _candidate_for_request(itinerary: Itinerary, candidate_id: str | None):
    candidates = itinerary.candidate_itineraries
    if candidate_id:
        matched = next((candidate for candidate in candidates if candidate.candidate_id == candidate_id), None)
        if matched is not None:
            return matched
    return next((candidate for candidate in candidates if candidate.candidate_id == "balanced"), None) or (
        candidates[0] if candidates else None
    )


def _execute_explain_plan(state: AssistantWorkflowState) -> None:
    assert state.trip_detail is not None
    started_at = time.perf_counter()
    itinerary = state.trip_detail.itinerary
    candidate = _candidate_for_request(itinerary, state.request.candidate_id)
    lines = []
    if candidate is not None:
        lines.append(f"{candidate.title}的推荐逻辑是：{candidate.summary}")
        if candidate.differences:
            lines.append("它和其他方案的主要差异包括：" + "；".join(candidate.differences[:4]) + "。")
        lines.append(f"该方案预算约为 {candidate.estimated_budget:.0f} 元，预算来自确定性规则估算。")
    else:
        lines.append(f"当前行程的核心思路是：{itinerary.summary}")
        lines.append(f"当前预估总预算为 {itinerary.estimated_budget:.0f} 元。")

    source_records = itinerary.source_records[:3]
    if source_records:
        lines.append("我只基于当前行程、候选方案和已保存来源解释，不把演示或检索摘要当作实时价格。")
        lines.append("可追溯来源：" + "；".join(record.title for record in source_records) + "。")

    state.reply = "\n".join(lines)
    state.message_type = ConversationMessageType.explanation
    state.source_records = source_records
    state.structured_payload = {
        "candidate_id": candidate.candidate_id if candidate else None,
        "source_count": len(source_records),
    }
    _event(state, "AI Travel Consultant", "success", started_at, tool="ItineraryReader")


def _format_day_query(itinerary: Itinerary, message: str) -> str | None:
    scope = _parse_day_scope(message, itinerary)
    if not scope:
        return None
    day_number = int(scope.split("_")[1])
    day = next((item for item in itinerary.days if item.day_index == day_number), None)
    if day is None:
        return None
    spot_names = "、".join(spot.name for spot in day.spots) or "未安排景点"
    meal_names = "、".join(meal.name for meal in day.meals) or "未安排餐饮"
    hotel_name = day.hotel.name if day.hotel else "未安排住宿"
    return (
        f"第{day.day_index}天主题是：{day.theme or '未命名主题'}。"
        f"景点：{spot_names}；餐饮：{meal_names}；住宿：{hotel_name}。"
    )


def _execute_query_trip(state: AssistantWorkflowState) -> None:
    assert state.trip_detail is not None
    started_at = time.perf_counter()
    itinerary = state.trip_detail.itinerary
    message = state.request.message.lower()

    if "预算" in message or "总费用" in message:
        budget = itinerary.budget_breakdown
        state.reply = (
            f"当前预估总预算为 {budget.total:.0f} 元。"
            f"其中交通 {budget.transport:.0f} 元、住宿 {budget.hotel:.0f} 元、"
            f"餐饮 {budget.meals:.0f} 元、门票 {budget.tickets:.0f} 元、其他 {budget.other:.0f} 元。"
            "这些数字由后端确定性代码汇总，不是实时价格或可预订库存。"
        )
    elif "来源" in message or "tavily" in message or "外部检索" in message:
        tavily_records = [
            record
            for record in itinerary.source_records
            if record.source_type == SourceType.tavily
        ]
        records = tavily_records or itinerary.source_records[:5]
        if records:
            state.reply = "当前行程来源包括：" + "；".join(
                f"{record.title}（{record.source_type.value}）" for record in records
            )
        else:
            state.reply = "当前行程暂未保存可展示的来源记录。"
        state.source_records = records
    elif "酒店" in message:
        hotels = [day.hotel.name for day in itinerary.days if day.hotel is not None]
        state.reply = "当前住宿安排：" + "；".join(hotels) if hotels else "当前行程暂未安排酒店。"
    else:
        day_reply = _format_day_query(itinerary, state.request.message)
        state.reply = day_reply or f"当前行程目的地是 {itinerary.destination}，概要：{itinerary.summary}"

    state.message_type = ConversationMessageType.text
    state.structured_payload = {"query_type": "deterministic_trip_query"}
    _event(state, "AI Travel Consultant", "success", started_at, tool="ItineraryReader")


def _execute_general_question(state: AssistantWorkflowState) -> None:
    assert state.trip_detail is not None
    started_at = time.perf_counter()
    itinerary = state.trip_detail.itinerary
    query = f"{itinerary.destination} {state.request.message}"
    tavily = search_tavily(query=query, category="travel_tip", max_results=3)
    if tavily.results:
        state.source_records = tavily.results
        state.reply = (
            "我根据受限 Tavily 工具查到这些公开旅行提示："
            + "；".join(f"{record.title}：{record.summary[:80]}" for record in tavily.results)
            + "。这些信息属于外部检索摘要，需要以现场公告或正式 API 为准。"
        )
        source_type = SourceType.tavily
        fallback = False
        tool = "TavilySearchTool"
    else:
        chunks = search_guide_chunks(query, top_k=3)
        state.reply = (
            "我没有使用到可用的 Tavily 结果，已回退到本地攻略："
            + "；".join(f"{chunk['title']}：{chunk['text'][:80]}" for chunk in chunks)
            if chunks
            else "当前没有检索到足够可靠的公开资料，建议以目的地官方公告为准。"
        )
        source_type = SourceType.demo
        fallback = True
        tool = "LocalRAGTool"
    state.message_type = ConversationMessageType.explanation
    state.structured_payload = {
        "source_count": len(state.source_records),
        "fallback_reason": tavily.fallback_reason,
    }
    _event(
        state,
        "AI Travel Consultant",
        "success" if not fallback else "fallback",
        started_at,
        tool=tool,
        fallback=fallback,
        error=tavily.fallback_reason if fallback else None,
        source_type=source_type,
    )


def _parse_version_number(message: str) -> int | None:
    match = re.search(r"版本\s*(\d+)", message)
    if match:
        return int(match.group(1))
    return None


def _extract_stable_memory_preference(message: str) -> str | None:
    normalized = message.strip()
    if not normalized or "这次" in normalized:
        return None
    if any(keyword in normalized for keyword in ("以后", "每次", "每趟", "长期", "都不要", "都喜欢")):
        return _sanitize_text(normalized)
    return None


def _execute_confirmation(state: AssistantWorkflowState) -> None:
    assert state.trip_detail is not None
    started_at = time.perf_counter()
    action = state.request.action
    if action is None and state.intent == AssistantIntent.cancel_action:
        action = "rejected"
    if action is None and state.request.confirmation_id is not None:
        action = "confirmed"

    if state.request.confirmation_id is not None and action is not None:
        try:
            confirmation = update_confirmation_status(
                state.user_id,
                confirmation_id=state.request.confirmation_id,
                action=action,
                session=state.session,
            )
        except InvalidConfirmationActionError as exc:
            raise HTTPException(status_code=422, detail="Invalid confirmation action.") from exc
        if confirmation is None:
            raise HTTPException(status_code=404, detail="Confirmation not found.")
        state.structured_payload = {
            "confirmation_id": confirmation.id,
            "confirmation_type": confirmation.confirmation_type,
            "status": confirmation.status,
        }
        if confirmation.status == "confirmed" and confirmation.confirmation_type == "restore_version":
            version_number = int(confirmation.payload.get("version_number", 1))
            restored = restore_trip_version(
                confirmation.trip_id or state.trip_detail.trip_id,
                version_number,
                user_id=state.user_id,
                session=state.session,
            )
            if restored is not None:
                state.trip_changed = True
                state.updated_itinerary = restored.itinerary
                state.new_version_number = restored.new_version_number
                state.structured_payload["new_version_number"] = restored.new_version_number
                state.reply = f"已确认并恢复到版本 {version_number}，新当前版本为 {restored.new_version_number}。"
            else:
                state.reply = "确认已记录，但没有找到可恢复的版本。"
        elif confirmation.status == "confirmed" and confirmation.confirmation_type == "save_memory":
            saved = add_confirmed_memory(
                user_id=state.user_id,
                memory_type=str(confirmation.payload.get("memory_type") or "explicit_note"),
                content=str(confirmation.payload.get("content") or ""),
                session=state.session,
            )
            state.reply = (
                "已保存为长期旅行偏好。"
                if saved
                else "确认已记录，但长期记忆未开启或内容不适合保存，因此没有写入长期记忆。"
            )
            state.structured_payload["memory_saved"] = saved
        else:
            state.reply = "已确认执行。" if confirmation.status == "confirmed" else "已取消本次受控操作。"
        state.message_type = ConversationMessageType.confirmation
        _event(state, "AI Travel Consultant", "success", started_at, tool="ConfirmationService")
        return

    memory_preference = _extract_stable_memory_preference(state.request.message)
    if memory_preference:
        confirmation = create_confirmation(
            user_id=state.user_id,
            trip_id=state.trip_detail.trip_id,
            confirmation_type="save_memory",
            payload={
                "memory_type": "explicit_note",
                "content": memory_preference,
            },
            session=state.session,
        )
        state.confirmation_required = True
        state.message_type = ConversationMessageType.confirmation
        state.reply = "这看起来像长期旅行偏好。是否确认保存到长期记忆？未确认前我不会写入。"
        state.structured_payload = {
            "confirmation_id": confirmation.id,
            "confirmation_type": confirmation.confirmation_type,
            "memory_type": "explicit_note",
        }
        _event(state, "AI Travel Consultant", "awaiting_confirmation", started_at, tool="ConfirmationService")
        return

    version_number = _parse_version_number(state.request.message)
    if "恢复" in state.request.message and version_number is not None:
        confirmation = create_confirmation(
            user_id=state.user_id,
            trip_id=state.trip_detail.trip_id,
            confirmation_type="restore_version",
            payload={"version_number": version_number},
            session=state.session,
        )
        state.confirmation_required = True
        state.message_type = ConversationMessageType.confirmation
        state.reply = f"恢复到版本 {version_number} 会生成一个新的当前版本。请确认是否继续。"
        state.structured_payload = {
            "confirmation_id": confirmation.id,
            "confirmation_type": confirmation.confirmation_type,
            "version_number": version_number,
        }
        _event(state, "AI Travel Consultant", "awaiting_confirmation", started_at, tool="ConfirmationService")
        return

    state.reply = "当前没有可确认的受控操作。你可以先说明要恢复哪个版本，或在确认卡片中点击确认/取消。"
    state.message_type = ConversationMessageType.confirmation
    _event(state, "AI Travel Consultant", "skipped", started_at, tool="ConfirmationService")


def _execute_unsupported(state: AssistantWorkflowState) -> None:
    started_at = time.perf_counter()
    state.reply = UNSUPPORTED_REPLY
    state.message_type = ConversationMessageType.error
    state.structured_payload = {"reason": "unsupported_intent"}
    _event(state, "AI Travel Consultant", "unsupported", started_at)


# ── LLM-Powered Assistant Integration ─────────────────────────────────────


def _load_conversation_history(state: AssistantWorkflowState) -> AssistantWorkflowState:
    """Load recent conversation messages as context for the LLM assistant."""
    if state.conversation is None:
        state.conversation_history = []
        return state
    try:
        messages = (
            state.session.query(ConversationMessage)
            .filter(
                ConversationMessage.conversation_id == state.conversation.id,
                ConversationMessage.user_id == state.user_id,
            )
            .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
            .limit(10)
            .all()
        )
        history = []
        for msg in reversed(messages):
            history.append({
                "role": msg.role,
                "content": msg.content[:300],
            })
        state.conversation_history = history
    except Exception:
        state.conversation_history = []
    return state


def _try_llm_assistant(state: AssistantWorkflowState) -> AssistantWorkflowState:
    """Try LLM-powered assistant for intent detection and response generation.

    When the user is not responding to an explicit confirmation, this attempts
    to use the LLM with tool-call delegation. On failure, sets llm_used=False
    so the existing rule-based pipeline takes over.
    """
    # Skip LLM when user is responding to a pending confirmation
    if state.request.confirmation_id is not None:
        state.llm_used = False
        return state

    started_at = time.perf_counter()
    try:
        result = run_primary_assistant(
            user_message=state.request.message,
            trip_detail=state.trip_detail,
            conversation_history=state.conversation_history,
        )
        state.llm_result = result
        state.llm_used = True
        _event(state, "AI Travel Consultant (LLM)", "success", started_at,
               tool=result.get("tool_called") or "LLM Direct Reply")
    except AssistantLLMNotAvailable as exc:
        state.llm_used = False
        _event(state, "AI Travel Consultant (LLM)", "fallback",
               started_at, fallback=True, error=str(exc)[:200])
    return state


def _apply_llm_result(state: AssistantWorkflowState) -> AssistantWorkflowState:
    """Apply the LLM sub-agent result to the workflow state.

    Routes the result to the appropriate handler. For modify_trip, calls the
    external edit service. For other intents, uses the LLM-generated reply
    directly.
    """
    if not state.llm_used or state.llm_result is None:
        return state

    result = state.llm_result
    sub = result.get("sub_result") or {}
    tool = result.get("tool_called", "")
    started_at = time.perf_counter()

    state.reply = result.get("reply", "")
    state.intent = result.get("intent", AssistantIntent.general_travel_question)
    state.source_records = result.get("source_records", [])

    if tool == "ModifyTripRequest" and sub.get("needs_external_edit"):
        # Use the existing external edit service
        try:
            current_itinerary = state.trip_detail.itinerary
            edit_request = TripEditRequest(
                trip_id=state.trip_detail.trip_id,
                current_itinerary=current_itinerary,
                user_instruction=sub.get("instruction", state.request.message),
                edit_scope=sub.get("day_scope", "day_1"),
                preserve_constraints=["保留目的地、日期、预算结构和已锁定行程项"],
            )
            updated = edit_trip_itinerary(edit_request)
            saved_trip_id = save_itinerary(
                updated, user_id=state.user_id, session=state.session,
                change_type="assistant_modify",
            )
            if saved_trip_id != updated.trip_id:
                updated = updated.model_copy(update={"trip_id": saved_trip_id})
            state.trip_changed = True
            state.updated_itinerary = updated
            state.new_version_number = _latest_version_number(
                state.session, saved_trip_id, state.user_id
            )
            state.reply = (
                f"{state.reply}\n\n已保存修改，新版本号为 {state.new_version_number}。"
            )
            state.message_type = ConversationMessageType.trip_update
            state.structured_payload = {
                "change_summary": sub.get("instruction", ""),
                "new_version_number": state.new_version_number,
                "trip_id": saved_trip_id,
            }
            _event(state, "AI Travel Consultant", "success", started_at,
                   tool="TripEditService", source_type=SourceType.estimate)
        except Exception as exc:
            state.reply = f"抱歉，修改行程时遇到问题：{exc}。请换个方式描述您的修改需求。"
            state.message_type = ConversationMessageType.error
            _event(state, "AI Travel Consultant", "error", started_at,
                   tool="TripEditService", error=str(exc)[:200])
    elif tool == "TravelInfoRequest":
        state.message_type = ConversationMessageType.explanation
        state.structured_payload = {
            "source_count": len(state.source_records),
            "used_tavily": sub.get("used_tavily", False),
        }
        _event(state, "AI Travel Consultant", "success", started_at,
               tool="TravelInfoAgent",
               source_type=SourceType.tavily if sub.get("used_tavily") else SourceType.demo)
    elif tool == "QueryTripRequest":
        state.message_type = ConversationMessageType.text
        state.structured_payload = {"query_type": "llm_deterministic"}
        _event(state, "AI Travel Consultant", "success", started_at, tool="TripQueryAgent")
    elif tool == "ExplainPlanRequest":
        state.message_type = ConversationMessageType.explanation
        state.structured_payload = {"explanation_type": "llm_explain"}
        _event(state, "AI Travel Consultant", "success", started_at, tool="TripExplainer")
    elif tool == "ConfirmActionRequest":
        state.message_type = ConversationMessageType.confirmation
        state.structured_payload = {"action": sub.get("action", "unknown")}
        state.confirmation_required = False
        _event(state, "AI Travel Consultant", "success", started_at, tool="ConfirmationAgent")
    else:
        # Direct reply from LLM (no tool call) — friendly chat
        state.message_type = ConversationMessageType.text
        state.structured_payload = {"llm_direct": True}

    return state


# ── Original Pipeline Nodes ───────────────────────────────────────────────


def _load_trip_context(state: AssistantWorkflowState) -> AssistantWorkflowState:
    started_at = time.perf_counter()
    init_db(state.session)
    trip_detail = get_itinerary_by_trip_id(
        state.request.trip_id,
        user_id=state.user_id,
        session=state.session,
    )
    if trip_detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found.")
    state.trip_detail = trip_detail
    state.conversation = _get_or_create_conversation(state.session, state.user_id, trip_detail)
    _event(state, "Assistant Context Loader", "success", started_at, tool="TripRepository")
    return state


def _detect_intent_node(state: AssistantWorkflowState) -> AssistantWorkflowState:
    started_at = time.perf_counter()
    if state.request.confirmation_id is not None:
        state.intent = AssistantIntent.cancel_action if state.request.action == "rejected" else AssistantIntent.confirm_action
    else:
        state.intent = _detect_intent(state.request.message)
    _event(state, "Assistant Intent Router", "success", started_at)
    return state


def _execute_intent_node(state: AssistantWorkflowState) -> AssistantWorkflowState:
    if state.intent == AssistantIntent.modify_trip:
        _execute_modify_trip(state)
    elif state.intent == AssistantIntent.explain_plan:
        _execute_explain_plan(state)
    elif state.intent == AssistantIntent.query_trip:
        _execute_query_trip(state)
    elif state.intent in {AssistantIntent.confirm_action, AssistantIntent.cancel_action}:
        _execute_confirmation(state)
    elif state.intent == AssistantIntent.general_travel_question:
        _execute_general_question(state)
    else:
        _execute_unsupported(state)
    return state


def _persist_messages_node(state: AssistantWorkflowState) -> AssistantWorkflowState:
    assert state.conversation is not None
    started_at = time.perf_counter()
    _persist_message(
        state.session,
        state.conversation,
        state.user_id,
        ConversationRole.user,
        ConversationMessageType.text,
        state.request.message,
        {
            "candidate_id": state.request.candidate_id,
            "confirmation_id": state.request.confirmation_id,
            "action": state.request.action,
        },
    )
    state.assistant_message = _persist_message(
        state.session,
        state.conversation,
        state.user_id,
        ConversationRole.assistant,
        state.message_type,
        state.reply,
        {
            **state.structured_payload,
            "intent": state.intent.value,
            "trip_changed": state.trip_changed,
            "confirmation_required": state.confirmation_required,
            "source_records": [
                record.model_dump(mode="json") for record in state.source_records
            ],
        },
    )
    _event(state, "Assistant Message Store", "success", started_at, tool="ConversationRepository")
    return state


def _run_sequential(state: AssistantWorkflowState) -> AssistantWorkflowState:
    state = _load_trip_context(state)
    state = _load_conversation_history(state)
    state = _try_llm_assistant(state)
    if state.llm_used:
        state = _apply_llm_result(state)
    else:
        # Fall back to rule-based intent detection and execution
        state = _detect_intent_node(state)
        state = _execute_intent_node(state)
    return _persist_messages_node(state)


def _run_langgraph(state: AssistantWorkflowState) -> AssistantWorkflowState | None:
    try:
        from langgraph.graph import END, StateGraph
    except Exception:
        return None

    def wrap(node: Callable[[AssistantWorkflowState], AssistantWorkflowState]):
        def wrapped(graph_state: _GraphState) -> _GraphState:
            return {"state": node(graph_state["state"])}

        return wrapped

    graph = StateGraph(_GraphState)
    graph.add_node("load_trip_context", wrap(_load_trip_context))
    graph.add_node("load_history", wrap(_load_conversation_history))
    graph.add_node("try_llm", wrap(_try_llm_assistant))
    graph.add_node("apply_llm", wrap(_apply_llm_result))
    graph.add_node("detect_intent", wrap(_detect_intent_node))
    graph.add_node("execute_intent", wrap(_execute_intent_node))
    graph.add_node("persist_message", wrap(_persist_messages_node))
    graph.set_entry_point("load_trip_context")
    graph.add_edge("load_trip_context", "load_history")
    graph.add_edge("load_history", "try_llm")

    # Conditional: if LLM was used, skip rule-based intent detection
    def _after_llm(graph_state: _GraphState) -> str:
        s = graph_state["state"]
        return "apply_llm" if s.llm_used else "detect_intent"

    graph.add_conditional_edges("try_llm", _after_llm, {
        "apply_llm": "apply_llm",
        "detect_intent": "detect_intent",
    })
    graph.add_edge("apply_llm", "persist_message")
    graph.add_edge("detect_intent", "execute_intent")
    graph.add_edge("execute_intent", "persist_message")
    graph.add_edge("persist_message", END)
    app = graph.compile()
    result = app.invoke({"state": state})
    return result["state"]


def handle_assistant_message(
    user_id: int,
    request: AssistantMessageRequest,
    session: Session,
) -> AssistantMessageResponse:
    state = AssistantWorkflowState(user_id=user_id, request=request, session=session)
    final_state = _run_langgraph(state) or _run_sequential(state)
    assert final_state.conversation is not None
    assert final_state.assistant_message is not None
    return AssistantMessageResponse(
        conversation_id=final_state.conversation.conversation_id,
        message_id=final_state.assistant_message.id,
        reply=final_state.reply,
        intent=final_state.intent,
        trip_changed=final_state.trip_changed,
        new_version_number=final_state.new_version_number,
        confirmation_required=final_state.confirmation_required,
        execution_events=final_state.execution_events,
        itinerary=final_state.updated_itinerary,
        message=final_state.assistant_message,
        source_records=final_state.source_records,
    )


def list_assistant_messages(
    user_id: int,
    trip_id: str,
    session: Session,
) -> ConversationMessagesResponse:
    init_db(session)
    trip_detail = get_itinerary_by_trip_id(trip_id, user_id=user_id, session=session)
    if trip_detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found.")
    conversation = (
        session.query(Conversation)
        .filter(Conversation.user_id == user_id, Conversation.trip_id == trip_id)
        .first()
    )
    if conversation is None:
        return ConversationMessagesResponse(trip_id=trip_id, total=0, items=[])
    messages = (
        session.query(ConversationMessage)
        .filter(
            ConversationMessage.conversation_id == conversation.id,
            ConversationMessage.user_id == user_id,
        )
        .order_by(ConversationMessage.created_at.asc(), ConversationMessage.id.asc())
        .all()
    )
    items = [_message_to_item(message, conversation.conversation_id) for message in messages]
    return ConversationMessagesResponse(
        conversation_id=conversation.conversation_id,
        trip_id=trip_id,
        total=len(items),
        items=items,
    )


def clear_assistant_messages(
    user_id: int,
    trip_id: str,
    session: Session,
) -> ConversationClearResponse:
    init_db(session)
    trip_detail = get_itinerary_by_trip_id(trip_id, user_id=user_id, session=session)
    if trip_detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found.")
    conversation = (
        session.query(Conversation)
        .filter(Conversation.user_id == user_id, Conversation.trip_id == trip_id)
        .first()
    )
    if conversation is None:
        return ConversationClearResponse(trip_id=trip_id, deleted_count=0)
    messages = (
        session.query(ConversationMessage)
        .filter(
            ConversationMessage.conversation_id == conversation.id,
            ConversationMessage.user_id == user_id,
        )
        .all()
    )
    deleted_count = len(messages)
    for message in messages:
        session.delete(message)
    conversation.updated_at = datetime.utcnow()
    session.commit()
    return ConversationClearResponse(trip_id=trip_id, deleted_count=deleted_count)
