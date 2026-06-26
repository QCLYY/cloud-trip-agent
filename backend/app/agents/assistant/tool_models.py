"""Pydantic delegation tool models for the AI travel consultant.

These models are bound as tools on the primary assistant's LLM. When the LLM
emits a tool call matching one of these classes, the routing logic delegates to
the corresponding sub-agent.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CompleteOrEscalate(BaseModel):
    """Finish the current sub-task or escalate back to the primary assistant.

    Call this when you have completed the user's request or when you need the
    primary assistant to take over (e.g. the user changed their mind, the task
    is not your responsibility, or you need additional context).
    """

    reason: str = Field(
        ...,
        description="Why this task is being completed or escalated back to the primary assistant.",
    )


# ── Delegation tools (primary assistant → sub-agent) ──────────────────────


class ModifyTripRequest(BaseModel):
    """Modify the current trip itinerary.

    Use when the user wants to change, adjust, replace, or rearrange any part
    of their itinerary — including swapping spots, changing hotels, adjusting
    pace, reordering days, updating budget allocation, or applying a candidate.
    """

    instruction: str = Field(
        ...,
        description="A concise description of what the user wants to change, including scope "
        "(which day, which item) and the desired outcome.",
    )
    day_scope: str | None = Field(
        default=None,
        description="Target day scope like 'day_1' or 'day_2'. Null means the whole itinerary.",
    )


class QueryTripRequest(BaseModel):
    """Answer a factual question about the current itinerary.

    Use when the user asks about budget breakdown, specific items, sources,
    hotel details, transport arrangements, daily themes, or any other
    factual information that can be read from the trip data.
    """

    question: str = Field(
        ...,
        description="The user's exact question or the topic they want to know about.",
    )
    topic: str | None = Field(
        default=None,
        description="Topic category: budget, hotel, transport, spots, meals, sources, day, or general.",
    )


class ExplainPlanRequest(BaseModel):
    """Explain the reasoning behind the trip plan or a candidate option.

    Use when the user asks 'why', 'what's the difference', 'which is better',
    or wants to understand how the plan was put together.
    """

    aspect: str | None = Field(
        default=None,
        description="What aspect the user wants explained: candidates, budget logic, "
        "day structure, recommendations, or general reasoning.",
    )
    candidate_id: str | None = Field(
        default=None,
        description="If the user is asking about a specific candidate, its ID.",
    )


class TravelInfoRequest(BaseModel):
    """Look up general travel information not specific to the current itinerary.

    Use when the user asks about destination weather, food recommendations,
    opening hours, travel tips, local customs, or any general travel knowledge
    question that requires external search or local RAG retrieval.
    """

    query: str = Field(
        ...,
        description="The specific travel information the user is looking for.",
    )
    category: str | None = Field(
        default=None,
        description="Info category: weather, food, attractions, transport, tips, or policy.",
    )


class ConfirmActionRequest(BaseModel):
    """Handle a user confirmation or cancellation action.

    Use when the user wants to confirm a pending operation (restore version,
    save memory, apply candidate) or cancel it.
    """

    action: str = Field(
        ...,
        description="'confirmed' or 'rejected'.",
    )
    reason: str | None = Field(
        default=None,
        description="Optional reason for the confirmation or rejection.",
    )
