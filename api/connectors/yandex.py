"""
Yandex Calendar connector using CalDAV protocol.

Yandex Calendar provides CalDAV access at:
- Main URL: https://caldav.yandex.ru
- Principal: /calendars/users/{username}

Authentication uses app-specific passwords (2FA required on account).

Features:
- asyncio.to_thread() for CalDAV operations
- X-TELEMOST-CONFERENCE parsing for existing events
- RECURRENCE-ID handling for recurring events
- Text field truncation (255 char limit)
- Sorted date_search results
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

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

# CalDAV field limits
MAX_SUMMARY_LENGTH = 255
MAX_LOCATION_LENGTH = 255
MAX_DESCRIPTION_LENGTH = 2000


def truncate_field(value: str, max_length: int) -> str:
    """Truncate field to max length, preserving word boundaries."""
    if not value or len(value) <= max_length:
        return value
    truncated = value[:max_length - 3]
    last_space = truncated.rfind(' ')
    if last_space > max_length // 2:
        truncated = truncated[:last_space]
    return truncated + "..."


class YandexCalendarConnector(CalendarConnector):
    """
    Yandex Calendar connector using CalDAV.

    Features:
    - X-TELEMOST-CONFERENCE parsing for Yandex video links
    - RECURRENCE-ID handling for recurring events
    - Proper field truncation
    """

    CALDAV_URL = "https://caldav.yandex.ru"
    TELEMOST_REGEX = re.compile(r'https://telemost\.yandex\.ru/j/\d+')

    def __init__(self, credentials: dict):
        """
        Initialize with Yandex credentials.

        Args:
            credentials: Dict with username and app_password.
        """
        super().__init__(credentials)
        self.username = credentials.get("username")
        self.password = credentials.get("app_password")
        self._client = None
        self._principal = None

    async def _get_client(self) -> caldav.DAVClient:
        """Get or create CalDAV client using asyncio.to_thread()."""
        if self._client is None:
            def create_client():
                return caldav.DAVClient(
                    url=self.CALDAV_URL,
                    username=self.username,
                    password=self.password,
                )

            self._client = await asyncio.to_thread(create_client)

        return self._client

    async def _get_principal(self) -> caldav.Principal:
        """Get CalDAV principal using asyncio.to_thread()."""
        if self._principal is None:
            client = await self._get_client()

            def get_principal():
                return client.principal()

            self._principal = await asyncio.to_thread(get_principal)

        return self._principal

    async def test_connection(self) -> bool:
        """Test if the connection is working."""
        try:
            principal = await self._get_principal()
            return principal is not None
        except Exception as e:
            logger.error(f"Yandex Calendar connection test failed: {e}")
            return False

    async def refresh_token(self) -> dict:
        """Yandex uses app passwords, no token refresh needed."""
        return self.credentials

    async def list_calendars(self) -> list[Calendar]:
        """List all calendars for the user."""
        principal = await self._get_principal()

        def get_calendars():
            return principal.calendars()

        caldav_calendars = await asyncio.to_thread(get_calendars)

        calendars = []
        for i, cal in enumerate(caldav_calendars):
            calendars.append(
                Calendar(
                    id=str(cal.url),
                    name=cal.name or f"Calendar {i + 1}",
                    color=None,  # CalDAV doesn't always provide color
                    is_primary=(i == 0),
                )
            )

        return calendars

    async def create_event(
        self,
        calendar_id: str,
        event: EventCreate,
        add_telemost: bool = False,
    ) -> Event:
        """
        Create a new event in the specified calendar.

        Args:
            calendar_id: Calendar URL.
            event: Event data.
            add_telemost: Whether to add Yandex Telemost link.

        Returns:
            Created event.
        """
        import uuid

        client = await self._get_client()

        # Truncate fields to CalDAV limits
        title = truncate_field(event.title, MAX_SUMMARY_LENGTH)
        location = truncate_field(event.location, MAX_LOCATION_LENGTH) if event.location else None
        description = truncate_field(event.description, MAX_DESCRIPTION_LENGTH) if event.description else None

        # Build iCalendar event
        vevent = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Telegram AI Assistant//EN
BEGIN:VEVENT
UID:{uuid.uuid4()}
DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}
DTSTART:{event.start.strftime('%Y%m%dT%H%M%SZ')}
DTEND:{event.end.strftime('%Y%m%dT%H%M%SZ')}
SUMMARY:{title}
"""

        if location:
            vevent += f"LOCATION:{location}\n"
        if description:
            vevent += f"DESCRIPTION:{description}\n"

        # Add Telemost link if requested
        telemost_link = None
        if add_telemost:
            telemost_link = await self._create_telemost_link(event.title, event.start)
            if telemost_link:
                vevent += f"X-TELEMOST-CONFERENCE:{telemost_link}\n"
                if not location:
                    vevent += f"LOCATION:{telemost_link}\n"

        vevent += "END:VEVENT\nEND:VCALENDAR"

        def add_event():
            calendar = caldav.Calendar(client=client, url=calendar_id)
            return calendar.save_event(vevent)

        created = await asyncio.to_thread(add_event)

        return Event(
            id=str(created.url),
            title=title,
            start=event.start,
            end=event.end,
            location=location or telemost_link,
            description=description,
            calendar_id=calendar_id,
            conference_link=telemost_link,
        )

    async def _create_telemost_link(
        self,
        topic: str,
        start_time: datetime,
    ) -> Optional[str]:
        """
        Create Yandex Telemost meeting link.

        Note: Telemost API requires Yandex 360 business account.
        For personal accounts, returns None and user creates manually.
        """
        # Telemost API is available for Yandex 360 business users
        # Personal users need to create links manually at telemost.yandex.ru
        # For now, return None - can be extended later
        logger.info("Telemost link creation requires Yandex 360 business account")
        return None

    async def list_events(
        self, calendar_id: str, start: datetime, end: datetime
    ) -> list[Event]:
        """
        List events in a calendar within a time range.

        Features:
        - X-TELEMOST-CONFERENCE parsing for Yandex video links
        - RECURRENCE-ID handling for recurring events
        - sort_keys=['dtstart'] for proper ordering
        """
        client = await self._get_client()

        def get_events():
            calendar = caldav.Calendar(client=client, url=calendar_id)
            return calendar.date_search(
                start=start,
                end=end,
                expand=True,
                sort_keys=['dtstart'],  # Sort by start time
            )

        caldav_events = await asyncio.to_thread(get_events)

        events = []
        seen_recurrence_ids = set()  # Track RECURRENCE-ID to avoid duplicates

        for e in caldav_events:
            try:
                vevent = e.vobject_instance.vevent

                # Handle RECURRENCE-ID for recurring events (mm-yc-notify pattern)
                recurrence_id = None
                if hasattr(vevent, 'recurrence_id'):
                    recurrence_id = str(vevent.recurrence_id.value)
                    event_key = f"{e.url}_{recurrence_id}"
                    if event_key in seen_recurrence_ids:
                        continue  # Skip duplicate instance
                    seen_recurrence_ids.add(event_key)

                event_start = vevent.dtstart.value
                event_end = vevent.dtend.value if hasattr(vevent, "dtend") else None

                # Convert date to datetime if needed
                if not isinstance(event_start, datetime):
                    event_start = datetime.combine(event_start, datetime.min.time())
                if event_end and not isinstance(event_end, datetime):
                    event_end = datetime.combine(event_end, datetime.min.time())
                if not event_end:
                    event_end = event_start + timedelta(hours=1)

                # Extract Telemost conference link (X-TELEMOST-CONFERENCE)
                conference_link = None
                raw_data = e.data if hasattr(e, 'data') else str(e.vobject_instance.serialize())

                # Try X-TELEMOST-CONFERENCE property first
                telemost_match = re.search(r'X-TELEMOST-CONFERENCE[^:]*:(.+)', raw_data)
                if telemost_match:
                    conference_link = telemost_match.group(1).strip()
                else:
                    # Fallback: search in location/description for Telemost URL
                    telemost_url = self.TELEMOST_REGEX.search(raw_data)
                    if telemost_url:
                        conference_link = telemost_url.group(0)

                events.append(
                    Event(
                        id=str(e.url),
                        title=str(vevent.summary.value) if hasattr(vevent, "summary") else "Untitled",
                        start=event_start,
                        end=event_end,
                        location=str(vevent.location.value) if hasattr(vevent, "location") else None,
                        description=str(vevent.description.value) if hasattr(vevent, "description") else None,
                        calendar_id=calendar_id,
                        conference_link=conference_link,
                    )
                )
            except Exception as ex:
                logger.warning(f"Failed to parse event: {ex}")
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

        # Sort events by start time
        events.sort(key=lambda e: e.start)

        free_slots = []
        current = start

        for event in events:
            if event.start > current:
                slot_duration = (event.start - current).total_seconds() / 60
                if slot_duration >= duration_minutes:
                    free_slots.append(TimeSlot(start=current, end=event.start))
            current = max(current, event.end)

        # Check for free time after last event
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
