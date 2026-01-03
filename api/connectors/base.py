"""
Base connector interfaces for calendar and notes integrations.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class Event(BaseModel):
    """Calendar event model."""

    id: str
    title: str
    start: datetime
    end: datetime
    location: Optional[str] = None
    description: Optional[str] = None
    calendar_id: str


class TimeSlot(BaseModel):
    """Free time slot model."""

    start: datetime
    end: datetime


class Calendar(BaseModel):
    """Calendar metadata model."""

    id: str
    name: str
    color: Optional[str] = None
    is_primary: bool = False


class EventCreate(BaseModel):
    """Event creation input model."""

    title: str
    start: datetime
    end: datetime
    location: Optional[str] = None
    description: Optional[str] = None


class NoteCreate(BaseModel):
    """Note creation input model."""

    title: str
    content: str
    folder: Optional[str] = None


class Note(BaseModel):
    """Note model."""

    id: str
    title: str
    content: str
    url: Optional[str] = None
    created_at: datetime


class BaseConnector(ABC):
    """
    Abstract base class for all connectors.

    All calendar and notes connectors must implement these methods.
    """

    def __init__(self, credentials: dict):
        """
        Initialize connector with credentials.

        Args:
            credentials: Decrypted credentials dict containing tokens/passwords.
        """
        self.credentials = credentials

    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Test if the connection is working.

        Returns:
            True if connection is successful, False otherwise.
        """
        pass

    @abstractmethod
    async def refresh_token(self) -> dict:
        """
        Refresh OAuth tokens if needed.

        Returns:
            Updated credentials dict with new tokens.
        """
        pass


class CalendarConnector(BaseConnector):
    """
    Abstract base class for calendar connectors.

    Implements Google Calendar, Outlook, and Apple Calendar integrations.
    """

    @abstractmethod
    async def list_calendars(self) -> list[Calendar]:
        """
        List all calendars for the user.

        Returns:
            List of Calendar objects.
        """
        pass

    @abstractmethod
    async def create_event(self, calendar_id: str, event: EventCreate) -> Event:
        """
        Create a new event in the specified calendar.

        Args:
            calendar_id: Target calendar ID.
            event: Event data to create.

        Returns:
            Created Event object with ID.
        """
        pass

    @abstractmethod
    async def list_events(
        self, calendar_id: str, start: datetime, end: datetime
    ) -> list[Event]:
        """
        List events in a calendar within a time range.

        Args:
            calendar_id: Calendar to query.
            start: Start of time range.
            end: End of time range.

        Returns:
            List of Event objects.
        """
        pass

    @abstractmethod
    async def get_free_slots(
        self,
        calendar_id: str,
        start: datetime,
        end: datetime,
        duration_minutes: int = 60,
    ) -> list[TimeSlot]:
        """
        Find free time slots in a calendar.

        Args:
            calendar_id: Calendar to check.
            start: Start of search range.
            end: End of search range.
            duration_minutes: Minimum slot duration.

        Returns:
            List of TimeSlot objects representing free time.
        """
        pass

    @abstractmethod
    async def check_conflicts(
        self, calendar_id: str, start: datetime, end: datetime
    ) -> list[Event]:
        """
        Check for conflicting events in a time range.

        Args:
            calendar_id: Calendar to check.
            start: Proposed event start.
            end: Proposed event end.

        Returns:
            List of conflicting Event objects.
        """
        pass


class NotesConnector(BaseConnector):
    """
    Abstract base class for notes connectors.

    Implements Notion integration.
    """

    @abstractmethod
    async def list_databases(self) -> list[dict]:
        """
        List available databases/folders for notes.

        Returns:
            List of database/folder info dicts.
        """
        pass

    @abstractmethod
    async def create_note(
        self, note: NoteCreate, database_id: Optional[str] = None
    ) -> Note:
        """
        Create a new note.

        Args:
            note: Note data to create.
            database_id: Target database/folder (optional).

        Returns:
            Created Note object.
        """
        pass


class AppleNotesConnector:
    """
    Apple Notes connector using clipboard bridge approach.

    Since Apple Notes has no API, we use a clipboard-based approach
    where the user copies the note content and pastes it manually.
    """

    @staticmethod
    def format_for_clipboard(title: str, content: str) -> str:
        """
        Format note content for clipboard copying.

        Args:
            title: Note title.
            content: Note content.

        Returns:
            Formatted string ready for clipboard.
        """
        return f"{title}\n{'─' * len(title)}\n\n{content}"

    @staticmethod
    def get_notes_deep_link() -> str:
        """
        Get the deep link URL to open Apple Notes.

        Returns:
            Deep link URL string.
        """
        return "mobilenotes://"
