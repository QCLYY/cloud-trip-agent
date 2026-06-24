from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.db_models import User
from app.models.schemas import MemorySettingRequest, UserMemoryResponse
from app.services.memory_service import (
    clear_user_memories,
    delete_user_memory,
    get_user_memory,
    set_memory_enabled,
)


router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("", response_model=UserMemoryResponse)
def read_memory(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> UserMemoryResponse:
    """Return current user's long-term memory switch and records."""
    return get_user_memory(current_user.id, session=session)


@router.put("", response_model=UserMemoryResponse)
def update_memory_setting(
    request: MemorySettingRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> UserMemoryResponse:
    """Enable or disable long-term memory for the current user."""
    return set_memory_enabled(
        current_user.id,
        enabled=request.enabled,
        session=session,
    )


@router.delete("/{memory_id}")
def delete_memory_item(
    memory_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, int | str]:
    """Delete one memory record owned by the current user."""
    deleted = delete_user_memory(
        current_user.id,
        memory_id=memory_id,
        session=session,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found.")
    return {"message": "Memory deleted.", "memory_id": memory_id}


@router.delete("")
def clear_memory(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, int | str]:
    """Delete all memory records owned by the current user."""
    deleted_count = clear_user_memories(current_user.id, session=session)
    return {"message": "Memories cleared.", "deleted_count": deleted_count}
