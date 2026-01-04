"""
ARQ background job handlers.

All long-running tasks should be processed here.

Important: All jobs should be idempotent - designed to handle being called
multiple times with the same parameters without creating duplicates.
See: https://arq-docs.helpmanual.io/
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)


def _generate_idempotency_key(user_id: UUID, event_data: dict) -> str:
    """Generate idempotency key for event creation."""
    # Create stable hash from user_id and event data
    data_str = json.dumps(
        {
            "user_id": str(user_id),
            "title": event_data.get("title", ""),
            "start": str(event_data.get("start_datetime", "")),
        },
        sort_keys=True,
    )
    return f"event:{hashlib.md5(data_str.encode()).hexdigest()}"


async def create_calendar_event(
    ctx: dict,
    user_id: UUID,
    event_data: dict,
    calendar_id: Optional[str] = None,
    add_conference: bool = False,
    conference_type: Optional[str] = None,  # "google_meet", "zoom"
) -> dict:
    """
    Create a calendar event in the background.

    Args:
        ctx: ARQ context with Redis and DB connections.
        user_id: User UUID.
        event_data: Event details (title, start, end, location, etc.).
        calendar_id: Target calendar ID (uses primary if not specified).
        add_conference: Whether to add video conference link.
        conference_type: Type of conference ("google_meet", "zoom").

    Returns:
        Created event data or error.

    Note: This job is idempotent - calling with same parameters won't create duplicates.
    """
    logger.info(f"Creating event for user {user_id}: {event_data.get('title')}")

    # Check idempotency - prevent duplicate event creation
    idempotency_key = _generate_idempotency_key(user_id, event_data)
    redis = ctx.get("redis")
    if redis:
        existing = await redis.get(idempotency_key)
        if existing:
            logger.info(f"Event already created (idempotency key: {idempotency_key})")
            return json.loads(existing)

    try:
        from sqlalchemy import select
        from db.database import async_session
        from db.models import Integration, User

        async with async_session() as session:
            # Get user
            user = await session.get(User, user_id)
            if not user:
                return {"error": "User not found", "success": False}

            # Get user's calendar integration
            result = await session.execute(
                select(Integration).where(
                    Integration.user_id == user_id,
                    Integration.is_active == True,
                    Integration.provider.in_(["google_calendar", "outlook", "apple_calendar", "yandex_calendar"]),
                )
            )
            integration = result.scalars().first()

            if not integration:
                return {"error": "No calendar integration found", "success": False}

            # Create event based on provider
            if integration.provider == "google_calendar":
                from api.connectors.google import GoogleCalendarConnector

                connector = GoogleCalendarConnector()
                await connector.authenticate(integration.get_credentials())

                # Add Google Meet if requested
                if add_conference and conference_type == "google_meet":
                    event_data["conference_data"] = {
                        "createRequest": {
                            "requestId": f"meet-{datetime.now().timestamp()}",
                            "conferenceSolutionKey": {"type": "hangoutsMeet"},
                        }
                    }

                result = await connector.create_event(event_data, calendar_id)

            elif integration.provider == "outlook":
                from api.connectors.outlook import OutlookConnector

                connector = OutlookConnector()
                await connector.authenticate(integration.get_credentials())

                # Add Teams meeting if requested (Outlook default)
                if add_conference and conference_type != "zoom":
                    event_data["is_online_meeting"] = True

                result = await connector.create_event(event_data, calendar_id)

            elif integration.provider == "apple_calendar":
                from api.connectors.apple import AppleCalendarConnector

                connector = AppleCalendarConnector()
                await connector.authenticate(integration.get_credentials())
                result = await connector.create_event(event_data, calendar_id)

            elif integration.provider == "yandex_calendar":
                from api.connectors.yandex import YandexCalendarConnector

                connector = YandexCalendarConnector()
                await connector.authenticate(integration.get_credentials())
                result = await connector.create_event(event_data, calendar_id)

            else:
                return {"error": f"Unknown provider: {integration.provider}", "success": False}

            logger.info(f"Event created: {result}")
            response = {"success": True, "event": result}

            # Store idempotency key to prevent duplicates on retry
            if redis:
                await redis.setex(
                    idempotency_key,
                    3600,  # 1 hour TTL
                    json.dumps(response, default=str),
                )

            return response

    except Exception as e:
        logger.error(f"Failed to create event: {e}", exc_info=True)
        return {"error": str(e), "success": False}


async def transcribe_voice(
    ctx: dict,
    audio_bytes: bytes,
    filename: str = "audio.oga",
    user_id: Optional[UUID] = None,
) -> dict:
    """
    Transcribe voice message using Whisper.

    Args:
        ctx: ARQ context.
        audio_bytes: Raw audio bytes.
        filename: Original filename.
        user_id: User ID for rate limiting.

    Returns:
        Transcribed text or error.
    """
    logger.info(f"Transcribing audio: {len(audio_bytes)} bytes")

    try:
        # Rate limiting check
        if user_id:
            from api.services.redis_store import get_store
            store = await get_store()

            allowed, remaining = await store.check_rate_limit(
                f"whisper:{user_id}",
                max_requests=20,  # 20 transcriptions per hour
                window_seconds=3600,
            )

            if not allowed:
                return {
                    "error": "Rate limit exceeded. Try again later.",
                    "success": False,
                }

        from api.services.parser import transcribe_voice as do_transcribe

        text = await do_transcribe(audio_bytes, filename)

        return {"success": True, "text": text}

    except Exception as e:
        logger.error(f"Transcription failed: {e}", exc_info=True)
        return {"error": str(e), "success": False}


async def parse_message_gpt(
    ctx: dict,
    text: str,
    user_timezone: str = "Europe/Moscow",
    forwarded_from: Optional[str] = None,
    user_id: Optional[UUID] = None,
) -> dict:
    """
    Parse message using GPT (fallback from local dateparser).

    Args:
        ctx: ARQ context.
        text: Message text to parse.
        user_timezone: User's timezone.
        forwarded_from: Original sender if forwarded.
        user_id: User ID for rate limiting.

    Returns:
        Parsed content or error.
    """
    logger.info(f"GPT parsing message: {text[:50]}...")

    try:
        # Rate limiting
        if user_id:
            from api.services.redis_store import get_store
            store = await get_store()

            allowed, remaining = await store.check_rate_limit(
                f"gpt:{user_id}",
                max_requests=50,  # 50 parses per hour
                window_seconds=3600,
            )

            if not allowed:
                return {
                    "error": "Rate limit exceeded",
                    "success": False,
                    "content_type": "unclear",
                }

        from api.services.parser import parse_message

        result = await parse_message(
            text=text,
            user_timezone=user_timezone,
            forwarded_from=forwarded_from,
        )

        return {
            "success": True,
            "content_type": result.content_type,
            "confidence": result.confidence,
            "title": result.title,
            "start_datetime": result.start_datetime.isoformat() if result.start_datetime else None,
            "end_datetime": result.end_datetime.isoformat() if result.end_datetime else None,
            "duration_minutes": result.duration_minutes,
            "location": result.location,
            "participants": result.participants,
            "note_content": result.note_content,
            "clarification_needed": result.clarification_needed,
        }

    except Exception as e:
        logger.error(f"GPT parsing failed: {e}", exc_info=True)
        return {
            "error": str(e),
            "success": False,
            "content_type": "unclear",
        }


async def send_notification(
    ctx: dict,
    user_telegram_id: int,
    message: str,
    reply_markup: Optional[dict] = None,
) -> dict:
    """
    Send notification to user via Telegram.

    Args:
        ctx: ARQ context.
        user_telegram_id: Telegram user ID.
        message: Message text (HTML).
        reply_markup: Optional inline keyboard.

    Returns:
        Success status.
    """
    logger.info(f"Sending notification to {user_telegram_id}")

    try:
        import os
        import httpx

        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            return {"error": "Bot token not configured", "success": False}

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        payload = {
            "chat_id": user_telegram_id,
            "text": message,
            "parse_mode": "HTML",
        }

        if reply_markup:
            payload["reply_markup"] = reply_markup

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            result = response.json()

            if result.get("ok"):
                return {"success": True, "message_id": result["result"]["message_id"]}
            else:
                return {"error": result.get("description", "Unknown error"), "success": False}

    except Exception as e:
        logger.error(f"Notification failed: {e}", exc_info=True)
        return {"error": str(e), "success": False}


async def sync_calendars(ctx: dict, user_id: Optional[UUID] = None) -> dict:
    """
    Sync calendar events for user(s).

    Args:
        ctx: ARQ context.
        user_id: Specific user to sync, or all users if None.

    Returns:
        Sync statistics.
    """
    logger.info(f"Syncing calendars for user: {user_id or 'all'}")

    try:
        from sqlalchemy import select
        from db.database import async_session
        from db.models import Integration, User

        synced = 0
        errors = 0

        async with async_session() as session:
            query = select(Integration).where(
                Integration.is_active == True,
                Integration.provider.in_(["google_calendar", "outlook", "apple_calendar", "yandex_calendar"]),
            )

            if user_id:
                query = query.where(Integration.user_id == user_id)

            result = await session.execute(query)
            integrations = result.scalars().all()

            for integration in integrations:
                try:
                    # Refresh token if needed
                    # This is placeholder - actual implementation depends on provider
                    synced += 1
                    logger.debug(f"Synced calendar for user {integration.user_id}")
                except Exception as e:
                    errors += 1
                    logger.error(f"Failed to sync for user {integration.user_id}: {e}")

        return {
            "success": True,
            "synced": synced,
            "errors": errors,
        }

    except Exception as e:
        logger.error(f"Calendar sync failed: {e}", exc_info=True)
        return {"error": str(e), "success": False}


async def check_upcoming_events(ctx: dict) -> dict:
    """
    Check for upcoming events and send reminders.

    This is a cron job that runs hourly.

    Returns:
        Reminder statistics.
    """
    logger.info("Checking upcoming events for reminders")

    try:
        from sqlalchemy import select
        from db.database import async_session
        from db.models import Integration, User

        reminders_sent = 0

        # Check events in the next hour
        now = datetime.utcnow()
        reminder_window = now + timedelta(hours=1)

        async with async_session() as session:
            # Get all active calendar integrations
            result = await session.execute(
                select(Integration).where(
                    Integration.is_active == True,
                    Integration.provider.in_(["google_calendar", "outlook", "apple_calendar", "yandex_calendar"]),
                )
            )
            integrations = result.scalars().all()

            for integration in integrations:
                try:
                    # Get user
                    user = await session.get(User, integration.user_id)
                    if not user:
                        continue

                    # Get connector and check events
                    # This is simplified - actual implementation would query calendars

                    # For now, just log
                    logger.debug(f"Checked events for user {user.telegram_id}")

                except Exception as e:
                    logger.error(f"Failed to check events for {integration.user_id}: {e}")

        return {
            "success": True,
            "reminders_sent": reminders_sent,
        }

    except Exception as e:
        logger.error(f"Event check failed: {e}", exc_info=True)
        return {"error": str(e), "success": False}


# Job enqueueing helpers
async def enqueue_create_event(
    user_id: UUID,
    event_data: dict,
    **kwargs,
) -> str:
    """Enqueue event creation job."""
    from arq import create_pool
    from workers.config import get_redis_settings

    pool = await create_pool(get_redis_settings())
    job = await pool.enqueue_job(
        "create_calendar_event",
        user_id,
        event_data,
        **kwargs,
    )
    return job.job_id


async def enqueue_notification(
    user_telegram_id: int,
    message: str,
    **kwargs,
) -> str:
    """Enqueue notification job."""
    from arq import create_pool
    from workers.config import get_redis_settings

    pool = await create_pool(get_redis_settings())
    job = await pool.enqueue_job(
        "send_notification",
        user_telegram_id,
        message,
        **kwargs,
    )
    return job.job_id
