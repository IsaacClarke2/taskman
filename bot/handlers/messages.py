"""
Message handlers for text, voice, and forwarded messages.
"""

import logging
from typing import Optional

import httpx
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import config

logger = logging.getLogger(__name__)
router = Router()

# Temporary storage for pending events (in production, use Redis)
pending_events: dict[str, dict] = {}


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


def get_event_keyboard(event_id: str) -> InlineKeyboardMarkup:
    """Create inline keyboard for event confirmation."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✓ Создать", callback_data=f"confirm:{event_id}"),
                InlineKeyboardButton(text="✎ Изменить", callback_data=f"edit:{event_id}"),
            ],
            [
                InlineKeyboardButton(text="📅 Другой календарь", callback_data=f"calendar:{event_id}"),
                InlineKeyboardButton(text="✗ Отмена", callback_data=f"cancel:{event_id}"),
            ],
        ]
    )


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
        # Generate event ID
        event_id = f"{user_id}_{message.message_id}"
        pending_events[event_id] = result

        preview = format_event_preview(result)
        keyboard = get_event_keyboard(event_id)

        await message.answer(preview, reply_markup=keyboard)

    elif content_type == "note":
        note_id = f"{user_id}_{message.message_id}"
        pending_events[note_id] = result

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
        pending_events[event_id] = result

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
        pending_events[event_id] = result

        if forwarded_from:
            result["participants"] = result.get("participants", []) + [forwarded_from]

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
    event_data = pending_events.get(event_id)

    if not event_data:
        await callback.answer("Событие устарело", show_alert=True)
        return

    # TODO: Create event via API
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>Событие создано!</b>",
        reply_markup=None,
    )

    # Clean up
    pending_events.pop(event_id, None)
    await callback.answer("Событие создано!")


@router.callback_query(lambda c: c.data.startswith("cancel:"))
async def cancel_event(callback: CallbackQuery):
    """Handle event cancellation."""
    event_id = callback.data.split(":")[1]
    pending_events.pop(event_id, None)

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <i>Отменено</i>",
        reply_markup=None,
    )
    await callback.answer("Отменено")


@router.callback_query(lambda c: c.data.startswith("copy_note:"))
async def copy_note(callback: CallbackQuery):
    """Handle note copy (clipboard bridge for Apple Notes)."""
    note_id = callback.data.split(":")[1]
    note_data = pending_events.get(note_id)

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

    pending_events.pop(note_id, None)
    await callback.answer("Текст готов для копирования!")
