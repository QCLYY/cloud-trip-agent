from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.db_models import HumanConfirmation
from app.models.schemas import HumanConfirmationItem, HumanConfirmationListResponse


ALLOWED_CONFIRMATION_TYPES = {
    "budget_over_limit",
    "uncertain_source",
    "partial_replan",
    "restore_version",
    "lock_item",
    "save_memory",
}

ALLOWED_CONFIRMATION_ACTIONS = {"confirmed", "rejected"}


class InvalidConfirmationTypeError(ValueError):
    pass


class InvalidConfirmationActionError(ValueError):
    pass


def _to_item(record: HumanConfirmation) -> HumanConfirmationItem:
    try:
        payload = json.loads(record.payload_json)
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return HumanConfirmationItem(
        id=record.id,
        trip_id=record.trip_id,
        confirmation_type=record.confirmation_type,
        status=record.status,
        payload=payload,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def create_confirmation(
    user_id: int,
    confirmation_type: str,
    payload: dict[str, Any],
    session: Session,
    trip_id: str | None = None,
) -> HumanConfirmationItem:
    if confirmation_type not in ALLOWED_CONFIRMATION_TYPES:
        raise InvalidConfirmationTypeError(confirmation_type)

    record = HumanConfirmation(
        user_id=user_id,
        trip_id=trip_id,
        confirmation_type=confirmation_type,
        payload_json=json.dumps(payload, ensure_ascii=False),
        status="pending",
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return _to_item(record)


def list_confirmations(
    user_id: int,
    session: Session,
    trip_id: str | None = None,
) -> HumanConfirmationListResponse:
    query = session.query(HumanConfirmation).filter(HumanConfirmation.user_id == user_id)
    if trip_id is not None:
        query = query.filter(HumanConfirmation.trip_id == trip_id)
    records = query.order_by(HumanConfirmation.created_at.desc(), HumanConfirmation.id.desc()).all()
    items = [_to_item(record) for record in records]
    return HumanConfirmationListResponse(total=len(items), items=items)


def update_confirmation_status(
    user_id: int,
    confirmation_id: int,
    action: str,
    session: Session,
) -> HumanConfirmationItem | None:
    if action not in ALLOWED_CONFIRMATION_ACTIONS:
        raise InvalidConfirmationActionError(action)

    record = (
        session.query(HumanConfirmation)
        .filter(
            HumanConfirmation.user_id == user_id,
            HumanConfirmation.id == confirmation_id,
        )
        .first()
    )
    if record is None:
        return None
    record.status = action
    session.commit()
    session.refresh(record)
    return _to_item(record)
