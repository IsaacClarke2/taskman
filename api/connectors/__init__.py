"""
Connectors package - integrations with external calendar and notes services.
"""

from api.connectors.apple import AppleCalendarConnector
from api.connectors.base import (
    AppleNotesConnector,
    BaseConnector,
    Calendar,
    CalendarConnector,
    Event,
    EventCreate,
    Note,
    NoteCreate,
    NotesConnector,
    TimeSlot,
)
from api.connectors.google import GoogleCalendarConnector
from api.connectors.notion import NotionConnector
from api.connectors.outlook import OutlookConnector
from api.connectors.yandex import YandexCalendarConnector
from api.connectors.zoom import ZoomConnector, ZoomMeeting

__all__ = [
    # Base classes
    "BaseConnector",
    "CalendarConnector",
    "NotesConnector",
    "AppleNotesConnector",
    # Models
    "Calendar",
    "Event",
    "EventCreate",
    "TimeSlot",
    "Note",
    "NoteCreate",
    "ZoomMeeting",
    # Connectors
    "GoogleCalendarConnector",
    "OutlookConnector",
    "AppleCalendarConnector",
    "YandexCalendarConnector",
    "NotionConnector",
    "ZoomConnector",
]
