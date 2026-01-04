"""
Google Calendar connector implementation.
"""

import logging
from datetime import datetime
from typing import Optional

import httpx

from api.connectors.base import (
    Calendar,
    CalendarConnector,
    Event,
    EventCreate,
    TimeSlot,
)

logger = logging.getLogger(__name__)


class GoogleCalendarConnector(CalendarConnector):
    """
    Google Calendar API connector.

    Implements calendar operations using Google Calendar REST API.
    """

    BASE_URL = "https://www.googleapis.com/calendar/v3"

    def __init__(self, credentials: dict):
        """
        Initialize with OAuth tokens.

        Args:
            credentials: Dict with access_token, refresh_token, etc.
        """
        super().__init__(credentials)
        self.access_token = credentials.get("access_token")
        self.refresh_token = credentials.get("refresh_token")

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> dict:
        """Make authenticated request to Google Calendar API."""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                f"{self.BASE_URL}{endpoint}",
                headers=headers,
                **kwargs,
            )

            if response.status_code == 401:
                # Token expired, need refresh
                raise TokenExpiredError("Access token expired")

            response.raise_for_status()
            return response.json() if response.content else {}

    async def test_connection(self) -> bool:
        """Test if the connection is working."""
        try:
            await self._request("GET", "/users/me/calendarList", params={"maxResults": 1})
            return True
        except Exception as e:
            logger.error(f"Google Calendar connection test failed: {e}")
            return False

    async def refresh_token(self) -> dict:
        """Refresh OAuth tokens."""
        from api.config import get_settings

        settings = get_settings()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                },
            )

            if response.status_code != 200:
                raise TokenRefreshError(f"Failed to refresh token: {response.text}")

            tokens = response.json()
            # Update internal token
            self.access_token = tokens["access_token"]
            # Merge with existing credentials
            self.credentials.update(tokens)
            return self.credentials

    async def list_calendars(self) -> list[Calendar]:
        """List all calendars for the user."""
        data = await self._request("GET", "/users/me/calendarList")

        calendars = []
        for item in data.get("items", []):
            calendars.append(
                Calendar(
                    id=item["id"],
                    name=item.get("summary", "Untitled"),
                    color=item.get("backgroundColor"),
                    is_primary=item.get("primary", False),
                )
            )

        return calendars

    async def create_event(
        self,
        calendar_id: str,
        event: EventCreate,
        add_google_meet: bool = False,
    ) -> Event:
        """
        Create a new event in the specified calendar.

        Args:
            calendar_id: Target calendar ID.
            event: Event details.
            add_google_meet: Whether to create a Google Meet link.

        Returns:
            Created event with conference link if requested.
        """
        import uuid

        body = {
            "summary": event.title,
            "start": {"dateTime": event.start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": event.end.isoformat(), "timeZone": "UTC"},
        }

        if event.location:
            body["location"] = event.location
        if event.description:
            body["description"] = event.description

        # Add Google Meet conference
        if add_google_meet:
            body["conferenceData"] = {
                "createRequest": {
                    "requestId": str(uuid.uuid4()),
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            }

        # Need conferenceDataVersion=1 for Meet creation
        params = {"conferenceDataVersion": 1} if add_google_meet else None

        data = await self._request(
            "POST",
            f"/calendars/{calendar_id}/events",
            json=body,
            params=params,
        )

        # Extract Meet link if created
        meet_link = None
        conference_data = data.get("conferenceData", {})
        entry_points = conference_data.get("entryPoints", [])
        for entry in entry_points:
            if entry.get("entryPointType") == "video":
                meet_link = entry.get("uri")
                break

        return Event(
            id=data["id"],
            title=data.get("summary", ""),
            start=datetime.fromisoformat(data["start"]["dateTime"].replace("Z", "+00:00")),
            end=datetime.fromisoformat(data["end"]["dateTime"].replace("Z", "+00:00")),
            location=data.get("location"),
            description=data.get("description"),
            calendar_id=calendar_id,
            conference_link=meet_link,
        )

    async def list_events(
        self, calendar_id: str, start: datetime, end: datetime
    ) -> list[Event]:
        """List events in a calendar within a time range."""
        params = {
            "timeMin": start.isoformat() + "Z",
            "timeMax": end.isoformat() + "Z",
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": 250,
        }

        data = await self._request(
            "GET",
            f"/calendars/{calendar_id}/events",
            params=params,
        )

        events = []
        for item in data.get("items", []):
            start_dt = item["start"].get("dateTime") or item["start"].get("date")
            end_dt = item["end"].get("dateTime") or item["end"].get("date")

            events.append(
                Event(
                    id=item["id"],
                    title=item.get("summary", ""),
                    start=datetime.fromisoformat(start_dt.replace("Z", "+00:00")),
                    end=datetime.fromisoformat(end_dt.replace("Z", "+00:00")),
                    location=item.get("location"),
                    description=item.get("description"),
                    calendar_id=calendar_id,
                )
            )

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
            # Check if event overlaps with the proposed time
            if event.start < end and event.end > start:
                conflicts.append(event)

        return conflicts


class TokenExpiredError(Exception):
    """Raised when access token is expired."""

    pass


class TokenRefreshError(Exception):
    """Raised when token refresh fails."""

    pass
