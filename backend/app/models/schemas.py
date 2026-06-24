from __future__ import annotations

from datetime import date as DateType, datetime
from enum import Enum

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """Allowed data source types shown to users and exported files."""

    demo = "demo"
    estimate = "estimate"
    user_input = "user_input"
    tavily = "tavily"
    official_api = "official_api"


class SourceRecord(BaseModel):
    """Traceable source metadata for external or derived itinerary facts."""

    title: str = Field(..., description="Source title")
    url: str | None = Field(default=None, description="Source URL, if any")
    summary: str = Field(..., description="Short source summary")
    queried_at: datetime = Field(default_factory=datetime.utcnow, description="Query time")
    source_type: SourceType = Field(..., description="Source category")
    category: str | None = Field(default=None, description="Business category")


class TripRequest(BaseModel):
    """用于生成新行程的请求体。"""

    destination: str = Field(..., description="目的地，例如大理")
    start_date: DateType = Field(..., description="出行开始日期")
    end_date: DateType = Field(..., description="出行结束日期")
    travelers: int = Field(..., ge=1, description="出行人数")
    budget: float = Field(..., ge=0, description="总预算")
    preferences: list[str] = Field(default_factory=list, description="旅行偏好标签")
    pace: str | None = Field(default=None, description="旅行节奏，例如轻松、适中、紧凑")
    dietary_preferences: list[str] = Field(
        default_factory=list,
        description="饮食偏好或忌口",
    )
    hotel_level: str | None = Field(default=None, description="酒店档次偏好")
    special_notes: str | None = Field(default=None, description="额外要求")


class TripEditRequest(BaseModel):
    """用于修改已有行程的请求体。"""

    trip_id: str = Field(..., description="需要编辑的行程 ID")
    current_itinerary: "Itinerary" = Field(..., description="当前完整 itinerary")
    user_instruction: str = Field(..., description="用户新的修改要求")
    edit_scope: str | None = Field(default=None, description="编辑范围")
    preserve_constraints: list[str] = Field(
        default_factory=list,
        description="需要尽量保留的条件",
    )


class TripSaveRequest(BaseModel):
    """用于保存当前 itinerary 的请求体。"""

    trip_id: str = Field(..., description="需要保存的行程 ID")
    itinerary: "Itinerary" = Field(..., description="完整行程数据")
    user_id: str | None = Field(default=None, description="用户 ID，当前版本可留空")


    change_type: str = Field(default="manual_save", description="Version change type")


class SpotItem(BaseModel):
    """单个景点安排。"""

    name: str = Field(..., description="景点名称")
    start_time: str | None = Field(default=None, description="开始时间")
    end_time: str | None = Field(default=None, description="结束时间")
    description: str | None = Field(default=None, description="景点安排说明")
    estimated_cost: float = Field(default=0.0, ge=0, description="预估花费")
    location: str | None = Field(default=None, description="景点位置描述")
    image_url: str | None = Field(default=None, description="景点图片地址")
    address: str | None = Field(default=None, description="景点详细地址")
    latitude: float | None = Field(default=None, description="景点纬度")
    longitude: float | None = Field(default=None, description="景点经度")
    poi_id: str | None = Field(default=None, description="地图服务返回的 POI 标识")


    source_type: SourceType = Field(default=SourceType.estimate, description="Data source")
    cost_source_type: SourceType = Field(default=SourceType.estimate, description="Cost source")


class MealItem(BaseModel):
    """单个餐饮安排。"""

    name: str = Field(..., description="餐厅或餐饮建议名称")
    meal_type: str = Field(..., description="早餐、午餐、晚餐等")
    estimated_cost: float = Field(default=0.0, ge=0, description="预估花费")
    notes: str | None = Field(default=None, description="补充说明")


    source_type: SourceType = Field(default=SourceType.estimate, description="Data source")
    cost_source_type: SourceType = Field(default=SourceType.estimate, description="Cost source")


class HotelItem(BaseModel):
    """单个住宿安排。"""

    name: str = Field(..., description="酒店名称")
    level: str | None = Field(default=None, description="酒店档次")
    estimated_cost: float = Field(default=0.0, ge=0, description="预估花费")
    location: str | None = Field(default=None, description="酒店位置")
    address: str | None = Field(default=None, description="酒店详细地址")
    latitude: float | None = Field(default=None, description="酒店纬度")
    longitude: float | None = Field(default=None, description="酒店经度")


    source_type: SourceType = Field(default=SourceType.estimate, description="Data source")
    cost_source_type: SourceType = Field(default=SourceType.estimate, description="Cost source")


class TransportItem(BaseModel):
    """单段交通安排。"""

    mode: str = Field(..., description="交通方式，例如步行、打车、公交")
    from_place: str | None = Field(default=None, description="出发地")
    to_place: str | None = Field(default=None, description="目的地")
    estimated_cost: float = Field(default=0.0, ge=0, description="预估花费")
    duration: str | None = Field(default=None, description="预计耗时")
    distance_km: float | None = Field(default=None, ge=0, description="预计距离，单位公里")
    estimated_minutes: int | None = Field(default=None, ge=0, description="预计耗时，单位分钟")


    source_type: SourceType = Field(default=SourceType.estimate, description="Data source")
    cost_source_type: SourceType = Field(default=SourceType.estimate, description="Cost source")


class BudgetBreakdown(BaseModel):
    """预算拆分。"""

    transport: float = Field(default=0.0, ge=0, description="交通预算")
    hotel: float = Field(default=0.0, ge=0, description="住宿预算")
    meals: float = Field(default=0.0, ge=0, description="餐饮预算")
    tickets: float = Field(default=0.0, ge=0, description="门票预算")
    other: float = Field(default=0.0, ge=0, description="其他预算")
    total: float = Field(default=0.0, ge=0, description="预算总计")


    source_type: SourceType = Field(default=SourceType.estimate, description="Budget source")


class DayPlan(BaseModel):
    """单日行程安排。"""

    day_index: int = Field(..., ge=1, description="第几天")
    date: DateType | None = Field(default=None, description="当天日期")
    theme: str | None = Field(default=None, description="当天主题")
    spots: list[SpotItem] = Field(default_factory=list, description="景点安排")
    meals: list[MealItem] = Field(default_factory=list, description="餐饮安排")
    hotel: HotelItem | None = Field(default=None, description="住宿安排")
    transport: list[TransportItem] = Field(default_factory=list, description="交通安排")
    notes: list[str] = Field(default_factory=list, description="补充说明")


class TokenUsage(BaseModel):
    """LLM 调用的 token 消耗统计。"""

    rewrite_prompt_tokens: int = Field(default=0, ge=0, description="Query Rewrite 输入 token")
    rewrite_completion_tokens: int = Field(default=0, ge=0, description="Query Rewrite 输出 token")
    embedding_prompt_tokens: int = Field(default=0, ge=0, description="Query Embedding 输入 token")
    embedding_completion_tokens: int = Field(default=0, ge=0, description="Query Embedding 输出 token")
    planner_prompt_tokens: int = Field(default=0, ge=0, description="行程生成输入 token")
    planner_completion_tokens: int = Field(default=0, ge=0, description="行程生成输出 token")
    rerank_prompt_tokens: int = Field(default=0, ge=0, description="Rerank 输入 token")
    rerank_completion_tokens: int = Field(default=0, ge=0, description="Rerank 输出 token")

    @property
    def total_prompt_tokens(self) -> int:
        return (
            self.rewrite_prompt_tokens
            + self.embedding_prompt_tokens
            + self.planner_prompt_tokens
            + self.rerank_prompt_tokens
        )

    @property
    def total_completion_tokens(self) -> int:
        return (
            self.rewrite_completion_tokens
            + self.embedding_completion_tokens
            + self.planner_completion_tokens
            + self.rerank_completion_tokens
        )

    @property
    def total_tokens(self) -> int:
        return self.total_prompt_tokens + self.total_completion_tokens


class AgentExecutionEvent(BaseModel):
    """Observable Agent or tool execution event, without chain-of-thought."""

    request_id: str = Field(..., description="Request ID")
    user_id: int | None = Field(default=None, description="User ID")
    trip_id: str | None = Field(default=None, description="Trip ID")
    agent: str = Field(..., description="Agent name")
    tool: str | None = Field(default=None, description="Tool name")
    status: str = Field(..., description="Execution status")
    duration_ms: int = Field(default=0, ge=0, description="Duration in milliseconds")
    retry_count: int = Field(default=0, ge=0, description="Retry count")
    fallback: bool = Field(default=False, description="Whether fallback was used")
    error: str | None = Field(default=None, description="Sanitized error reason")
    token_usage: dict[str, int] = Field(default_factory=dict, description="Token usage")
    source_type: SourceType | None = Field(default=None, description="Related source type")


class CandidateItinerary(BaseModel):
    """Candidate itinerary option kept compatible with the main itinerary shape."""

    candidate_id: str = Field(..., description="Candidate ID")
    title: str = Field(..., description="Candidate title")
    strategy: str = Field(..., description="Candidate strategy")
    summary: str = Field(..., description="Candidate summary")
    days: list[DayPlan] = Field(default_factory=list, description="Candidate days")
    estimated_budget: float = Field(default=0.0, ge=0, description="Candidate budget")
    budget_breakdown: BudgetBreakdown = Field(..., description="Candidate budget breakdown")
    differences: list[str] = Field(default_factory=list, description="Main differences")


class Itinerary(BaseModel):
    """完整行程。"""

    trip_id: str = Field(..., description="行程唯一标识")
    destination: str = Field(..., description="目的地")
    summary: str = Field(..., description="整趟行程的概述")
    days: list[DayPlan] = Field(default_factory=list, description="逐日行程")
    estimated_budget: float = Field(default=0.0, ge=0, description="预算总计")
    budget_breakdown: BudgetBreakdown = Field(..., description="预算明细")
    tips: list[str] = Field(default_factory=list, description="旅行建议")
    source_notes: list[str] = Field(
        default_factory=list,
        description="RAG 或规则生成产生的补充说明",
    )
    token_usage: TokenUsage | None = Field(default=None, description="LLM token 消耗统计")


    source_records: list[SourceRecord] = Field(
        default_factory=list,
        description="Traceable source records used by the itinerary",
    )


    execution_events: list[AgentExecutionEvent] = Field(
        default_factory=list,
        description="Observable Agent execution events",
    )
    candidate_itineraries: list[CandidateItinerary] = Field(
        default_factory=list,
        description="Generated candidate itinerary options",
    )


class TripDetailResponse(BaseModel):
    """查询已保存行程时返回的响应体。"""

    trip_id: str = Field(..., description="行程 ID")
    itinerary: Itinerary = Field(..., description="已保存的完整行程")
    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")


class TripSummaryItem(BaseModel):
    """已保存行程的摘要信息。"""

    trip_id: str = Field(..., description="行程 ID")
    destination: str = Field(..., description="目的地")
    summary: str = Field(..., description="行程概述")
    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")


class TripListResponse(BaseModel):
    """行程列表接口的响应结构。"""

    total: int = Field(..., ge=0, description="列表总数")
    items: list[TripSummaryItem] = Field(default_factory=list, description="行程摘要列表")


class TripVersionSummary(BaseModel):
    """Saved itinerary version summary."""

    trip_id: str = Field(..., description="Trip ID")
    version_number: int = Field(..., ge=1, description="Version number")
    change_type: str = Field(..., description="Change type")
    summary: str = Field(..., description="Version summary")
    created_at: datetime | None = Field(default=None, description="Created time")


class TripVersionListResponse(BaseModel):
    """Version list response."""

    trip_id: str = Field(..., description="Trip ID")
    total: int = Field(..., ge=0, description="Version count")
    items: list[TripVersionSummary] = Field(default_factory=list, description="Versions")


class TripVersionDetailResponse(BaseModel):
    """Version detail response."""

    trip_id: str = Field(..., description="Trip ID")
    version_number: int = Field(..., ge=1, description="Version number")
    change_type: str = Field(..., description="Change type")
    itinerary: Itinerary = Field(..., description="Version itinerary snapshot")
    created_at: datetime | None = Field(default=None, description="Created time")


class TripVersionCompareResponse(BaseModel):
    """Simple deterministic version diff response."""

    trip_id: str = Field(..., description="Trip ID")
    from_version: int = Field(..., ge=1, description="Base version")
    to_version: int = Field(..., ge=1, description="Target version")
    differences: list[str] = Field(default_factory=list, description="Detected differences")


class TripVersionRestoreResponse(BaseModel):
    """Restore response. Restoring creates a new current version."""

    trip_id: str = Field(..., description="Trip ID")
    restored_from_version: int = Field(..., ge=1, description="Restored source version")
    new_version_number: int = Field(..., ge=1, description="New current version number")
    itinerary: Itinerary = Field(..., description="Restored itinerary")


class MemorySettingRequest(BaseModel):
    """Enable or disable long-term memory for the current user."""

    enabled: bool = Field(..., description="Whether long-term memory is enabled")


class UserMemoryItem(BaseModel):
    """One explicit stable user preference."""

    id: int = Field(..., ge=1, description="Memory ID")
    memory_type: str = Field(..., description="Memory type")
    content: str = Field(..., description="Memory content")
    created_at: datetime | None = Field(default=None, description="Created time")


class UserMemoryResponse(BaseModel):
    """Current user's long-term memory state."""

    enabled: bool = Field(..., description="Whether memory is enabled")
    items: list[UserMemoryItem] = Field(default_factory=list, description="Saved memories")


class HumanConfirmationRequest(BaseModel):
    """Create a human confirmation request for an allowed decision type."""

    trip_id: str | None = Field(default=None, description="Trip ID")
    confirmation_type: str = Field(..., description="Confirmation type")
    payload: dict[str, object] = Field(default_factory=dict, description="Confirmation payload")


class HumanConfirmationActionRequest(BaseModel):
    """Confirm or reject a pending confirmation."""

    action: str = Field(..., description="confirmed or rejected")


class HumanConfirmationItem(BaseModel):
    """Human confirmation response item."""

    id: int = Field(..., ge=1, description="Confirmation ID")
    trip_id: str | None = Field(default=None, description="Trip ID")
    confirmation_type: str = Field(..., description="Confirmation type")
    status: str = Field(..., description="Status")
    payload: dict[str, object] = Field(default_factory=dict, description="Payload")
    created_at: datetime | None = Field(default=None, description="Created time")
    updated_at: datetime | None = Field(default=None, description="Updated time")


class HumanConfirmationListResponse(BaseModel):
    """List human confirmations."""

    total: int = Field(..., ge=0, description="Total")
    items: list[HumanConfirmationItem] = Field(default_factory=list, description="Items")


class AssistantIntent(str, Enum):
    """Controlled intents supported by the travel consultant."""

    modify_trip = "modify_trip"
    explain_plan = "explain_plan"
    query_trip = "query_trip"
    confirm_action = "confirm_action"
    cancel_action = "cancel_action"
    general_travel_question = "general_travel_question"
    unsupported = "unsupported"


class ConversationRole(str, Enum):
    """Persisted conversation roles."""

    user = "user"
    assistant = "assistant"
    system = "system"


class ConversationMessageType(str, Enum):
    """Persisted assistant message categories."""

    text = "text"
    trip_update = "trip_update"
    explanation = "explanation"
    confirmation = "confirmation"
    error = "error"


class AssistantMessageRequest(BaseModel):
    """User message sent to the AI travel consultant."""

    trip_id: str = Field(..., min_length=1, max_length=100, description="Bound trip ID")
    message: str = Field(..., min_length=1, max_length=1200, description="User message")
    candidate_id: str | None = Field(default=None, max_length=60, description="Candidate option ID")
    confirmation_id: int | None = Field(default=None, ge=1, description="Pending confirmation ID")
    action: str | None = Field(default=None, description="confirmed or rejected")


class ConversationMessageItem(BaseModel):
    """One conversation message returned to the frontend."""

    id: str = Field(..., description="Public message ID")
    conversation_id: str = Field(..., description="Public conversation ID")
    role: ConversationRole = Field(..., description="Message role")
    message_type: ConversationMessageType = Field(..., description="Message type")
    content: str = Field(..., description="Sanitized message content")
    structured_payload: dict[str, object] = Field(default_factory=dict, description="Structured metadata")
    created_at: datetime | None = Field(default=None, description="Created time")


class AssistantMessageResponse(BaseModel):
    """Assistant response for one user message."""

    conversation_id: str = Field(..., description="Public conversation ID")
    message_id: str = Field(..., description="Assistant message ID")
    reply: str = Field(..., description="Assistant reply")
    intent: AssistantIntent = Field(..., description="Detected controlled intent")
    trip_changed: bool = Field(default=False, description="Whether the itinerary changed")
    new_version_number: int | None = Field(default=None, description="Created version number")
    confirmation_required: bool = Field(default=False, description="Whether user confirmation is required")
    execution_events: list[AgentExecutionEvent] = Field(default_factory=list, description="Observable execution")
    itinerary: Itinerary | None = Field(default=None, description="Updated itinerary when changed")
    message: ConversationMessageItem | None = Field(default=None, description="Persisted assistant message")
    source_records: list[SourceRecord] = Field(default_factory=list, description="Sources used by this reply")


class ConversationMessagesResponse(BaseModel):
    """Conversation history bound to one trip."""

    conversation_id: str | None = Field(default=None, description="Public conversation ID")
    trip_id: str = Field(..., description="Trip ID")
    total: int = Field(..., ge=0, description="Message count")
    items: list[ConversationMessageItem] = Field(default_factory=list, description="Messages")


class ConversationClearResponse(BaseModel):
    """Clear conversation messages without deleting the trip."""

    trip_id: str = Field(..., description="Trip ID")
    deleted_count: int = Field(..., ge=0, description="Deleted messages")


class TripTokenStatsItem(BaseModel):
    """单个行程的 token 消耗。"""

    trip_id: str = Field(..., description="行程 ID")
    destination: str = Field(..., description="目的地")
    token_usage: TokenUsage = Field(..., description="token 消耗")


class TokenStatsResponse(BaseModel):
    """Token 消耗统计接口的响应结构。"""

    trip_count: int = Field(..., ge=0, description="统计行程数")
    total_prompt_tokens: int = Field(default=0, ge=0, description="总输入 token")
    total_completion_tokens: int = Field(default=0, ge=0, description="总输出 token")
    total_tokens: int = Field(default=0, ge=0, description="总 token")
    items: list[TripTokenStatsItem] = Field(default_factory=list, description="各行程 token 明细")
