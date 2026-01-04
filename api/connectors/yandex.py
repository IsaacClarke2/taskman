"""
Yandex Calendar connector using CalDAV protocol.

Yandex Calendar provides CalDAV access at:
- Main URL: https://caldav.yandex.ru
- Principal: /calendars/users/{username}

Authentication uses app-specific passwords (2FA required on account).
"""

import logging
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


class YandexCalendarConnector(CalendarConnector):
    """
    Yandex Calendar connector using CalDAV.

    Similar to Apple Calendar but with Yandex-specific URLs.
    """

    CALDAV_URL = "https://caldav.yandex.ru"

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
        """Get or create CalDAV client."""
        if self._client is None:
            # Run in thread pool since caldav is synchronous
            import asyncio

            def create_client():
                return caldav.DAVClient(
                    url=self.CALDAV_URL,
                    username=self.username,
                    password=self.password,
                )

            loop = asyncio.get_event_loop()
            self._client = await loop.run_in_executor(None, create_client)

        return self._client

    async def _get_principal(self) -> caldav.Principal:
        """Get CalDAV principal."""
        if self._principal is None:
            import asyncio

            client = await self._get_client()

            def get_principal():
                return client.principal()

            loop = asyncio.get_event_loop()
            self._principal = await loop.run_in_executor(None, get_principal)

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
        import asyncio

        principal = await self._get_principal()

        def get_calendars():
            return principal.calendars()

        loop = asyncio.get_event_loop()
        caldav_calendars = await loop.run_in_executor(None, get_calendars)

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
        import asyncio
        import uuid

        client = await self._get_client()

        # Build iCalendar event
        vevent = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Telegram AI Assistant//EN
BEGIN:VEVENT
UID:{uuid.uuid4()}
DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}
DTSTART:{event.start.strftime('%Y%m%dT%H%M%SZ')}
DTEND:{event.end.strftime('%Y%m%dT%H%M%SZ')}
SUMMARY:{event.title}
"""

        if event.location:
            vevent += f"LOCATION:{event.location}\n"
        if event.description:
            vevent += f"DESCRIPTION:{event.description}\n"

        # Add Telemost link if requested
        telemost_link = None
        if add_telemost:
            # Yandex Telemost links are generated separately
            # For now, add placeholder that user needs to create manually
            telemost_link = await self._create_telemost_link(event.title, event.start)
            if telemost_link:
                vevent += f"LOCATION:{telemost_link}\n"
                vevent += f"DESCRIPTION:Telemost: {telemost_link}\n"

        vevent += "END:VEVENT\nEND:VCALENDAR"

        def add_event():
            calendar = caldav.Calendar(client=client, url=calendar_id)
            return calendar.save_event(vevent)

        loop = asyncio.get_event_loop()
        created = await loop.run_in_executor(None, add_event)

        return Event(
            id=str(created.url),
            title=event.title,
            start=event.start,
            end=event.end,
            location=event.location or telemost_link,
            description=event.description,
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
        """List events in a calendar within a time range."""
        import asyncio

        client = await self._get_client()

        def get_events():
            calendar = caldav.Calendar(client=client, url=calendar_id)
            return calendar.date_search(
                start=start,
                end=end,
                expand=True,
            )

        loop = asyncio.get_event_loop()
        caldav_events = await loop.run_in_executor(None, get_events)

        events = []
        for e in caldav_events:
            try:
                vevent = e.vobject_instance.vevent

                event_start = vevent.dtstart.value
                event_end = vevent.dtend.value if hasattr(vevent, "dtend") else None

                # Convert date to datetime if needed
                if not isinstance(event_start, datetime):
                    event_start = datetime.combine(event_start, datetime.min.time())
                if event_end and not isinstance(event_end, datetime):
                    event_end = datetime.combine(event_end, datetime.min.time())
                if not event_end:
                    event_end = event_start + timedelta(hours=1)

                events.append(
                    Event(
                        id=str(e.url),
                        title=str(vevent.summary.value) if hasattr(vevent, "summary") else "Untitled",
                        start=event_start,
                        end=event_end,
                        location=str(vevent.location.value) if hasattr(vevent, "location") else None,
                        description=str(vevent.description.value) if hasattr(vevent, "description") else None,
                        calendar_id=calendar_id,
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
