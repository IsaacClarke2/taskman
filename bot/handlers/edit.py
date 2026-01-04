"""
FSM handlers for event editing workflow.

Uses aiogram FSM with RedisStorage for state persistence.
"""

import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.handlers.messages import (
    delete_pending_event,
    format_event_preview,
    get_event_keyboard,
    get_pending_event,
    save_pending_event,
)
from bot.states import EventEdit

logger = logging.getLogger(__name__)
router = Router()


def get_edit_keyboard(event_id: str) -> InlineKeyboardMarkup:
    """Create keyboard for choosing what to edit."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Название", callback_data=f"edit_title:{event_id}"),
                InlineKeyboardButton(text="🕐 Время", callback_data=f"edit_time:{event_id}"),
            ],
            [
                InlineKeyboardButton(text="📍 Место", callback_data=f"edit_location:{event_id}"),
                InlineKeyboardButton(text="📄 Описание", callback_data=f"edit_desc:{event_id}"),
            ],
            [
                InlineKeyboardButton(text="← Назад", callback_data=f"back_to_preview:{event_id}"),
            ],
        ]
    )


@router.callback_query(lambda c: c.data.startswith("edit:"))
async def start_edit(callback: CallbackQuery, state: FSMContext):
    """Start event editing - show field selection."""
    event_id = callback.data.split(":")[1]
    event_data = await get_pending_event(event_id)

    if not event_data:
        await callback.answer("Событие устарело", show_alert=True)
        return

    # Store event_id in FSM state
    await state.update_data(event_id=event_id)
    await state.set_state(EventEdit.choose_field)

    keyboard = get_edit_keyboard(event_id)
    await callback.message.edit_text(
        "✎ <b>Что изменить?</b>\n\n" + format_event_preview(event_data),
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_title:"))
async def edit_title_start(callback: CallbackQuery, state: FSMContext):
    """Start editing title."""
    event_id = callback.data.split(":")[1]
    event_data = await get_pending_event(event_id)

    if not event_data:
        await callback.answer("Событие устарело", show_alert=True)
        return

    await state.update_data(event_id=event_id)
    await state.set_state(EventEdit.edit_title)

    await callback.message.edit_text(
        f"📝 <b>Текущее название:</b> {event_data.get('title', 'Событие')}\n\n"
        "Введите новое название:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="← Отмена", callback_data=f"back_to_edit:{event_id}")]
            ]
        ),
    )
    await callback.answer()


@router.message(EventEdit.edit_title)
async def edit_title_finish(message: Message, state: FSMContext):
    """Save new title."""
    data = await state.get_data()
    event_id = data.get("event_id")

    if not event_id:
        await message.answer("❌ Событие не найдено")
        await state.clear()
        return

    event_data = await get_pending_event(event_id)
    if not event_data:
        await message.answer("❌ Событие устарело")
        await state.clear()
        return

    # Update title
    event_data["title"] = message.text
    await save_pending_event(event_id, event_data)

    await state.set_state(EventEdit.choose_field)

    preview = format_event_preview(event_data)
    keyboard = get_edit_keyboard(event_id)

    await message.answer(
        f"✅ Название обновлено!\n\n{preview}",
        reply_markup=keyboard,
    )


@router.callback_query(lambda c: c.data.startswith("edit_time:"))
async def edit_time_start(callback: CallbackQuery, state: FSMContext):
    """Start editing time."""
    event_id = callback.data.split(":")[1]
    event_data = await get_pending_event(event_id)

    if not event_data:
        await callback.answer("Событие устарело", show_alert=True)
        return

    await state.update_data(event_id=event_id)
    await state.set_state(EventEdit.edit_time)

    current_time = event_data.get("start_datetime", "Не указано")
    if current_time != "Не указано":
        try:
            dt = datetime.fromisoformat(current_time.replace("Z", "+00:00"))
            current_time = dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            pass

    await callback.message.edit_text(
        f"🕐 <b>Текущее время:</b> {current_time}\n\n"
        "Введите новое время (например: завтра в 15:00, 25 декабря в 10:30):",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="← Отмена", callback_data=f"back_to_edit:{event_id}")]
            ]
        ),
    )
    await callback.answer()


@router.message(EventEdit.edit_time)
async def edit_time_finish(message: Message, state: FSMContext):
    """Parse and save new time."""
    data = await state.get_data()
    event_id = data.get("event_id")

    if not event_id:
        await message.answer("❌ Событие не найдено")
        await state.clear()
        return

    event_data = await get_pending_event(event_id)
    if not event_data:
        await message.answer("❌ Событие устарело")
        await state.clear()
        return

    # Parse time using dateparser
    try:
        import dateparser

        parsed_dt = dateparser.parse(
            message.text,
            languages=["ru", "en"],
            settings={
                "PREFER_DATES_FROM": "future",
                "TIMEZONE": "Europe/Moscow",
            },
        )

        if not parsed_dt:
            await message.answer(
                "❌ Не удалось распознать время.\n"
                "Попробуйте формат: завтра в 15:00, 25.12 в 10:30"
            )
            return

        # Calculate end time (1 hour default)
        from datetime import timedelta
        end_dt = parsed_dt + timedelta(hours=1)

        event_data["start_datetime"] = parsed_dt.isoformat()
        event_data["end_datetime"] = end_dt.isoformat()
        await save_pending_event(event_id, event_data)

        await state.set_state(EventEdit.choose_field)

        preview = format_event_preview(event_data)
        keyboard = get_edit_keyboard(event_id)

        await message.answer(
            f"✅ Время обновлено!\n\n{preview}",
            reply_markup=keyboard,
        )

    except Exception as e:
        logger.error(f"Failed to parse time: {e}")
        await message.answer(
            "❌ Не удалось распознать время.\n"
            "Попробуйте формат: завтра в 15:00, 25.12 в 10:30"
        )


@router.callback_query(lambda c: c.data.startswith("edit_location:"))
async def edit_location_start(callback: CallbackQuery, state: FSMContext):
    """Start editing location."""
    event_id = callback.data.split(":")[1]
    event_data = await get_pending_event(event_id)

    if not event_data:
        await callback.answer("Событие устарело", show_alert=True)
        return

    await state.update_data(event_id=event_id)
    await state.set_state(EventEdit.edit_location)

    current_location = event_data.get("location", "Не указано")

    await callback.message.edit_text(
        f"📍 <b>Текущее место:</b> {current_location}\n\n"
        "Введите новое место:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="← Отмена", callback_data=f"back_to_edit:{event_id}")]
            ]
        ),
    )
    await callback.answer()


@router.message(EventEdit.edit_location)
async def edit_location_finish(message: Message, state: FSMContext):
    """Save new location."""
    data = await state.get_data()
    event_id = data.get("event_id")

    if not event_id:
        await message.answer("❌ Событие не найдено")
        await state.clear()
        return

    event_data = await get_pending_event(event_id)
    if not event_data:
        await message.answer("❌ Событие устарело")
        await state.clear()
        return

    # Update location
    event_data["location"] = message.text
    await save_pending_event(event_id, event_data)

    await state.set_state(EventEdit.choose_field)

    preview = format_event_preview(event_data)
    keyboard = get_edit_keyboard(event_id)

    await message.answer(
        f"✅ Место обновлено!\n\n{preview}",
        reply_markup=keyboard,
    )


@router.callback_query(lambda c: c.data.startswith("edit_desc:"))
async def edit_description_start(callback: CallbackQuery, state: FSMContext):
    """Start editing description."""
    event_id = callback.data.split(":")[1]
    event_data = await get_pending_event(event_id)

    if not event_data:
        await callback.answer("Событие устарело", show_alert=True)
        return

    await state.update_data(event_id=event_id)
    await state.set_state(EventEdit.edit_description)

    current_desc = event_data.get("description", "Не указано")
    if current_desc and len(current_desc) > 100:
        current_desc = current_desc[:100] + "..."

    await callback.message.edit_text(
        f"📄 <b>Текущее описание:</b> {current_desc}\n\n"
        "Введите новое описание:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="← Отмена", callback_data=f"back_to_edit:{event_id}")]
            ]
        ),
    )
    await callback.answer()


@router.message(EventEdit.edit_description)
async def edit_description_finish(message: Message, state: FSMContext):
    """Save new description."""
    data = await state.get_data()
    event_id = data.get("event_id")

    if not event_id:
        await message.answer("❌ Событие не найдено")
        await state.clear()
        return

    event_data = await get_pending_event(event_id)
    if not event_data:
        await message.answer("❌ Событие устарело")
        await state.clear()
        return

    # Update description
    event_data["description"] = message.text
    await save_pending_event(event_id, event_data)

    await state.set_state(EventEdit.choose_field)

    preview = format_event_preview(event_data)
    keyboard = get_edit_keyboard(event_id)

    await message.answer(
        f"✅ Описание обновлено!\n\n{preview}",
        reply_markup=keyboard,
    )


@router.callback_query(lambda c: c.data.startswith("back_to_edit:"))
async def back_to_edit(callback: CallbackQuery, state: FSMContext):
    """Go back to edit field selection."""
    event_id = callback.data.split(":")[1]
    event_data = await get_pending_event(event_id)

    if not event_data:
        await callback.answer("Событие устарело", show_alert=True)
        await state.clear()
        return

    await state.set_state(EventEdit.choose_field)

    keyboard = get_edit_keyboard(event_id)
    await callback.message.edit_text(
        "✎ <b>Что изменить?</b>\n\n" + format_event_preview(event_data),
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("back_to_preview:"))
async def back_to_preview(callback: CallbackQuery, state: FSMContext):
    """Go back to event preview with confirm/cancel buttons."""
    event_id = callback.data.split(":")[1]
    event_data = await get_pending_event(event_id)

    if not event_data:
        await callback.answer("Событие устарело", show_alert=True)
        await state.clear()
        return

    await state.clear()

    preview = format_event_preview(event_data)
    keyboard = get_event_keyboard(event_id)

    await callback.message.edit_text(preview, reply_markup=keyboard)
    await callback.answer()
