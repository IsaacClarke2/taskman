"""
Message handlers for text, voice, and forwarded messages.

Uses Redis for state storage instead of in-memory dict.
"""

import json
import logging
from datetime import timedelta
from typing import Optional

import httpx
import redis.asyncio as redis
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import config

logger = logging.getLogger(__name__)
router = Router()

# Redis client for state storage
_redis_client: Optional[redis.Redis] = None

PENDING_KEY_PREFIX = "pending:event:"
PENDING_TTL = timedelta(minutes=30)


async def get_redis() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            config.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def save_pending_event(event_id: str, event_data: dict) -> None:
    """Save pending event to Redis."""
    r = await get_redis()
    await r.setex(
        f"{PENDING_KEY_PREFIX}{event_id}",
        PENDING_TTL,
        json.dumps(event_data, default=str),
    )


async def get_pending_event(event_id: str) -> Optional[dict]:
    """Get pending event from Redis."""
    r = await get_redis()
    data = await r.get(f"{PENDING_KEY_PREFIX}{event_id}")
    if data:
        return json.loads(data)
    return None


async def delete_pending_event(event_id: str) -> None:
    """Delete pending event from Redis."""
    r = await get_redis()
    await r.delete(f"{PENDING_KEY_PREFIX}{event_id}")


async def call_api(endpoint: str, method: str = "POST", **kwargs) -> Optional[dict]:
    """Make API call to backend."""
    url = f"{config.API_URL}{endpoint}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "POST":
                response = await client.post(url, **kwargs)
            else:
                response = await client.get(url, **kwargs)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        logger.error(f"API call failed: {e}")
        return None


def format_event_preview(parsed: dict) -> str:
    """Format parsed event for user preview."""
    title = parsed.get("title", "Событие")
    start = parsed.get("start_datetime", "Не указано")
    location = parsed.get("location", "Не указано")

    # Format datetime if present
    if start and start != "Не указано":
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            start = dt.strftime("%d.%m.%Y %H:%M")
        except:
            pass

    return (
        f"📅 <b>{title}</b>\n"
        f"🕐 {start}\n"
        f"📍 {location}\n"
        f"📅 Календарь: <i>Основной</i>"
    )


def get_event_keyboard(event_id: str, show_conference: bool = True) -> InlineKeyboardMarkup:
    """Create inline keyboard for event confirmation."""
    rows = [
        [
            InlineKeyboardButton(text="✓ Создать", callback_data=f"confirm:{event_id}"),
            InlineKeyboardButton(text="✎ Изменить", callback_data=f"edit:{event_id}"),
        ],
    ]

    if show_conference:
        rows.append([
            InlineKeyboardButton(text="📹 + Google Meet", callback_data=f"meet:{event_id}"),
            InlineKeyboardButton(text="📹 + Zoom", callback_data=f"zoom:{event_id}"),
        ])

    rows.append([
        InlineKeyboardButton(text="📅 Другой календарь", callback_data=f"calendar:{event_id}"),
        InlineKeyboardButton(text="✗ Отмена", callback_data=f"cancel:{event_id}"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_note_keyboard(note_id: str) -> InlineKeyboardMarkup:
    """Create inline keyboard for note (Apple Notes clipboard bridge)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Скопировать", callback_data=f"copy_note:{note_id}"),
                InlineKeyboardButton(text="📓 Открыть Notes", url="mobilenotes://"),
            ],
            [
                InlineKeyboardButton(text="✗ Отмена", callback_data=f"cancel_note:{note_id}"),
            ],
        ]
    )


@router.message(F.text)
async def handle_text(message: Message):
    """Handle text messages."""
    user_id = message.from_user.id
    text = message.text

    logger.info(f"Text from {user_id}: {text[:50]}...")

    # Show typing indicator
    await message.bot.send_chat_action(message.chat.id, "typing")

    # Parse message via API
    result = await call_api(
        "/telegram/parse",
        json={
            "message_type": "text",
            "content": text,
            "user_timezone": "Europe/Moscow",
        },
    )

    if not result:
        await message.answer("❌ Не удалось обработать сообщение. Попробуйте позже.")
        return

    content_type = result.get("content_type", "unclear")

    if content_type == "event":
        # Generate event ID and save to Redis
        event_id = f"{user_id}_{message.message_id}"
        await save_pending_event(event_id, result)

        preview = format_event_preview(result)
        keyboard = get_event_keyboard(event_id)

        await message.answer(preview, reply_markup=keyboard)

    elif content_type == "note":
        note_id = f"{user_id}_{message.message_id}"
        await save_pending_event(note_id, result)

        title = result.get("title", "Заметка")
        content = result.get("note_content", text)

        text_response = (
            f"📓 <b>Готово к сохранению в Apple Notes!</b>\n\n"
            f"<b>{title}</b>\n"
            f"{'─' * 20}\n"
            f"{content[:500]}{'...' if len(content) > 500 else ''}"
        )

        keyboard = get_note_keyboard(note_id)
        await message.answer(text_response, reply_markup=keyboard)

    else:
        clarification = result.get("clarification_needed", "")
        await message.answer(
            f"🤔 Не совсем понял. {clarification}\n\n"
            "Попробуйте уточнить дату и время события."
        )


@router.message(F.voice)
async def handle_voice(message: Message):
    """Handle voice messages."""
    user_id = message.from_user.id
    logger.info(f"Voice from {user_id}")

    await message.answer("🎤 Распознаю голосовое сообщение...")
    await message.bot.send_chat_action(message.chat.id, "typing")

    # Download voice file
    file = await message.bot.get_file(message.voice.file_id)
    file_bytes = await message.bot.download_file(file.file_path)

    # Transcribe via API
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{config.API_URL}/telegram/transcribe",
            content=file_bytes.read(),
            headers={
                "Content-Type": "audio/ogg",
                "X-Filename": "voice.oga",
            },
        )

    if response.status_code != 200:
        await message.answer("❌ Не удалось распознать голосовое сообщение.")
        return

    transcribed_text = response.json().get("text", "")
    logger.info(f"Transcribed: {transcribed_text[:50]}...")

    # Parse transcribed text
    result = await call_api(
        "/telegram/parse",
        json={
            "message_type": "voice",
            "content": transcribed_text,
            "user_timezone": "Europe/Moscow",
        },
    )

    if not result:
        await message.answer(
            f"📝 <i>{transcribed_text}</i>\n\n"
            "❌ Не удалось обработать сообщение."
        )
        return

    content_type = result.get("content_type", "unclear")

    if content_type == "event":
        event_id = f"{user_id}_{message.message_id}"
        await save_pending_event(event_id, result)

        preview = f"📝 <i>{transcribed_text}</i>\n\n" + format_event_preview(result)
        keyboard = get_event_keyboard(event_id)

        await message.answer(preview, reply_markup=keyboard)
    else:
        await message.answer(
            f"📝 <i>{transcribed_text}</i>\n\n"
            "🤔 Не нашёл информацию о событии. Уточните дату и время."
        )


@router.message(F.forward_date)
async def handle_forwarded(message: Message):
    """Handle forwarded messages."""
    user_id = message.from_user.id

    # Get forwarded from info
    forwarded_from = None
    if message.forward_from:
        forwarded_from = message.forward_from.full_name
    elif message.forward_sender_name:
        forwarded_from = message.forward_sender_name

    text = message.text or message.caption or ""

    logger.info(f"Forwarded from {forwarded_from}: {text[:50]}...")

    await message.bot.send_chat_action(message.chat.id, "typing")

    # Parse with forwarded context
    result = await call_api(
        "/telegram/parse",
        json={
            "message_type": "forwarded",
            "content": text,
            "forwarded_from": forwarded_from,
            "user_timezone": "Europe/Moscow",
        },
    )

    if not result:
        await message.answer("❌ Не удалось обработать пересланное сообщение.")
        return

    content_type = result.get("content_type", "unclear")

    if content_type == "event":
        event_id = f"{user_id}_{message.message_id}"

        if forwarded_from:
            result["participants"] = result.get("participants", []) + [forwarded_from]

        await save_pending_event(event_id, result)

        preview = format_event_preview(result)
        if forwarded_from:
            preview += f"\n👤 Участник: {forwarded_from}"

        keyboard = get_event_keyboard(event_id)
        await message.answer(preview, reply_markup=keyboard)
    else:
        await message.answer(
            "🤔 Не нашёл информацию о событии в пересланном сообщении.\n"
            "Попробуйте добавить дату и время."
        )


@router.callback_query(lambda c: c.data.startswith("confirm:"))
async def confirm_event(callback: CallbackQuery):
    """Handle event confirmation."""
    event_id = callback.data.split(":")[1]
    event_data = await get_pending_event(event_id)

    if not event_data:
        await callback.answer("Событие устарело", show_alert=True)
        return

    # TODO: Create event via API
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>Событие создано!</b>",
        reply_markup=None,
    )

    # Clean up
    await delete_pending_event(event_id)
    await callback.answer("Событие создано!")


@router.callback_query(lambda c: c.data.startswith("meet:"))
async def add_google_meet(callback: CallbackQuery):
    """Handle adding Google Meet to event."""
    event_id = callback.data.split(":")[1]
    event_data = await get_pending_event(event_id)

    if not event_data:
        await callback.answer("Событие устарело", show_alert=True)
        return

    # Mark event as needing Google Meet
    event_data["add_conference"] = "google_meet"
    await save_pending_event(event_id, event_data)

    # TODO: Create event with Google Meet via API
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>Событие создано с Google Meet!</b>",
        reply_markup=None,
    )

    await delete_pending_event(event_id)
    await callback.answer("Событие с Google Meet создано!")


@router.callback_query(lambda c: c.data.startswith("zoom:"))
async def add_zoom(callback: CallbackQuery):
    """Handle adding Zoom to event."""
    event_id = callback.data.split(":")[1]
    event_data = await get_pending_event(event_id)

    if not event_data:
        await callback.answer("Событие устарело", show_alert=True)
        return

    # Mark event as needing Zoom
    event_data["add_conference"] = "zoom"
    await save_pending_event(event_id, event_data)

    # TODO: Create event with Zoom via API
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>Событие создано с Zoom!</b>",
        reply_markup=None,
    )

    await delete_pending_event(event_id)
    await callback.answer("Событие с Zoom создано!")


@router.callback_query(lambda c: c.data.startswith("cancel:"))
async def cancel_event(callback: CallbackQuery):
    """Handle event cancellation."""
    event_id = callback.data.split(":")[1]
    await delete_pending_event(event_id)

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <i>Отменено</i>",
        reply_markup=None,
    )
    await callback.answer("Отменено")


@router.callback_query(lambda c: c.data.startswith("copy_note:"))
async def copy_note(callback: CallbackQuery):
    """Handle note copy (clipboard bridge for Apple Notes)."""
    note_id = callback.data.split(":")[1]
    note_data = await get_pending_event(note_id)

    if not note_data:
        await callback.answer("Заметка устарела", show_alert=True)
        return

    title = note_data.get("title", "Заметка")
    content = note_data.get("note_content", "")

    # Format for clipboard
    clipboard_text = f"{title}\n{'─' * len(title)}\n\n{content}"

    await callback.message.edit_text(
        f"📋 <b>Скопируйте текст ниже и вставьте в Apple Notes:</b>\n\n"
        f"<code>{clipboard_text}</code>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📓 Открыть Notes", url="mobilenotes://")]
            ]
        ),
    )

    await delete_pending_event(note_id)
    await callback.answer("Текст готов для копирования!")
