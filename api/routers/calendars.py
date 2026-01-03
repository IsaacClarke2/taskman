"""
Calendars router - Calendar management and event operations.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from api.dependencies import CurrentUser, DatabaseSession
from api.models.requests import CalendarSettingsRequest, EventCreateRequest
from api.models.responses import CalendarResponse, ConflictResponse, EventResponse, TimeSlotResponse
from db.models import Calendar, Integration

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=list[CalendarResponse])
async def list_calendars(
    current_user: CurrentUser,
    session: DatabaseSession,
):
    """List all calendars for the current user."""
    result = await session.execute(
        select(Calendar, Integration)
        .join(Integration, Calendar.integration_id == Integration.id)
        .where(Integration.user_id == current_user.id)
    )
    calendars_with_integrations = result.all()

    return [
        CalendarResponse(
            id=cal.id,
            external_id=cal.external_id,
            name=cal.name,
            color=cal.color,
            is_primary=cal.is_primary,
            is_enabled=cal.is_enabled,
            provider=integration.provider,
        )
        for cal, integration in calendars_with_integrations
    ]


@router.get("/primary", response_model=Optional[CalendarResponse])
async def get_primary_calendar(
    current_user: CurrentUser,
    session: DatabaseSession,
):
    """Get the user's primary calendar."""
    result = await session.execute(
        select(Calendar, Integration)
        .join(Integration, Calendar.integration_id == Integration.id)
        .where(
            Integration.user_id == current_user.id,
            Calendar.is_primary == True,
        )
    )
    row = result.first()

    if not row:
        return None

    cal, integration = row
    return CalendarResponse(
        id=cal.id,
        external_id=cal.external_id,
        name=cal.name,
        color=cal.color,
        is_primary=cal.is_primary,
        is_enabled=cal.is_enabled,
        provider=integration.provider,
    )


@router.patch("/{calendar_id}", response_model=CalendarResponse)
async def update_calendar_settings(
    calendar_id: UUID,
    request: CalendarSettingsRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
):
    """Update calendar settings (primary, enabled)."""
    result = await session.execute(
        select(Calendar, Integration)
        .join(Integration, Calendar.integration_id == Integration.id)
        .where(
            Calendar.id == calendar_id,
            Integration.user_id == current_user.id,
        )
    )
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendar not found",
        )

    calendar, integration = row

    # If setting as primary, unset other primary calendars
    if request.is_primary:
        await session.execute(
            select(Calendar)
            .join(Integration, Calendar.integration_id == Integration.id)
            .where(
                Integration.user_id == current_user.id,
                Calendar.is_primary == True,
            )
        )
        # Unset all primary calendars for this user
        all_cals_result = await session.execute(
            select(Calendar)
            .join(Integration, Calendar.integration_id == Integration.id)
            .where(Integration.user_id == current_user.id)
        )
        for cal in all_cals_result.scalars():
            cal.is_primary = False

    if request.is_primary is not None:
        calendar.is_primary = request.is_primary
    if request.is_enabled is not None:
        calendar.is_enabled = request.is_enabled

    await session.flush()

    return CalendarResponse(
        id=calendar.id,
        external_id=calendar.external_id,
        name=calendar.name,
        color=calendar.color,
        is_primary=calendar.is_primary,
        is_enabled=calendar.is_enabled,
        provider=integration.provider,
    )


@router.post("/events", response_model=EventResponse)
async def create_event(
    request: EventCreateRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
):
    """Create a new calendar event."""
    # TODO: Implement actual event creation via connector
    # For now, return a mock response

    logger.info(f"Creating event: {request.title} for user {current_user.id}")

    return EventResponse(
        id="mock-event-id",
        title=request.title,
        start=request.start,
        end=request.end,
        location=request.location,
        calendar_id=request.calendar_id,
        calendar_name="Primary Calendar",
    )


@router.get("/events", response_model=list[EventResponse])
async def list_events(
    current_user: CurrentUser,
    session: DatabaseSession,
    start: datetime = Query(default_factory=datetime.now),
    end: datetime = Query(default=None),
    calendar_id: Optional[str] = None,
):
    """List events in a time range."""
    if end is None:
        end = start + timedelta(days=7)

    # TODO: Implement actual event listing via connectors
    logger.info(f"Listing events for user {current_user.id} from {start} to {end}")

    return []


@router.get("/free-slots", response_model=list[TimeSlotResponse])
async def get_free_slots(
    current_user: CurrentUser,
    session: DatabaseSession,
    start: datetime = Query(default_factory=datetime.now),
    end: datetime = Query(default=None),
    duration_minutes: int = Query(default=60, ge=15, le=480),
):
    """Find free time slots across all enabled calendars."""
    if end is None:
        end = start + timedelta(days=7)

    # TODO: Implement actual free slot calculation
    logger.info(f"Finding free slots for user {current_user.id}")

    # Return mock slots
    slots = []
    current = start.replace(hour=10, minute=0, second=0, microsecond=0)

    while current < end:
        if current.weekday() < 5:  # Weekdays only
            slot_end = current + timedelta(minutes=duration_minutes)
            if slot_end.hour <= 18:  # Working hours
                slots.append(TimeSlotResponse(start=current, end=slot_end))
        current += timedelta(days=1)

    return slots[:5]  # Return max 5 slots


@router.post("/check-conflicts", response_model=ConflictResponse)
async def check_conflicts(
    request: EventCreateRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
):
    """Check for conflicts with existing events."""
    # TODO: Implement actual conflict checking via connectors
    logger.info(f"Checking conflicts for {request.start} - {request.end}")

    return ConflictResponse(
        has_conflict=False,
        conflicting_events=[],
        suggested_slots=[],
    )
