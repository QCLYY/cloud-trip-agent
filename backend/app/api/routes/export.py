from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.db_models import User
from app.services.export_service import itinerary_to_markdown, itinerary_to_pdf_bytes
from app.services.storage_service import get_itinerary_by_trip_id


router = APIRouter(prefix="/export", tags=["export"])


def _build_inline_filename_header(filename: str) -> dict[str, str]:
    """Build a Content-Disposition header that supports non-ASCII names."""
    return {
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}",
    }


@router.get("/{trip_id}/markdown", response_class=PlainTextResponse)
def export_trip_markdown(
    trip_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> PlainTextResponse:
    """Export the current user's saved itinerary as Markdown."""
    trip_detail = get_itinerary_by_trip_id(
        trip_id,
        user_id=current_user.id,
        session=session,
    )
    if trip_detail is None:
        raise HTTPException(status_code=404, detail="Trip not found.")

    markdown = itinerary_to_markdown(trip_detail)
    return PlainTextResponse(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers=_build_inline_filename_header(f"{trip_id}.md"),
    )


@router.get("/{trip_id}/pdf", response_class=Response)
def export_trip_pdf(
    trip_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Response:
    """Export the current user's saved itinerary as PDF."""
    trip_detail = get_itinerary_by_trip_id(
        trip_id,
        user_id=current_user.id,
        session=session,
    )
    if trip_detail is None:
        raise HTTPException(status_code=404, detail="Trip not found.")

    try:
        pdf_bytes = itinerary_to_pdf_bytes(trip_detail)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers=_build_inline_filename_header(f"{trip_id}.pdf"),
    )
