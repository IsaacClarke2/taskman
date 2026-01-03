"""
Apple Calendar connector using CalDAV protocol.
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

import caldav
from caldav.elements import dav

from api.connectors.base import (
    Calendar,
    CalendarConnector,
    Event,
    EventCreate,
    TimeSlot,
)

logger = logging.getLogger(__name__)


class AppleCalendarConnector(CalendarConnector):
    """
    Apple Calendar connector using CalDAV protocol.

    Connects to iCloud Calendar using app-specific password.
    """

    CALDAV_URL = "https://caldav.icloud.com"

    def __init__(self, credentials: dict):
        """
        Initialize with iCloud credentials.

        Args:
            credentials: Dict with email and app_password.
        """
        super().__init__(credentials)
        self.email = credentials.get("email")
        self.app_password = credentials.get("app_password")
        self._client: Optional[caldav.DAVClient] = None
        self._principal: Optional[caldav.Principal] = None

    def _get_client(self) -> caldav.DAVClient:
        """Get or create CalDAV client."""
        if not self._client:
            self._client = caldav.DAVClient(
                url=self.CALDAV_URL,
                username=self.email,
                password=self.app_password,
            )
        return self._client

    def _get_principal(self) -> caldav.Principal:
        """Get or create CalDAV principal."""
        if not self._principal:
            client = self._get_client()
            self._principal = client.principal()
        return self._principal

    async def test_connection(self) -> bool:
        """Test if the connection is working."""
        try:
            principal = self._get_principal()
            calendars = principal.calendars()
            logger.info(f"Apple Calendar connected: {len(calendars)} calendars found")
            return True
        except Exception as e:
            logger.error(f"Apple Calendar connection test failed: {e}")
            return False

    async def refresh_token(self) -> dict:
        """
        Refresh token - not applicable for app-specific passwords.

        Returns the existing credentials.
        """
        return self.credentials

    async def list_calendars(self) -> list[Calendar]:
        """List all calendars for the user."""
        principal = self._get_principal()
        caldav_calendars = principal.calendars()

        calendars = []
        for i, cal in enumerate(caldav_calendars):
            calendars.append(
                Calendar(
                    id=str(cal.url),
                    name=cal.name or f"Calendar {i + 1}",
                    color=None,  # CalDAV doesn't always provide color
                    is_primary=(i == 0),  # First calendar is considered primary
                )
            )

        return calendars

    async def create_event(self, calendar_id: str, event: EventCreate) -> Event:
        """Create a new event in the specified calendar."""
        principal = self._get_principal()

        # Find the calendar by URL
        target_cal = None
        for cal in principal.calendars():
            if str(cal.url) == calendar_id:
                target_cal = cal
                break

        if not target_cal:
            raise ValueError(f"Calendar not found: {calendar_id}")

        # Create iCalendar event
        event_uid = str(uuid4())
        ical_event = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Telegram AI Assistant//EN
BEGIN:VEVENT
UID:{event_uid}
DTSTART:{event.start.strftime('%Y%m%dT%H%M%SZ')}
DTEND:{event.end.strftime('%Y%m%dT%H%M%SZ')}
SUMMARY:{event.title}
{f'LOCATION:{event.location}' if event.location else ''}
{f'DESCRIPTION:{event.description}' if event.description else ''}
END:VEVENT
END:VCALENDAR"""

        caldav_event = target_cal.save_event(ical_event)

        return Event(
            id=event_uid,
            title=event.title,
            start=event.start,
            end=event.end,
            location=event.location,
            description=event.description,
            calendar_id=calendar_id,
        )

    async def list_events(
        self, calendar_id: str, start: datetime, end: datetime
    ) -> list[Event]:
        """List events in a calendar within a time range."""
        principal = self._get_principal()

        target_cal = None
        for cal in principal.calendars():
            if str(cal.url) == calendar_id:
                target_cal = cal
                break

        if not target_cal:
            raise ValueError(f"Calendar not found: {calendar_id}")

        caldav_events = target_cal.date_search(start=start, end=end, expand=True)

        events = []
        for caldav_event in caldav_events:
            try:
                ical = caldav_event.icalendar_component
                vevent = ical.walk("VEVENT")[0] if ical.walk("VEVENT") else None

                if vevent:
                    events.append(
                        Event(
                            id=str(vevent.get("UID", uuid4())),
                            title=str(vevent.get("SUMMARY", "")),
                            start=vevent.get("DTSTART").dt if vevent.get("DTSTART") else start,
                            end=vevent.get("DTEND").dt if vevent.get("DTEND") else end,
                            location=str(vevent.get("LOCATION", "")) or None,
                            description=str(vevent.get("DESCRIPTION", "")) or None,
                            calendar_id=calendar_id,
                        )
                    )
            except Exception as e:
                logger.warning(f"Failed to parse CalDAV event: {e}")
                continue

        return events

    async def get_free_slots(
        self,
        calendar_id: str,
        start: datetime,
        end: datetime,
        duration_minutes: int = 60,
    ) -> list[TimeSlot]:
        """Find free time slots in a calendar."""
        events = await self.list_events(calendar_id, start, end)
        events.sort(key=lambda e: e.start)

        free_slots = []
        current = start

        for event in events:
            if event.start > current:
                slot_duration = (event.start - current).total_seconds() / 60
                if slot_duration >= duration_minutes:
                    free_slots.append(TimeSlot(start=current, end=event.start))
            current = max(current, event.end)

        if current < end:
            slot_duration = (end - current).total_seconds() / 60
            if slot_duration >= duration_minutes:
                free_slots.append(TimeSlot(start=current, end=end))

        return free_slots

    async def check_conflicts(
        self, calendar_id: str, start: datetime, end: datetime
    ) -> list[Event]:
        """Check for conflicting events in a time range."""
        events = await self.list_events(calendar_id, start, end)

        conflicts = []
        for event in events:
            if event.start < end and event.end > start:
                conflicts.append(event)

        return conflicts
