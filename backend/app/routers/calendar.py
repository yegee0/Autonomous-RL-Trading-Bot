from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.app.services import calendar_service as cs

router = APIRouter()


class CalendarEventOut(BaseModel):
    ts: int
    name: str
    impact: str
    affects: str
    source: str


class CalendarResponse(BaseModel):
    events: List[CalendarEventOut]
    event_window_active: bool
    active_event: Optional[CalendarEventOut] = None


@router.get("/calendar", response_model=CalendarResponse)
def calendar(
    ticker: Optional[str] = Query(None),
    hours_ahead: int = Query(168, ge=1, le=720),
) -> CalendarResponse:
    events = [
        CalendarEventOut(**e.__dict__) for e in cs.upcoming_events(ticker=ticker, hours_ahead=hours_ahead)
    ]
    active = cs.in_event_window(ticker=ticker)
    return CalendarResponse(
        events=events,
        event_window_active=active is not None,
        active_event=CalendarEventOut(**active.__dict__) if active else None,
    )
