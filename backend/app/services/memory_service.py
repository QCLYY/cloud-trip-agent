from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.db_models import UserMemoryRecord, UserMemorySetting
from app.models.schemas import TripRequest, UserMemoryItem, UserMemoryResponse


FORBIDDEN_MEMORY_KEYWORDS = (
    "password",
    "密码",
    "token",
    "jwt",
    "api key",
    "apikey",
    "secret",
    "身份证",
    "护照",
    "银行卡",
    "信用卡",
    "支付",
    "支付宝",
    "微信支付",
)

STABLE_NOTE_KEYWORDS = (
    "喜欢",
    "偏好",
    "不喜欢",
    "不吃",
    "少辣",
    "清淡",
    "素食",
    "亲子",
    "老人",
    "轮椅",
)


def _normalize_text(value: str | None, max_length: int = 120) -> str:
    normalized = " ".join((value or "").strip().split())
    return normalized[:max_length]


def _is_safe_memory_content(value: str) -> bool:
    lowered = value.lower()
    return bool(value) and not any(keyword in lowered for keyword in FORBIDDEN_MEMORY_KEYWORDS)


def _get_setting(session: Session, user_id: int) -> UserMemorySetting | None:
    return (
        session.query(UserMemorySetting)
        .filter(UserMemorySetting.user_id == user_id)
        .first()
    )


def is_memory_enabled(user_id: int, session: Session) -> bool:
    setting = _get_setting(session, user_id)
    return bool(setting and setting.enabled)


def set_memory_enabled(user_id: int, enabled: bool, session: Session) -> UserMemoryResponse:
    setting = _get_setting(session, user_id)
    if setting is None:
        setting = UserMemorySetting(user_id=user_id, enabled=1 if enabled else 0)
        session.add(setting)
    else:
        setting.enabled = 1 if enabled else 0
    session.commit()
    return get_user_memory(user_id, session=session)


def get_user_memory(user_id: int, session: Session) -> UserMemoryResponse:
    enabled = is_memory_enabled(user_id, session=session)
    records = (
        session.query(UserMemoryRecord)
        .filter(UserMemoryRecord.user_id == user_id)
        .order_by(UserMemoryRecord.created_at.desc(), UserMemoryRecord.id.desc())
        .all()
    )
    return UserMemoryResponse(
        enabled=enabled,
        items=[
            UserMemoryItem(
                id=record.id,
                memory_type=record.memory_type,
                content=record.content,
                created_at=record.created_at,
            )
            for record in records
        ],
    )


def delete_user_memory(user_id: int, memory_id: int, session: Session) -> bool:
    record = (
        session.query(UserMemoryRecord)
        .filter(UserMemoryRecord.user_id == user_id, UserMemoryRecord.id == memory_id)
        .first()
    )
    if record is None:
        return False
    session.delete(record)
    session.commit()
    return True


def clear_user_memories(user_id: int, session: Session) -> int:
    records = (
        session.query(UserMemoryRecord)
        .filter(UserMemoryRecord.user_id == user_id)
        .all()
    )
    count = len(records)
    for record in records:
        session.delete(record)
    session.commit()
    return count


def _add_unique_memory(
    memories: list[tuple[str, str]],
    memory_type: str,
    content: str | None,
) -> None:
    normalized = _normalize_text(content)
    if not _is_safe_memory_content(normalized):
        return
    item = (memory_type, normalized)
    if item not in memories:
        memories.append(item)


def extract_explicit_memories(request: TripRequest) -> list[tuple[str, str]]:
    """Extract only explicit stable preferences from structured user input."""
    memories: list[tuple[str, str]] = []
    for preference in request.preferences:
        _add_unique_memory(memories, "travel_preference", preference)
    for preference in request.dietary_preferences:
        _add_unique_memory(memories, "dietary_preference", preference)
    _add_unique_memory(memories, "pace", request.pace)
    _add_unique_memory(memories, "hotel_level", request.hotel_level)

    note = _normalize_text(request.special_notes, max_length=160)
    if note and any(keyword in note for keyword in STABLE_NOTE_KEYWORDS):
        _add_unique_memory(memories, "explicit_note", note)
    return memories


def save_explicit_memories(
    user_id: int,
    request: TripRequest,
    session: Session,
) -> None:
    """Save explicit memories only when the user's memory switch is enabled."""
    if not is_memory_enabled(user_id, session=session):
        return

    for memory_type, content in extract_explicit_memories(request):
        session.add(
            UserMemoryRecord(
                user_id=user_id,
                memory_type=memory_type,
                content=content,
            )
        )
        try:
            session.commit()
        except IntegrityError:
            session.rollback()


def add_confirmed_memory(
    user_id: int,
    memory_type: str,
    content: str,
    session: Session,
) -> bool:
    """Save one explicitly confirmed preference only when memory is enabled."""
    if not is_memory_enabled(user_id, session=session):
        return False

    normalized = _normalize_text(content, max_length=160)
    if not _is_safe_memory_content(normalized):
        return False

    session.add(
        UserMemoryRecord(
            user_id=user_id,
            memory_type=memory_type[:50] or "explicit_note",
            content=normalized,
        )
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
    return True


def _merge_unique(base: Iterable[str], extras: Iterable[str]) -> list[str]:
    values: list[str] = []
    for value in [*base, *extras]:
        normalized = _normalize_text(value)
        if normalized and normalized not in values:
            values.append(normalized)
    return values


def apply_memories_to_request(
    user_id: int,
    request: TripRequest,
    session: Session,
) -> TripRequest:
    """Return a request augmented with stored preferences when memory is enabled."""
    if not is_memory_enabled(user_id, session=session):
        return request

    memories = (
        session.query(UserMemoryRecord)
        .filter(UserMemoryRecord.user_id == user_id)
        .all()
    )
    travel_preferences = [
        record.content
        for record in memories
        if record.memory_type in {"travel_preference", "explicit_note"}
    ]
    dietary_preferences = [
        record.content
        for record in memories
        if record.memory_type == "dietary_preference"
    ]
    pace = request.pace or next(
        (record.content for record in memories if record.memory_type == "pace"),
        None,
    )
    hotel_level = request.hotel_level or next(
        (record.content for record in memories if record.memory_type == "hotel_level"),
        None,
    )
    return request.model_copy(
        update={
            "preferences": _merge_unique(request.preferences, travel_preferences),
            "dietary_preferences": _merge_unique(
                request.dietary_preferences,
                dietary_preferences,
            ),
            "pace": pace,
            "hotel_level": hotel_level,
        }
    )
