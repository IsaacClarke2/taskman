"""
Logging middleware for Telegram bot.

Provides structured logging for all incoming events.
"""

import logging
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """
    Logging middleware.

    Logs all incoming events with timing information.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Process event with logging."""
        start_time = time.time()

        # Extract event info
        user_id = None
        username = None
        event_type = type(event).__name__
        event_detail = ""

        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            username = event.from_user.username if event.from_user else None

            if event.text:
                event_detail = f"text: {event.text[:50]}..."
            elif event.voice:
                event_detail = f"voice: {event.voice.duration}s"
            elif event.forward_date:
                event_detail = "forwarded"
            else:
                event_detail = "other"

        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
            username = event.from_user.username if event.from_user else None
            event_detail = f"callback: {event.data}"

        logger.info(
            "Request received",
            extra={
                "user_id": user_id,
                "username": username,
                "event_type": event_type,
                "event_detail": event_detail,
            },
        )

        try:
            result = await handler(event, data)

            duration = (time.time() - start_time) * 1000
            logger.info(
                "Request completed",
                extra={
                    "user_id": user_id,
                    "event_type": event_type,
                    "duration_ms": round(duration, 2),
                    "status": "success",
                },
            )

            return result

        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.error(
                "Request failed",
                extra={
                    "user_id": user_id,
                    "event_type": event_type,
                    "duration_ms": round(duration, 2),
                    "status": "error",
                    "error": str(e),
                },
                exc_info=True,
            )
            raise
