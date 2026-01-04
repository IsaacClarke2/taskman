"""
Pydantic request models for API endpoints.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class TelegramAuthData(BaseModel):
    """Data received from Telegram Login Widget."""

    id: int = Field(..., description="Telegram user ID")
    first_name: str = Field(..., description="User's first name")
    last_name: Optional[str] = Field(None, description="User's last name")
    username: Optional[str] = Field(None, description="User's Telegram username")
    photo_url: Optional[str] = Field(None, description="User's profile photo URL")
    auth_date: int = Field(..., description="Unix timestamp of authentication")
    hash: str = Field(..., description="Authentication hash for verification")


class ParseRequest(BaseModel):
    """Request to parse a message from the bot."""

    message_type: Literal["text", "voice", "forwarded"] = Field(
        ..., description="Type of the original message"
    )
    content: str = Field(..., description="Text content or transcribed voice")
    forwarded_from: Optional[str] = Field(
        None, description="Name of the original sender if forwarded"
    )
    user_timezone: str = Field(
        "Europe/Moscow", description="User's timezone for date/time parsing"
    )


class EventCreateRequest(BaseModel):
    """Request to create a calendar event."""

    title: str = Field(..., min_length=1, max_length=500)
    start: datetime = Field(..., description="Event start time")
    end: datetime = Field(..., description="Event end time")
    location: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    calendar_id: str = Field(..., description="Target calendar ID")


class NoteCreateRequest(BaseModel):
    """Request to create a note."""

    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    database_id: Optional[str] = Field(
        None, description="Notion database ID (optional)"
    )


class IntegrationConnectRequest(BaseModel):
    """Request to connect an integration via OAuth code."""

    code: str = Field(..., description="OAuth authorization code")
    state: Optional[str] = Field(None, description="OAuth state for CSRF protection")


class AppleCalendarConnectRequest(BaseModel):
    """Request to connect Apple Calendar via CalDAV."""

    email: EmailStr = Field(..., description="Apple ID email")
    app_password: str = Field(
        ..., min_length=16, description="App-specific password from Apple"
    )


class CalendarSettingsRequest(BaseModel):
    """Request to update calendar settings."""

    is_primary: Optional[bool] = Field(None)
    is_enabled: Optional[bool] = Field(None)


class UserSettingsRequest(BaseModel):
    """Request to update user settings."""

    timezone: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = Field(None)
