"""
Microsoft Outlook Calendar connector implementation.
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


class OutlookConnector(CalendarConnector):
    """
    Microsoft Outlook Calendar connector using Microsoft Graph API.
    """

    BASE_URL = "https://graph.microsoft.com/v1.0"

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
        """Make authenticated request to Microsoft Graph API."""
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
                raise TokenExpiredError("Access token expired")

            response.raise_for_status()
            return response.json() if response.content else {}

    async def test_connection(self) -> bool:
        """Test if the connection is working."""
        try:
            await self._request("GET", "/me/calendars", params={"$top": 1})
            return True
        except Exception as e:
            logger.error(f"Outlook connection test failed: {e}")
            return False

    async def refresh_token(self) -> dict:
        """Refresh OAuth tokens."""
        from api.config import get_settings

        settings = get_settings()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                data={
                    "client_id": settings.microsoft_client_id,
                    "client_secret": settings.microsoft_client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                    "scope": "offline_access Calendars.ReadWrite User.Read",
                },
            )

            if response.status_code != 200:
                raise TokenRefreshError(f"Failed to refresh token: {response.text}")

            tokens = response.json()
            self.access_token = tokens["access_token"]
            self.refresh_token = tokens.get("refresh_token", self.refresh_token)
            self.credentials.update(tokens)
            return self.credentials

    async def list_calendars(self) -> list[Calendar]:
        """List all calendars for the user."""
        data = await self._request("GET", "/me/calendars")

        calendars = []
        for item in data.get("value", []):
            calendars.append(
                Calendar(
                    id=item["id"],
                    name=item.get("name", "Untitled"),
                    color=item.get("color"),
                    is_primary=item.get("isDefaultCalendar", False),
                )
            )

        return calendars

    async def create_event(self, calendar_id: str, event: EventCreate) -> Event:
        """Create a new event in the specified calendar."""
        body = {
            "subject": event.title,
            "start": {
                "dateTime": event.start.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": event.end.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "UTC",
            },
        }

        if event.location:
            body["location"] = {"displayName": event.location}
        if event.description:
            body["body"] = {"contentType": "text", "content": event.description}

        data = await self._request(
            "POST",
            f"/me/calendars/{calendar_id}/events",
            json=body,
        )

        return Event(
            id=data["id"],
            title=data.get("subject", ""),
            start=datetime.fromisoformat(data["start"]["dateTime"]),
            end=datetime.fromisoformat(data["end"]["dateTime"]),
            location=data.get("location", {}).get("displayName"),
            description=data.get("body", {}).get("content"),
            calendar_id=calendar_id,
        )

    async def list_events(
        self, calendar_id: str, start: datetime, end: datetime
    ) -> list[Event]:
        """List events in a calendar within a time range."""
        params = {
            "$filter": f"start/dateTime ge '{start.isoformat()}' and end/dateTime le '{end.isoformat()}'",
            "$orderby": "start/dateTime",
            "$top": 250,
        }

        data = await self._request(
            "GET",
            f"/me/calendars/{calendar_id}/events",
            params=params,
        )

        events = []
        for item in data.get("value", []):
            events.append(
                Event(
                    id=item["id"],
                    title=item.get("subject", ""),
                    start=datetime.fromisoformat(item["start"]["dateTime"]),
                    end=datetime.fromisoformat(item["end"]["dateTime"]),
                    location=item.get("location", {}).get("displayName"),
                    description=item.get("body", {}).get("content"),
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
        """Find free time slots using Microsoft Graph findMeetingTimes API."""
        # Use simple slot calculation based on events
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


class TokenExpiredError(Exception):
    """Raised when access token is expired."""

    pass


class TokenRefreshError(Exception):
    """Raised when token refresh fails."""

    pass
