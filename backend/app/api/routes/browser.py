"""POST /browser/navigate — launch MS Edge to a Ctrip page for manual browsing."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.browser_nav_service import navigate_to_ctrip

router = APIRouter(prefix="/browser", tags=["browser"])


class BrowserNavigateRequest(BaseModel):
    category: str = Field(
        ...,
        description="One of: flight, train, hotel, vacation",
        examples=["flight"],
    )
    origin_city: str = Field(
        default="",
        description="Departure city, e.g. 上海",
        examples=["上海"],
    )
    destination: str = Field(
        default="",
        description="Destination city, e.g. 大理",
        examples=["大理"],
    )
    start_date: str = Field(
        default="",
        description="ISO-format start date, e.g. 2026-07-01",
        examples=["2026-07-01"],
    )
    end_date: str = Field(
        default="",
        description="ISO-format end date (used for hotel checkout)",
        examples=["2026-07-04"],
    )


@router.post("/navigate")
def navigate(request: BrowserNavigateRequest) -> dict:
    """Launch MS Edge and navigate to a Ctrip search page.

    The browser runs independently — closing the backend does not close it.
    """
    result = navigate_to_ctrip(
        category=request.category,
        origin_city=request.origin_city,
        destination=request.destination,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    if result["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["message"],
        )
    return result
