"""
Date parsing service using dateparser library.

Provides local date/time parsing without OpenAI calls for common patterns.
Falls back to GPT for complex cases.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

import dateparser
import pytz

logger = logging.getLogger(__name__)

# Russian keywords that indicate a note (not an event)
NOTE_KEYWORDS = {
    "идея", "мысль", "заметка", "запомни", "записать", "запиши",
    "нужно купить", "не забыть", "напомни себе", "todo", "список",
}

# Keywords that strongly indicate an event
EVENT_KEYWORDS = {
    "встреча", "звонок", "созвон", "zoom", "зум", "meet", "митинг",
    "собрание", "переговоры", "презентация", "обед", "ужин", "завтрак",
    "прием", "консультация", "интервью", "собеседование", "вебинар",
    "конференция", "семинар", "тренинг", "курс", "урок", "занятие",
}

# Time patterns in Russian
TIME_PATTERNS = {
    r"утром": "10:00",
    r"с утра": "09:00",
    r"днем|днём": "14:00",
    r"после обеда": "14:00",
    r"вечером": "19:00",
    r"ночью": "23:00",
    r"в обед": "13:00",
}

# Duration patterns
DURATION_PATTERNS = {
    r"(\d+)\s*час": lambda m: int(m.group(1)) * 60,
    r"(\d+)\s*мин": lambda m: int(m.group(1)),
    r"полчаса": lambda m: 30,
    r"полтора\s*час": lambda m: 90,
}


class DateParseResult:
    """Result of date parsing attempt."""

    def __init__(
        self,
        success: bool = False,
        start_datetime: Optional[datetime] = None,
        end_datetime: Optional[datetime] = None,
        duration_minutes: int = 60,
        is_note: bool = False,
        is_event: bool = False,
        title: Optional[str] = None,
        location: Optional[str] = None,
        participants: Optional[list] = None,
        confidence: float = 0.0,
        needs_gpt: bool = False,
    ):
        self.success = success
        self.start_datetime = start_datetime
        self.end_datetime = end_datetime
        self.duration_minutes = duration_minutes
        self.is_note = is_note
        self.is_event = is_event
        self.title = title
        self.location = location
        self.participants = participants or []
        self.confidence = confidence
        self.needs_gpt = needs_gpt


def extract_time_from_text(text: str) -> Optional[str]:
    """Extract time from Russian time expressions."""
    text_lower = text.lower()

    for pattern, time_value in TIME_PATTERNS.items():
        if re.search(pattern, text_lower):
            return time_value

    # Look for explicit time patterns like "в 15:00" or "в 3 часа"
    time_match = re.search(r"в\s*(\d{1,2})[:.]?(\d{2})?\s*(час|:)?", text_lower)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0

        # Handle 12-hour format heuristics
        if hour < 8 and "вечер" not in text_lower and "ночь" not in text_lower:
            hour += 12  # Assume PM for business hours

        return f"{hour:02d}:{minute:02d}"

    return None


def extract_duration(text: str) -> int:
    """Extract duration from text in minutes."""
    text_lower = text.lower()

    for pattern, duration_func in DURATION_PATTERNS.items():
        match = re.search(pattern, text_lower)
        if match:
            return duration_func(match)

    return 60  # Default duration


def extract_location(text: str) -> Optional[str]:
    """Extract location from text."""
    text_lower = text.lower()

    # Common location patterns
    location_patterns = [
        r"в\s+(кафе|ресторан[еа]?|офис[еа]?|переговорн\w+|конференц[- ]зал\w*)\s*[«\"']?(\w+)?[»\"']?",
        r"на\s+(адрес[еа]?|улиц[еа]?)\s+(.+?)(?=[\.,]|$)",
        r"место[:\s]+(.+?)(?=[\.,]|$)",
        r"где[:\s]+(.+?)(?=[\.,]|$)",
    ]

    for pattern in location_patterns:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(0).strip()

    # Check for Zoom/Meet links
    zoom_match = re.search(r"(https?://[^\s]*zoom[^\s]*)", text)
    if zoom_match:
        return zoom_match.group(1)

    meet_match = re.search(r"(https?://meet\.google\.com/[^\s]+)", text)
    if meet_match:
        return meet_match.group(1)

    return None


def extract_participants(text: str) -> list:
    """Extract participant names from text."""
    participants = []
    text_lower = text.lower()

    # Patterns for participants
    patterns = [
        r"с\s+(\w+(?:\s+\w+)?)",  # "с Иваном", "с Иваном Петровым"
        r"встреча\s+с\s+(\w+(?:\s+\w+)?)",
        r"звонок\s+(\w+)",
        r"созвон\s+с\s+(\w+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            name = match.group(1).strip()
            # Filter out common non-name words
            if name not in {"утра", "вечера", "обеда", "завтра", "послезавтра"}:
                participants.append(name.title())

    return list(set(participants))


def detect_content_type(text: str) -> Tuple[str, float]:
    """
    Detect if text is about an event or a note.

    Returns:
        Tuple of (content_type, confidence)
    """
    text_lower = text.lower()

    # Check for note keywords
    note_score = sum(1 for kw in NOTE_KEYWORDS if kw in text_lower)

    # Check for event keywords
    event_score = sum(1 for kw in EVENT_KEYWORDS if kw in text_lower)

    # Check for date/time indicators
    has_date = bool(dateparser.parse(
        text,
        languages=["ru", "en"],
        settings={"STRICT_PARSING": True}
    ))

    # Has explicit time
    has_time = bool(extract_time_from_text(text)) or bool(
        re.search(r"\d{1,2}[:.]?\d{0,2}\s*(час|:)", text_lower)
    )

    if note_score > 0 and event_score == 0 and not has_time:
        return "note", 0.8 + (note_score * 0.05)

    if event_score > 0 or has_time:
        confidence = 0.6 + (event_score * 0.1)
        if has_date:
            confidence += 0.1
        if has_time:
            confidence += 0.1
        return "event", min(confidence, 0.95)

    if has_date:
        return "event", 0.5

    return "unclear", 0.3


def parse_date_local(
    text: str,
    user_timezone: str = "Europe/Moscow",
    reference_date: Optional[datetime] = None,
) -> DateParseResult:
    """
    Parse date/time from text using local dateparser library.

    Args:
        text: Input text to parse.
        user_timezone: User's timezone for date interpretation.
        reference_date: Reference date for relative expressions (default: now).

    Returns:
        DateParseResult with parsed information or needs_gpt=True if complex.
    """
    logger.info(f"Local date parsing: {text[:100]}...")

    try:
        tz = pytz.timezone(user_timezone)
    except Exception:
        tz = pytz.timezone("Europe/Moscow")

    if reference_date is None:
        reference_date = datetime.now(tz)

    # Detect content type first
    content_type, confidence = detect_content_type(text)

    result = DateParseResult(
        is_note=(content_type == "note"),
        is_event=(content_type == "event"),
        confidence=confidence,
    )

    # If it's clearly a note, no need for date parsing
    if content_type == "note":
        result.success = True
        # Try to extract a title from the first sentence
        sentences = re.split(r'[.!?\n]', text)
        if sentences:
            result.title = sentences[0].strip()[:100]
        return result

    # Try to parse date
    dateparser_settings = {
        "TIMEZONE": user_timezone,
        "RETURN_AS_TIMEZONE_AWARE": True,
        "PREFER_DATES_FROM": "future",
        "RELATIVE_BASE": reference_date.replace(tzinfo=None),
    }

    parsed_date = dateparser.parse(
        text,
        languages=["ru", "en"],
        settings=dateparser_settings,
    )

    # Extract time separately if dateparser didn't get it
    explicit_time = extract_time_from_text(text)

    if parsed_date:
        result.start_datetime = parsed_date

        # If dateparser got a date but no time, and we have explicit time
        if explicit_time and parsed_date.hour == 0 and parsed_date.minute == 0:
            hour, minute = map(int, explicit_time.split(":"))
            result.start_datetime = parsed_date.replace(hour=hour, minute=minute)

        # Extract duration
        result.duration_minutes = extract_duration(text)

        # Calculate end time
        result.end_datetime = result.start_datetime + timedelta(
            minutes=result.duration_minutes
        )

        result.success = True
        result.confidence = max(result.confidence, 0.7)
    elif explicit_time:
        # We have time but no date - assume today or tomorrow
        hour, minute = map(int, explicit_time.split(":"))
        now = datetime.now(tz)

        result.start_datetime = now.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )

        # If time has passed, assume tomorrow
        if result.start_datetime <= now:
            result.start_datetime += timedelta(days=1)

        result.duration_minutes = extract_duration(text)
        result.end_datetime = result.start_datetime + timedelta(
            minutes=result.duration_minutes
        )

        result.success = True
        result.confidence = 0.6

    # Extract additional info
    result.location = extract_location(text)
    result.participants = extract_participants(text)

    # If we couldn't parse and it's marked as event, need GPT
    if not result.success and content_type == "event":
        result.needs_gpt = True
        result.confidence = 0.3

    # Mark as unclear if very low confidence
    if result.confidence < 0.5 and not result.success:
        result.needs_gpt = True

    return result


def extract_title_from_text(text: str) -> str:
    """Extract a suitable title from the message text."""
    text_lower = text.lower()

    # Common patterns for extracting event titles
    patterns = [
        r"(встреча|звонок|созвон|zoom|зум|собрание)\s+(?:с\s+)?(.+?)(?=\s+(?:в|на|завтра|сегодня|\d)|$)",
        r"(презентация|вебинар|конференция|семинар)\s+(.+?)(?=\s+(?:в|на|завтра|сегодня|\d)|$)",
        r"(обед|ужин|завтрак)\s+(?:с\s+)?(.+?)(?=\s+(?:в|на|завтра|сегодня|\d)|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            event_type = match.group(1).strip().title()
            subject = match.group(2).strip()
            if subject and len(subject) > 2:
                return f"{event_type}: {subject.title()}"
            return event_type

    # Default: first 50 chars
    title = text.split("\n")[0][:50]
    if len(text) > 50:
        title += "..."
    return title
