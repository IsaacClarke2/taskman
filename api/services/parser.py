"""
Parser service - Whisper transcription and GPT parsing.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from openai import AsyncOpenAI

from api.config import get_settings
from api.models.responses import ParsedContentResponse

logger = logging.getLogger(__name__)

settings = get_settings()

# Initialize OpenAI client
client = AsyncOpenAI(api_key=settings.openai_api_key)

# GPT prompt for parsing messages
PARSE_PROMPT_TEMPLATE = """You are a message parser for a calendar assistant. Extract event or note information from user messages.

Current datetime: {current_datetime}
User timezone: {user_timezone}
{forwarded_context}

Analyze the message and return ONLY valid JSON:
{{
  "content_type": "event" | "note" | "unclear",
  "confidence": 0.0-1.0,

  "title": "event/note title",
  "start_datetime": "ISO 8601 with timezone or null",
  "end_datetime": "ISO 8601 with timezone or null",
  "duration_minutes": 60,
  "location": "location or null",
  "participants": ["names or emails"],

  "note_content": "for notes only",

  "clarification_needed": "what's missing, if unclear"
}}

Rules:
- If no time specified, set start_datetime to null
- Default duration: 60 minutes
- "завтра" = tomorrow, "послезавтра" = day after tomorrow
- "после обеда" = 14:00, "утром" = 10:00, "вечером" = 19:00
- "на следующей неделе" = next Monday
- Keywords "идея", "мысль", "заметка", "запомни" → content_type = "note"
- Keywords with date/time + action/person → content_type = "event"
- Return ONLY JSON, no markdown, no explanation"""


async def transcribe_voice(audio_bytes: bytes, filename: str = "audio.oga") -> str:
    """
    Transcribe voice message using OpenAI Whisper API.

    Args:
        audio_bytes: Raw audio bytes (Telegram sends .oga format).
        filename: Original filename with extension.

    Returns:
        Transcribed text.

    Raises:
        Exception: If transcription fails.
    """
    logger.info(f"Transcribing audio: {len(audio_bytes)} bytes")

    try:
        # Create a file-like object for the API
        transcription = await client.audio.transcriptions.create(
            model=settings.openai_whisper_model,
            file=(filename, audio_bytes),
            response_format="text",
        )

        logger.info(f"Transcription complete: {len(transcription)} chars")
        return transcription

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise


async def parse_message(
    text: str,
    user_timezone: str = "Europe/Moscow",
    forwarded_from: Optional[str] = None,
) -> ParsedContentResponse:
    """
    Parse a text message using GPT to extract event/note information.

    Args:
        text: Message text (or transcribed voice).
        user_timezone: User's timezone for date/time interpretation.
        forwarded_from: Original sender name if message was forwarded.

    Returns:
        ParsedContentResponse with extracted information.

    Raises:
        Exception: If parsing fails.
    """
    logger.info(f"Parsing message: {text[:100]}...")

    # Build the prompt
    current_datetime = datetime.now().isoformat()
    forwarded_context = (
        f"Message forwarded from: {forwarded_from}" if forwarded_from else ""
    )

    prompt = PARSE_PROMPT_TEMPLATE.format(
        current_datetime=current_datetime,
        user_timezone=user_timezone,
        forwarded_context=forwarded_context,
    )

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            temperature=0.1,  # Low temperature for consistent parsing
            max_tokens=1000,
        )

        result_text = response.choices[0].message.content.strip()

        # Clean up potential markdown formatting
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()

        # Parse JSON response
        parsed_data = json.loads(result_text)

        # Convert to response model
        return ParsedContentResponse(
            content_type=parsed_data.get("content_type", "unclear"),
            confidence=float(parsed_data.get("confidence", 0.5)),
            title=parsed_data.get("title"),
            start_datetime=_parse_datetime(parsed_data.get("start_datetime")),
            end_datetime=_parse_datetime(parsed_data.get("end_datetime")),
            duration_minutes=int(parsed_data.get("duration_minutes", 60)),
            location=parsed_data.get("location"),
            participants=parsed_data.get("participants", []),
            note_title=parsed_data.get("title"),  # Same as title for notes
            note_content=parsed_data.get("note_content"),
            clarification_needed=parsed_data.get("clarification_needed"),
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse GPT response as JSON: {e}")
        return ParsedContentResponse(
            content_type="unclear",
            confidence=0.0,
            clarification_needed="Failed to parse your message. Please try again.",
        )
    except Exception as e:
        logger.error(f"Parsing error: {e}")
        raise


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string to datetime object."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


async def detect_conflicts(
    events: list[dict],
    start: datetime,
    end: datetime,
) -> list[dict]:
    """
    Detect conflicting events in a time range.

    Args:
        events: List of existing events.
        start: Proposed event start.
        end: Proposed event end.

    Returns:
        List of conflicting events.
    """
    conflicts = []

    for event in events:
        event_start = event.get("start")
        event_end = event.get("end")

        if isinstance(event_start, str):
            event_start = datetime.fromisoformat(event_start)
        if isinstance(event_end, str):
            event_end = datetime.fromisoformat(event_end)

        # Check for overlap
        if event_start < end and event_end > start:
            conflicts.append(event)

    return conflicts
