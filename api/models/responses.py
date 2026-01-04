"""
Pydantic response models for API endpoints.
"""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    """User data response."""

    id: UUID
    telegram_id: int
    telegram_username: Optional[str]
    email: Optional[str]
    timezone: str
    created_at: datetime

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    """Authentication response with JWT token."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class IntegrationResponse(BaseModel):
    """Integration data response."""

    id: UUID
    provider: str
    is_active: bool
    created_at: datetime
    # Don't expose credentials!
    settings: dict = Field(default_factory=dict)

    class Config:
        from_attributes = True


class CalendarResponse(BaseModel):
    """Calendar data response."""

    id: UUID
    external_id: str
    name: str
    color: Optional[str]
    is_primary: bool
    is_enabled: bool
    provider: str  # Added from integration

    class Config:
        from_attributes = True


class EventResponse(BaseModel):
    """Calendar event response."""

    id: str
    title: str
    start: datetime
    end: datetime
    location: Optional[str]
    calendar_id: str
    calendar_name: str


class TimeSlotResponse(BaseModel):
    """Free time slot response."""

    start: datetime
    end: datetime


class ParsedContentResponse(BaseModel):
    """Parsed message content response."""

    content_type: Literal["event", "note", "reminder", "unclear"]
    confidence: float = Field(..., ge=0.0, le=1.0)

    # For events
    title: Optional[str] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    duration_minutes: int = 60
    location: Optional[str] = None
    participants: list[str] = Field(default_factory=list)

    # For notes
    note_title: Optional[str] = None
    note_content: Optional[str] = None

    # For unclear
    clarification_needed: Optional[str] = None


class ConflictResponse(BaseModel):
    """Calendar conflict response."""

    has_conflict: bool
    conflicting_events: list[EventResponse] = Field(default_factory=list)
    suggested_slots: list[TimeSlotResponse] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """Error response."""

    detail: str
    error_code: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str


class OAuthURLResponse(BaseModel):
    """OAuth authorization URL response."""

    authorization_url: str
    state: str


class IntegrationStatusResponse(BaseModel):
    """Status of all integrations for a user."""

    google_calendar: Optional[IntegrationResponse] = None
    outlook: Optional[IntegrationResponse] = None
    apple_calendar: Optional[IntegrationResponse] = None
    yandex_calendar: Optional[IntegrationResponse] = None
    notion: Optional[IntegrationResponse] = None
    zoom: Optional[IntegrationResponse] = None
    apple_notes: bool = False  # Apple Notes uses clipboard bridge, not OAuth
