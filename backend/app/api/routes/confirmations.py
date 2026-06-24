from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.db_models import User
from app.models.schemas import (
    HumanConfirmationActionRequest,
    HumanConfirmationItem,
    HumanConfirmationListResponse,
    HumanConfirmationRequest,
)
from app.services.confirmation_service import (
    InvalidConfirmationActionError,
    InvalidConfirmationTypeError,
    create_confirmation,
    list_confirmations,
    update_confirmation_status,
)


router = APIRouter(prefix="/confirmations", tags=["confirmations"])


@router.get("", response_model=HumanConfirmationListResponse)
def read_confirmations(
    trip_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> HumanConfirmationListResponse:
    """List current user's human confirmations."""
    return list_confirmations(current_user.id, session=session, trip_id=trip_id)


@router.post("", response_model=HumanConfirmationItem, status_code=status.HTTP_201_CREATED)
def create_human_confirmation(
    request: HumanConfirmationRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> HumanConfirmationItem:
    """Create a pending human confirmation for an allowed decision type."""
    try:
        return create_confirmation(
            current_user.id,
            confirmation_type=request.confirmation_type,
            payload=request.payload,
            trip_id=request.trip_id,
            session=session,
        )
    except InvalidConfirmationTypeError as exc:
        raise HTTPException(
            status_code=422,
            detail="Confirmation type is not allowed.",
        ) from exc


@router.post("/{confirmation_id}", response_model=HumanConfirmationItem)
def update_human_confirmation(
    confirmation_id: int,
    request: HumanConfirmationActionRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> HumanConfirmationItem:
    """Confirm or reject a pending confirmation."""
    try:
        result = update_confirmation_status(
            current_user.id,
            confirmation_id=confirmation_id,
            action=request.action,
            session=session,
        )
    except InvalidConfirmationActionError as exc:
        raise HTTPException(status_code=422, detail="Action is not allowed.") from exc

    if result is None:
        raise HTTPException(status_code=404, detail="Confirmation not found.")
    return result
