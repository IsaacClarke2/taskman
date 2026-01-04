"""
Zoom connector for creating meetings.

Uses Zoom OAuth 2.0 User-Level App for creating meetings.
The meeting link is then added to calendar events.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class ZoomMeeting:
    """Zoom meeting details."""

    def __init__(
        self,
        id: str,
        join_url: str,
        start_url: str,
        password: Optional[str] = None,
        topic: str = "",
        start_time: Optional[datetime] = None,
        duration: int = 60,
    ):
        self.id = id
        self.join_url = join_url
        self.start_url = start_url
        self.password = password
        self.topic = topic
        self.start_time = start_time
        self.duration = duration


class ZoomConnector:
    """
    Zoom API connector.

    Uses Zoom OAuth 2.0 for user-level access to create meetings.
    """

    BASE_URL = "https://api.zoom.us/v2"
    AUTH_URL = "https://zoom.us/oauth/authorize"
    TOKEN_URL = "https://zoom.us/oauth/token"

    def __init__(self, credentials: dict):
        """
        Initialize with OAuth tokens.

        Args:
            credentials: Dict with access_token, refresh_token, etc.
        """
        self.credentials = credentials
        self.access_token = credentials.get("access_token")
        self.refresh_token = credentials.get("refresh_token")

    @classmethod
    def get_authorization_url(
        cls,
        client_id: str,
        redirect_uri: str,
        state: str,
    ) -> str:
        """
        Generate OAuth authorization URL.

        Args:
            client_id: Zoom OAuth app client ID.
            redirect_uri: OAuth callback URL.
            state: State parameter for CSRF protection.

        Returns:
            Authorization URL for Zoom OAuth.
        """
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }

        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{cls.AUTH_URL}?{query}"

    @classmethod
    async def exchange_code(
        cls,
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> dict:
        """
        Exchange authorization code for tokens.

        Args:
            code: Authorization code from OAuth callback.
            client_id: Zoom OAuth app client ID.
            client_secret: Zoom OAuth app client secret.
            redirect_uri: OAuth callback URL.

        Returns:
            Token response dict with access_token, refresh_token, etc.
        """
        import base64

        # Zoom requires Basic auth for token exchange
        credentials = base64.b64encode(
            f"{client_id}:{client_secret}".encode()
        ).decode()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                cls.TOKEN_URL,
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )

            if response.status_code != 200:
                raise ZoomAuthError(f"Token exchange failed: {response.text}")

            return response.json()

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> dict:
        """Make authenticated request to Zoom API."""
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
                raise ZoomTokenExpiredError("Access token expired")

            response.raise_for_status()
            return response.json() if response.content else {}

    async def refresh_tokens(
        self,
        client_id: str,
        client_secret: str,
    ) -> dict:
        """
        Refresh OAuth tokens.

        Args:
            client_id: Zoom OAuth app client ID.
            client_secret: Zoom OAuth app client secret.

        Returns:
            Updated credentials with new tokens.
        """
        import base64

        credentials = base64.b64encode(
            f"{client_id}:{client_secret}".encode()
        ).decode()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                },
            )

            if response.status_code != 200:
                raise ZoomAuthError(f"Token refresh failed: {response.text}")

            tokens = response.json()
            self.access_token = tokens["access_token"]
            self.refresh_token = tokens.get("refresh_token", self.refresh_token)
            self.credentials.update(tokens)

            return self.credentials

    async def test_connection(self) -> bool:
        """Test if the connection is working."""
        try:
            await self._request("GET", "/users/me")
            return True
        except Exception as e:
            logger.error(f"Zoom connection test failed: {e}")
            return False

    async def get_user_info(self) -> dict:
        """Get current user information."""
        return await self._request("GET", "/users/me")

    async def create_meeting(
        self,
        topic: str,
        start_time: datetime,
        duration_minutes: int = 60,
        timezone: str = "Europe/Moscow",
        password: Optional[str] = None,
        agenda: Optional[str] = None,
        auto_recording: str = "none",  # "local", "cloud", "none"
        waiting_room: bool = False,
    ) -> ZoomMeeting:
        """
        Create a new Zoom meeting.

        Args:
            topic: Meeting topic/title.
            start_time: Meeting start time.
            duration_minutes: Meeting duration in minutes.
            timezone: Timezone for the meeting.
            password: Meeting password (generated if None).
            agenda: Meeting agenda/description.
            auto_recording: Auto-recording setting.
            waiting_room: Enable waiting room.

        Returns:
            ZoomMeeting object with join URL.
        """
        body = {
            "topic": topic,
            "type": 2,  # Scheduled meeting
            "start_time": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "duration": duration_minutes,
            "timezone": timezone,
            "settings": {
                "host_video": True,
                "participant_video": True,
                "join_before_host": True,
                "mute_upon_entry": True,
                "auto_recording": auto_recording,
                "waiting_room": waiting_room,
            },
        }

        if password:
            body["password"] = password
        if agenda:
            body["agenda"] = agenda

        data = await self._request("POST", "/users/me/meetings", json=body)

        return ZoomMeeting(
            id=str(data["id"]),
            join_url=data["join_url"],
            start_url=data["start_url"],
            password=data.get("password"),
            topic=data["topic"],
            start_time=datetime.fromisoformat(data["start_time"].replace("Z", "+00:00")),
            duration=data["duration"],
        )

    async def get_meeting(self, meeting_id: str) -> ZoomMeeting:
        """Get meeting details by ID."""
        data = await self._request("GET", f"/meetings/{meeting_id}")

        return ZoomMeeting(
            id=str(data["id"]),
            join_url=data["join_url"],
            start_url=data["start_url"],
            password=data.get("password"),
            topic=data["topic"],
            start_time=datetime.fromisoformat(data["start_time"].replace("Z", "+00:00"))
            if data.get("start_time")
            else None,
            duration=data.get("duration", 60),
        )

    async def delete_meeting(self, meeting_id: str) -> bool:
        """Delete a meeting."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.BASE_URL}/meetings/{meeting_id}",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                )
                return response.status_code == 204
        except Exception as e:
            logger.error(f"Failed to delete Zoom meeting: {e}")
            return False

    async def list_meetings(
        self,
        type: str = "scheduled",  # "scheduled", "live", "upcoming"
    ) -> list[ZoomMeeting]:
        """List user's meetings."""
        data = await self._request("GET", "/users/me/meetings", params={"type": type})

        meetings = []
        for meeting in data.get("meetings", []):
            meetings.append(
                ZoomMeeting(
                    id=str(meeting["id"]),
                    join_url=meeting["join_url"],
                    start_url="",  # Not included in list
                    topic=meeting["topic"],
                    start_time=datetime.fromisoformat(meeting["start_time"].replace("Z", "+00:00"))
                    if meeting.get("start_time")
                    else None,
                    duration=meeting.get("duration", 60),
                )
            )

        return meetings


class ZoomAuthError(Exception):
    """Raised when Zoom authentication fails."""
    pass


class ZoomTokenExpiredError(Exception):
    """Raised when Zoom token is expired."""
    pass
