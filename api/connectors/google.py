"""
Google Calendar connector implementation.

Features:
- Proactive token refresh (5-minute buffer)
- FreeBusy API for efficient conflict detection
- Google Meet integration
"""

import logging
import time
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
from api.utils.token_manager import TOKEN_REFRESH_BUFFER, is_token_expired

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
            credentials: Dict with access_token, refresh_token, expires_at, etc.
        """
        super().__init__(credentials)
        self.access_token = credentials.get("access_token")
        self.refresh_token_value = credentials.get("refresh_token")
        self.expires_at = credentials.get("expires_at")

    async def _ensure_valid_token(self) -> None:
        """
        Ensure token is valid, refresh proactively if needed.

        Uses 5-minute buffer before expiration to prevent race conditions.
        """
        if is_token_expired(self.credentials, TOKEN_REFRESH_BUFFER):
            logger.info("Token expired or expiring soon, refreshing...")
            new_creds = await self.refresh_token()
            self.access_token = new_creds["access_token"]
            self.expires_at = new_creds.get("expires_at")

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> dict:
        """Make authenticated request to Google Calendar API."""
        # Proactive token refresh
        await self._ensure_valid_token()

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
                # Token expired despite proactive check, retry once
                logger.warning("Token expired, refreshing and retrying...")
                new_creds = await self.refresh_token()
                self.access_token = new_creds["access_token"]

                headers["Authorization"] = f"Bearer {self.access_token}"
                response = await client.request(
                    method,
                    f"{self.BASE_URL}{endpoint}",
                    headers=headers,
                    **kwargs,
                )

                if response.status_code == 401:
                    raise TokenExpiredError("Access token expired after refresh")

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
                    "refresh_token": self.refresh_token_value,
                    "grant_type": "refresh_token",
                },
            )

            if response.status_code != 200:
                raise TokenRefreshError(f"Failed to refresh token: {response.text}")

            tokens = response.json()

            # Add expiration timestamp
            if "expires_in" in tokens:
                tokens["expires_at"] = time.time() + tokens["expires_in"]

            # Preserve refresh token if not returned
            if "refresh_token" not in tokens:
                tokens["refresh_token"] = self.refresh_token_value

            # Update internal state
            self.access_token = tokens["access_token"]
            self.expires_at = tokens.get("expires_at")
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

    async def get_freebusy(
        self,
        calendar_ids: list[str],
        start: datetime,
        end: datetime,
    ) -> dict[str, list[dict]]:
        """
        Query FreeBusy API for multiple calendars.

        More efficient than listing all events when only need busy/free status.

        Args:
            calendar_ids: List of calendar IDs to query
            start: Start of time range
            end: End of time range

        Returns:
            Dict mapping calendar_id to list of busy periods
        """
        body = {
            "timeMin": start.isoformat() + "Z",
            "timeMax": end.isoformat() + "Z",
            "items": [{"id": cal_id} for cal_id in calendar_ids],
        }

        data = await self._request(
            "POST",
            "/freeBusy",
            json=body,
        )

        result = {}
        calendars = data.get("calendars", {})
        for cal_id in calendar_ids:
            cal_data = calendars.get(cal_id, {})
            busy_periods = cal_data.get("busy", [])
            result[cal_id] = busy_periods

        return result

    async def get_free_slots(
        self,
        calendar_id: str,
        start: datetime,
        end: datetime,
        duration_minutes: int = 60,
        max_per_day: int = 3,
        max_total: int = 10,
    ) -> list[TimeSlot]:
        """
        Find free time slots using FreeBusy API.

        Uses efficient gap analysis algorithm with constraints.

        Args:
            calendar_id: Calendar to check
            start: Start of search range
            end: End of search range
            duration_minutes: Minimum slot duration
            max_per_day: Maximum slots per day
            max_total: Maximum total slots

        Returns:
            List of available time slots
        """
        # Use FreeBusy API for efficiency
        freebusy = await self.get_freebusy([calendar_id], start, end)
        busy_periods = freebusy.get(calendar_id, [])

        # Merge overlapping busy periods (stack-based algorithm)
        merged = self._merge_busy_periods(busy_periods)

        # Find gaps using sliding window
        free_slots = []
        current = start
        current_day = start.date()
        day_count = 0

        for busy in merged:
            busy_start = datetime.fromisoformat(busy["start"].replace("Z", "+00:00"))
            busy_end = datetime.fromisoformat(busy["end"].replace("Z", "+00:00"))

            # Check gap before busy period
            if busy_start > current:
                gap_minutes = (busy_start - current).total_seconds() / 60
                if gap_minutes >= duration_minutes:
                    # Check day limit
                    slot_day = current.date()
                    if slot_day != current_day:
                        current_day = slot_day
                        day_count = 0

                    if day_count < max_per_day and len(free_slots) < max_total:
                        free_slots.append(TimeSlot(start=current, end=busy_start))
                        day_count += 1

            current = max(current, busy_end)

        # Check gap after last busy period
        if current < end and len(free_slots) < max_total:
            gap_minutes = (end - current).total_seconds() / 60
            if gap_minutes >= duration_minutes:
                free_slots.append(TimeSlot(start=current, end=end))

        return free_slots[:max_total]

    def _merge_busy_periods(self, busy_periods: list[dict]) -> list[dict]:
        """
        Merge overlapping busy periods using stack algorithm.

        From AI_for_Scheduling pattern.
        """
        if not busy_periods:
            return []

        # Sort by start time
        sorted_periods = sorted(busy_periods, key=lambda x: x["start"])

        merged = [sorted_periods[0]]

        for period in sorted_periods[1:]:
            top = merged[-1]

            # Check overlap
            if period["start"] <= top["end"]:
                # Extend if current ends later
                if period["end"] > top["end"]:
                    merged[-1] = {"start": top["start"], "end": period["end"]}
            else:
                merged.append(period)

        return merged

    async def check_conflicts(
        self, calendar_id: str, start: datetime, end: datetime
    ) -> list[Event]:
        """
        Check for conflicting events using FreeBusy API.

        More efficient than listing all events.
        """
        freebusy = await self.get_freebusy([calendar_id], start, end)
        busy_periods = freebusy.get(calendar_id, [])

        # For detailed conflict info, fetch actual events
        if busy_periods:
            return await self.list_events(calendar_id, start, end)

        return []

    async def check_multi_calendar_conflicts(
        self,
        calendar_ids: list[str],
        start: datetime,
        end: datetime,
    ) -> dict[str, bool]:
        """
        Check conflicts across multiple calendars efficiently.

        Args:
            calendar_ids: List of calendar IDs to check
            start: Proposed event start
            end: Proposed event end

        Returns:
            Dict mapping calendar_id to conflict status (True = has conflict)
        """
        freebusy = await self.get_freebusy(calendar_ids, start, end)

        conflicts = {}
        for cal_id in calendar_ids:
            busy_periods = freebusy.get(cal_id, [])
            conflicts[cal_id] = len(busy_periods) > 0

        return conflicts


class TokenExpiredError(Exception):
    """Raised when access token is expired."""
    pass


class TokenRefreshError(Exception):
    """Raised when token refresh fails."""
    pass
