from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.db_models import User
from app.models.schemas import (
    AssistantMessageRequest,
    AssistantMessageResponse,
    ConversationClearResponse,
    ConversationMessagesResponse,
)
from app.services.assistant_service import (
    clear_assistant_messages,
    handle_assistant_message,
    list_assistant_messages,
)


router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/message", response_model=AssistantMessageResponse)
def send_assistant_message(
    request: AssistantMessageRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> AssistantMessageResponse:
    """Send one message to the current trip's controlled AI travel consultant."""
    return handle_assistant_message(
        user_id=current_user.id,
        request=request,
        session=session,
    )


@router.get("/trips/{trip_id}/messages", response_model=ConversationMessagesResponse)
def get_trip_assistant_messages(
    trip_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ConversationMessagesResponse:
    """Read current user's assistant conversation for one trip."""
    return list_assistant_messages(
        user_id=current_user.id,
        trip_id=trip_id,
        session=session,
    )


@router.delete("/trips/{trip_id}/messages", response_model=ConversationClearResponse)
def delete_trip_assistant_messages(
    trip_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ConversationClearResponse:
    """Clear assistant messages for one trip without deleting the trip."""
    return clear_assistant_messages(
        user_id=current_user.id,
        trip_id=trip_id,
        session=session,
    )
