from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.db_models import User
from app.models.schemas import (
    Itinerary,
    TokenStatsResponse,
    TripVersionCompareResponse,
    TripVersionDetailResponse,
    TripVersionListResponse,
    TripVersionRestoreResponse,
    TripDetailResponse,
    TripEditRequest,
    TripListResponse,
    TripRequest,
    TripSaveRequest,
)
from app.services.storage_service import (
    delete_itinerary_by_trip_id,
    compare_trip_versions,
    get_itinerary_by_trip_id,
    get_trip_version,
    get_token_stats,
    list_trip_versions,
    list_saved_itineraries,
    restore_trip_version,
    save_itinerary,
)
from app.services.memory_service import apply_memories_to_request, save_explicit_memories
from app.services.trip_service import edit_trip_itinerary, generate_trip_itinerary


router = APIRouter(prefix="/trip", tags=["trip"])


@router.get("", response_model=TripListResponse)
def list_trips(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> TripListResponse:
    """Return saved itinerary summaries for the current user."""
    return list_saved_itineraries(user_id=current_user.id, session=session)


@router.post("/generate", response_model=Itinerary)
def generate_trip(
    request: TripRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Itinerary:
    """Generate a structured itinerary for an authenticated user."""
    request_with_memory = apply_memories_to_request(
        current_user.id,
        request,
        session=session,
    )
    itinerary = generate_trip_itinerary(request_with_memory, user_id=current_user.id)
    save_explicit_memories(
        current_user.id,
        request,
        session=session,
    )
    return itinerary


@router.get("/stats", response_model=TokenStatsResponse)
def get_trip_token_stats(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> TokenStatsResponse:
    """Return token usage stats for the current user's saved trips."""
    return get_token_stats(user_id=current_user.id, session=session)


@router.post("/edit", response_model=Itinerary)
def edit_trip(
    request: TripEditRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Itinerary:
    """Apply a user edit instruction to an itinerary."""
    updated_itinerary = edit_trip_itinerary(request)
    saved_trip_id = save_itinerary(
        updated_itinerary,
        user_id=current_user.id,
        session=session,
        change_type="nl_edit",
    )
    if saved_trip_id != updated_itinerary.trip_id:
        updated_itinerary = updated_itinerary.model_copy(update={"trip_id": saved_trip_id})
    return updated_itinerary


@router.post("/save")
def save_trip(
    request: TripSaveRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    """Save an itinerary for the current user and return the trip_id."""
    saved_trip_id = save_itinerary(
        request.itinerary,
        user_id=current_user.id,
        session=session,
        change_type=request.change_type,
    )
    return {
        "message": "Trip itinerary saved successfully.",
        "trip_id": saved_trip_id,
    }


@router.get("/{trip_id}/versions", response_model=TripVersionListResponse)
def get_trip_versions(
    trip_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> TripVersionListResponse:
    """List versions owned by the current user for one trip."""
    return list_trip_versions(
        trip_id,
        user_id=current_user.id,
        session=session,
    )


@router.get("/{trip_id}/versions/compare", response_model=TripVersionCompareResponse)
def compare_versions(
    trip_id: str,
    from_version: int,
    to_version: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> TripVersionCompareResponse:
    """Compare two versions owned by the current user."""
    comparison = compare_trip_versions(
        trip_id,
        from_version=from_version,
        to_version=to_version,
        user_id=current_user.id,
        session=session,
    )
    if comparison is None:
        raise HTTPException(status_code=404, detail="Trip version not found.")
    return comparison


@router.get("/{trip_id}/versions/{version_number}", response_model=TripVersionDetailResponse)
def get_version_detail(
    trip_id: str,
    version_number: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> TripVersionDetailResponse:
    """Read one version owned by the current user."""
    version = get_trip_version(
        trip_id,
        version_number,
        user_id=current_user.id,
        session=session,
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Trip version not found.")
    return version


@router.post(
    "/{trip_id}/versions/{version_number}/restore",
    response_model=TripVersionRestoreResponse,
)
def restore_version(
    trip_id: str,
    version_number: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> TripVersionRestoreResponse:
    """Restore a version and create a new current version."""
    restored = restore_trip_version(
        trip_id,
        version_number,
        user_id=current_user.id,
        session=session,
    )
    if restored is None:
        raise HTTPException(status_code=404, detail="Trip version not found.")
    return restored


@router.get("/{trip_id}", response_model=TripDetailResponse)
def get_trip_detail(
    trip_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> TripDetailResponse:
    """Read a saved itinerary owned by the current user."""
    trip_detail = get_itinerary_by_trip_id(
        trip_id,
        user_id=current_user.id,
        session=session,
    )
    if trip_detail is None:
        raise HTTPException(status_code=404, detail="Trip not found.")
    return trip_detail


@router.delete("/{trip_id}")
def delete_trip(
    trip_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    """Delete a saved itinerary owned by the current user."""
    deleted = delete_itinerary_by_trip_id(
        trip_id,
        user_id=current_user.id,
        session=session,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Trip not found.")
    return {
        "message": "Trip itinerary deleted successfully.",
        "trip_id": trip_id,
    }
