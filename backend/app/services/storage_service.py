from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Query, Session

from app.config import Base, SessionLocal, engine
from app.models.db_models import Conversation, ConversationMessage, HumanConfirmation, TripRecord, TripVersion
from app.models.schemas import (
    Itinerary,
    TokenStatsResponse,
    TokenUsage,
    TripDetailResponse,
    TripListResponse,
    TripSummaryItem,
    TripTokenStatsItem,
    TripVersionCompareResponse,
    TripVersionDetailResponse,
    TripVersionListResponse,
    TripVersionRestoreResponse,
    TripVersionSummary,
)


TRIP_ID_MAX_LENGTH = 100


def _execute_schema_sql(bind, statement: str) -> None:
    if isinstance(bind, Engine):
        with bind.begin() as connection:
            connection.execute(text(statement))
        return

    bind.execute(text(statement))


def _is_duplicate_column_error(exc: OperationalError) -> bool:
    return "duplicate column name" in str(exc).lower()


def _ensure_trip_record_user_id_column(bind) -> None:
    inspector = inspect(bind)
    if "trip_records" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("trip_records")}
    if "user_id" not in columns:
        try:
            _execute_schema_sql(
                bind,
                "ALTER TABLE trip_records ADD COLUMN user_id INTEGER",
            )
        except OperationalError as exc:
            if not _is_duplicate_column_error(exc):
                raise

    _execute_schema_sql(
        bind,
        "CREATE INDEX IF NOT EXISTS ix_trip_records_user_id "
        "ON trip_records (user_id)",
    )


def init_db(session: Session | None = None) -> None:
    """Initialize database tables and apply small SQLite-safe migrations."""
    bind = session.get_bind() if session is not None else engine
    Base.metadata.create_all(bind=bind)
    _ensure_trip_record_user_id_column(bind)


@contextmanager
def _managed_session(session: Session | None = None) -> Iterator[Session]:
    if session is not None:
        yield session
        return

    local_session = SessionLocal()
    try:
        yield local_session
    finally:
        local_session.close()


def _filter_by_user(query: Query, user_id: int | None) -> Query:
    if user_id is None:
        return query
    return query.filter(TripRecord.user_id == user_id)


def _filter_version_by_user(query: Query, user_id: int | None) -> Query:
    if user_id is None:
        return query
    return query.filter(TripVersion.user_id == user_id)


def _filter_confirmation_by_user(query: Query, user_id: int | None) -> Query:
    if user_id is None:
        return query
    return query.filter(HumanConfirmation.user_id == user_id)


def _filter_conversation_by_user(query: Query, user_id: int | None) -> Query:
    if user_id is None:
        return query
    return query.filter(Conversation.user_id == user_id)


def _trip_record_exists(
    session: Session,
    trip_id: str,
    user_id: int | None,
) -> bool:
    query = session.query(TripRecord).filter(TripRecord.trip_id == trip_id)
    return _filter_by_user(query, user_id).first() is not None


def _next_trip_version_number(
    session: Session,
    trip_id: str,
    user_id: int | None,
) -> int:
    query = session.query(TripVersion).filter(TripVersion.trip_id == trip_id)
    latest_version = (
        _filter_version_by_user(query, user_id)
        .order_by(TripVersion.version_number.desc())
        .first()
    )
    if latest_version is None:
        return 1
    return latest_version.version_number + 1


def _create_trip_version(
    session: Session,
    itinerary: Itinerary,
    user_id: int | None,
    change_type: str,
) -> TripVersion:
    version_number = _next_trip_version_number(session, itinerary.trip_id, user_id)
    itinerary_json = json.dumps(
        itinerary.model_dump(mode="json"),
        ensure_ascii=False,
    )
    version = TripVersion(
        user_id=user_id,
        trip_id=itinerary.trip_id,
        version_number=version_number,
        change_type=change_type[:50] or "manual_save",
        summary=itinerary.summary,
        itinerary_json=itinerary_json,
    )
    session.add(version)
    return version


def _append_trip_id_suffix(base_trip_id: str, suffix: str) -> str:
    max_base_length = max(1, TRIP_ID_MAX_LENGTH - len(suffix))
    return f"{base_trip_id[:max_base_length]}{suffix}"


def _resolve_trip_id_for_user(
    session: Session,
    trip_id: str,
    user_id: int | None,
) -> str:
    if user_id is None:
        return trip_id

    existing_record = (
        session.query(TripRecord)
        .filter(TripRecord.trip_id == trip_id)
        .first()
    )
    if existing_record is None or existing_record.user_id == user_id:
        return trip_id

    user_scoped_trip_id = _append_trip_id_suffix(trip_id, f"_u{user_id}")
    user_scoped_record = (
        session.query(TripRecord)
        .filter(TripRecord.trip_id == user_scoped_trip_id)
        .first()
    )
    if user_scoped_record is None or user_scoped_record.user_id == user_id:
        return user_scoped_trip_id

    return _append_trip_id_suffix(
        trip_id,
        f"_u{user_id}_{uuid.uuid4().hex[:8]}",
    )


def save_itinerary(
    itinerary: Itinerary,
    user_id: int | None = None,
    session: Session | None = None,
    change_type: str = "manual_save",
    create_version: bool = True,
) -> str:
    """Save or update an itinerary and return the persisted trip_id."""
    init_db(session)

    with _managed_session(session) as active_session:
        saved_trip_id = _resolve_trip_id_for_user(
            active_session,
            itinerary.trip_id,
            user_id,
        )
        stored_itinerary = itinerary.model_copy(update={"trip_id": saved_trip_id})
        itinerary_json = json.dumps(
            stored_itinerary.model_dump(mode="json"),
            ensure_ascii=False,
        )

        existing_query = active_session.query(TripRecord).filter(
            TripRecord.trip_id == saved_trip_id,
        )
        existing_record = _filter_by_user(existing_query, user_id).first()

        if existing_record is None:
            record = TripRecord(
                user_id=user_id,
                trip_id=saved_trip_id,
                destination=stored_itinerary.destination,
                summary=stored_itinerary.summary,
                itinerary_json=itinerary_json,
            )
            active_session.add(record)
        else:
            existing_record.destination = stored_itinerary.destination
            existing_record.summary = stored_itinerary.summary
            existing_record.itinerary_json = itinerary_json

        if create_version:
            _create_trip_version(
                active_session,
                stored_itinerary,
                user_id=user_id,
                change_type=change_type,
            )

        active_session.commit()
        return saved_trip_id


def get_itinerary_by_trip_id(
    trip_id: str,
    user_id: int | None = None,
    session: Session | None = None,
) -> TripDetailResponse | None:
    """Read an itinerary by trip_id, optionally restricted to one user."""
    init_db(session)

    with _managed_session(session) as active_session:
        query = active_session.query(TripRecord).filter(TripRecord.trip_id == trip_id)
        record = _filter_by_user(query, user_id).first()
        if record is None:
            return None

        itinerary_data = json.loads(record.itinerary_json)
        itinerary = Itinerary(**itinerary_data)

        return TripDetailResponse(
            trip_id=record.trip_id,
            itinerary=itinerary,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


def list_saved_itineraries(
    user_id: int | None = None,
    session: Session | None = None,
) -> TripListResponse:
    """Return saved itinerary summaries, optionally restricted to one user."""
    init_db(session)

    with _managed_session(session) as active_session:
        query = active_session.query(TripRecord)
        records = (
            _filter_by_user(query, user_id)
            .order_by(TripRecord.updated_at.desc(), TripRecord.id.desc())
            .all()
        )

        items = [
            TripSummaryItem(
                trip_id=record.trip_id,
                destination=record.destination,
                summary=record.summary,
                created_at=record.created_at,
                updated_at=record.updated_at,
            )
            for record in records
        ]
        return TripListResponse(total=len(items), items=items)


def list_trip_versions(
    trip_id: str,
    user_id: int | None = None,
    session: Session | None = None,
) -> TripVersionListResponse:
    """Return version summaries for one trip, optionally restricted to one user."""
    init_db(session)

    with _managed_session(session) as active_session:
        if not _trip_record_exists(active_session, trip_id, user_id):
            return TripVersionListResponse(trip_id=trip_id, total=0, items=[])

        query = active_session.query(TripVersion).filter(TripVersion.trip_id == trip_id)
        versions = (
            _filter_version_by_user(query, user_id)
            .order_by(TripVersion.version_number.desc())
            .all()
        )
        items = [
            TripVersionSummary(
                trip_id=version.trip_id,
                version_number=version.version_number,
                change_type=version.change_type,
                summary=version.summary,
                created_at=version.created_at,
            )
            for version in versions
        ]
        return TripVersionListResponse(trip_id=trip_id, total=len(items), items=items)


def get_trip_version(
    trip_id: str,
    version_number: int,
    user_id: int | None = None,
    session: Session | None = None,
) -> TripVersionDetailResponse | None:
    """Read one immutable trip version."""
    init_db(session)

    with _managed_session(session) as active_session:
        if not _trip_record_exists(active_session, trip_id, user_id):
            return None

        query = active_session.query(TripVersion).filter(
            TripVersion.trip_id == trip_id,
            TripVersion.version_number == version_number,
        )
        version = _filter_version_by_user(query, user_id).first()
        if version is None:
            return None

        return TripVersionDetailResponse(
            trip_id=version.trip_id,
            version_number=version.version_number,
            change_type=version.change_type,
            itinerary=Itinerary(**json.loads(version.itinerary_json)),
            created_at=version.created_at,
        )


def _first_spot_names(itinerary: Itinerary) -> list[str]:
    return [
        day.spots[0].name if day.spots else ""
        for day in itinerary.days
    ]


def _day_themes(itinerary: Itinerary) -> list[str]:
    return [day.theme or "" for day in itinerary.days]


def _diff_itineraries(base: Itinerary, target: Itinerary) -> list[str]:
    differences: list[str] = []
    if base.destination != target.destination:
        differences.append(f"destination: {base.destination} -> {target.destination}")
    if base.summary != target.summary:
        differences.append("summary changed")
    if len(base.days) != len(target.days):
        differences.append(f"day_count: {len(base.days)} -> {len(target.days)}")
    if round(base.estimated_budget, 2) != round(target.estimated_budget, 2):
        differences.append(
            f"estimated_budget: {base.estimated_budget:.2f} -> {target.estimated_budget:.2f}"
        )
    if _day_themes(base) != _day_themes(target):
        differences.append("day themes changed")
    if _first_spot_names(base) != _first_spot_names(target):
        differences.append("main spots changed")
    return differences or ["no deterministic differences detected"]


def compare_trip_versions(
    trip_id: str,
    from_version: int,
    to_version: int,
    user_id: int | None = None,
    session: Session | None = None,
) -> TripVersionCompareResponse | None:
    """Compare two versions using deterministic Python checks."""
    base_version = get_trip_version(trip_id, from_version, user_id=user_id, session=session)
    target_version = get_trip_version(trip_id, to_version, user_id=user_id, session=session)
    if base_version is None or target_version is None:
        return None
    return TripVersionCompareResponse(
        trip_id=trip_id,
        from_version=from_version,
        to_version=to_version,
        differences=_diff_itineraries(base_version.itinerary, target_version.itinerary),
    )


def restore_trip_version(
    trip_id: str,
    version_number: int,
    user_id: int | None = None,
    session: Session | None = None,
) -> TripVersionRestoreResponse | None:
    """Restore a version and create a new current version snapshot."""
    init_db(session)

    with _managed_session(session) as active_session:
        if not _trip_record_exists(active_session, trip_id, user_id):
            return None

        query = active_session.query(TripVersion).filter(
            TripVersion.trip_id == trip_id,
            TripVersion.version_number == version_number,
        )
        version = _filter_version_by_user(query, user_id).first()
        if version is None:
            return None

        itinerary = Itinerary(**json.loads(version.itinerary_json))
        restored_trip_id = save_itinerary(
            itinerary,
            user_id=user_id,
            session=active_session,
            change_type=f"restore_v{version_number}",
            create_version=True,
        )
        latest_number = _next_trip_version_number(active_session, restored_trip_id, user_id) - 1
        return TripVersionRestoreResponse(
            trip_id=restored_trip_id,
            restored_from_version=version_number,
            new_version_number=latest_number,
            itinerary=itinerary.model_copy(update={"trip_id": restored_trip_id}),
        )


def get_token_stats(
    user_id: int | None = None,
    session: Session | None = None,
) -> TokenStatsResponse:
    """Return token usage stats, optionally restricted to one user."""
    init_db(session)

    with _managed_session(session) as active_session:
        query = active_session.query(TripRecord)
        records = (
            _filter_by_user(query, user_id)
            .order_by(TripRecord.updated_at.desc(), TripRecord.id.desc())
            .all()
        )

        items: list[TripTokenStatsItem] = []
        total_prompt = 0
        total_completion = 0

        for record in records:
            itinerary_data = json.loads(record.itinerary_json)
            itinerary = Itinerary(**itinerary_data)
            usage = itinerary.token_usage
            if usage is None:
                usage = TokenUsage()

            items.append(
                TripTokenStatsItem(
                    trip_id=record.trip_id,
                    destination=record.destination,
                    token_usage=usage,
                )
            )
            total_prompt += usage.total_prompt_tokens
            total_completion += usage.total_completion_tokens

        return TokenStatsResponse(
            trip_count=len(items),
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_completion,
            total_tokens=total_prompt + total_completion,
            items=items,
        )


def delete_itinerary_by_trip_id(
    trip_id: str,
    user_id: int | None = None,
    session: Session | None = None,
) -> bool:
    """Delete an itinerary by trip_id, optionally restricted to one user."""
    init_db(session)

    with _managed_session(session) as active_session:
        query = active_session.query(TripRecord).filter(TripRecord.trip_id == trip_id)
        record = _filter_by_user(query, user_id).first()
        if record is None:
            return False

        version_query = active_session.query(TripVersion).filter(
            TripVersion.trip_id == trip_id,
        )
        _filter_version_by_user(version_query, user_id).delete(synchronize_session=False)

        confirmation_query = active_session.query(HumanConfirmation).filter(
            HumanConfirmation.trip_id == trip_id,
        )
        _filter_confirmation_by_user(confirmation_query, user_id).delete(
            synchronize_session=False,
        )

        conversation_query = active_session.query(Conversation).filter(
            Conversation.trip_id == trip_id,
        )
        conversations = _filter_conversation_by_user(conversation_query, user_id).all()
        for conversation in conversations:
            active_session.query(ConversationMessage).filter(
                ConversationMessage.conversation_id == conversation.id,
            ).delete(synchronize_session=False)
            active_session.delete(conversation)

        active_session.delete(record)
        active_session.commit()
        return True
