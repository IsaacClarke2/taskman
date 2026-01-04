"""
Centralized error handlers for Telegram bot.

Handles different types of exceptions with appropriate user messages.
"""

import logging

from aiogram import Bot, Router
from aiogram.filters import ExceptionTypeFilter
from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)
router = Router()


# Custom exceptions
class APIError(Exception):
    """Raised when API call fails."""
    pass


class TranscriptionError(Exception):
    """Raised when voice transcription fails."""
    pass


class CalendarConnectionError(Exception):
    """Raised when calendar connection fails."""
    pass


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    pass


class IntegrationNotConfigured(Exception):
    """Raised when required integration is not connected."""
    pass


@router.errors(ExceptionTypeFilter(APIError))
async def handle_api_error(event: ErrorEvent) -> bool:
    """Handle API errors."""
    logger.error(
        "API error",
        extra={
            "error": str(event.exception),
            "update": event.update.model_dump_json() if event.update else None,
        },
    )

    if event.update and event.update.message:
        await event.update.message.answer(
            "❌ Сервер временно недоступен. Попробуйте позже."
        )
    elif event.update and event.update.callback_query:
        await event.update.callback_query.answer(
            "❌ Ошибка сервера",
            show_alert=True,
        )

    return True  # Error handled


@router.errors(ExceptionTypeFilter(TranscriptionError))
async def handle_transcription_error(event: ErrorEvent) -> bool:
    """Handle voice transcription errors."""
    logger.error(f"Transcription error: {event.exception}")

    if event.update and event.update.message:
        await event.update.message.answer(
            "❌ Не удалось распознать голосовое сообщение.\n"
            "Попробуйте записать ещё раз или отправьте текстом."
        )

    return True


@router.errors(ExceptionTypeFilter(CalendarConnectionError))
async def handle_calendar_error(event: ErrorEvent) -> bool:
    """Handle calendar connection errors."""
    logger.error(f"Calendar connection error: {event.exception}")

    if event.update and event.update.message:
        await event.update.message.answer(
            "❌ Не удалось подключиться к календарю.\n"
            "Проверьте подключение в настройках: /settings"
        )
    elif event.update and event.update.callback_query:
        await event.update.callback_query.answer(
            "❌ Ошибка календаря",
            show_alert=True,
        )

    return True


@router.errors(ExceptionTypeFilter(IntegrationNotConfigured))
async def handle_integration_not_configured(event: ErrorEvent) -> bool:
    """Handle missing integration errors."""
    logger.warning(f"Integration not configured: {event.exception}")

    if event.update and event.update.message:
        await event.update.message.answer(
            "📅 Календарь не подключён.\n\n"
            "Подключите календарь, чтобы создавать события:\n"
            "👉 Нажмите /start → Подключить календарь"
        )

    return True


@router.errors(ExceptionTypeFilter(RateLimitExceeded))
async def handle_rate_limit(event: ErrorEvent) -> bool:
    """Handle rate limit errors."""
    logger.warning(f"Rate limit exceeded: {event.exception}")

    if event.update and event.update.message:
        await event.update.message.answer(
            "⏱ Слишком много запросов. Подождите минуту."
        )

    return True


@router.errors()
async def handle_unknown_error(event: ErrorEvent) -> bool:
    """Handle any unhandled errors."""
    logger.error(
        "Unhandled error",
        extra={
            "error": str(event.exception),
            "error_type": type(event.exception).__name__,
        },
        exc_info=event.exception,
    )

    # Try to notify user
    try:
        if event.update and event.update.message:
            await event.update.message.answer(
                "❌ Произошла непредвиденная ошибка.\n"
                "Мы уже знаем о проблеме и работаем над её решением."
            )
        elif event.update and event.update.callback_query:
            await event.update.callback_query.answer(
                "❌ Ошибка",
                show_alert=True,
            )
    except Exception:
        pass  # Can't notify user, just log

    return True
