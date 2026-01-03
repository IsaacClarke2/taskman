"""
Start command handler.
"""

import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import config

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command."""
    user = message.from_user
    logger.info(f"User started bot: {user.id} (@{user.username})")

    # Welcome message
    text = (
        f"<b>Привет, {user.first_name}!</b>\n\n"
        "Я AI-ассистент для управления календарём и заметками.\n\n"
        "<b>Что я умею:</b>\n"
        "📅 Создавать события в Google/Outlook/Apple Calendar\n"
        "📝 Сохранять заметки в Notion\n"
        "🎤 Распознавать голосовые сообщения\n"
        "↩️ Обрабатывать пересланные сообщения\n\n"
        "<b>Просто отправь мне сообщение, например:</b>\n"
        "<i>«Завтра в 15:00 созвон с Петровым»</i>\n\n"
        "Для начала работы подключи календарь:"
    )

    # Inline keyboard with settings button
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚙️ Настройки",
                    url=f"{config.WEBAPP_URL}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📖 Помощь",
                    callback_data="help",
                )
            ],
        ]
    )

    await message.answer(text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data == "help")
async def show_help(callback_query):
    """Show help message."""
    text = (
        "<b>Как пользоваться:</b>\n\n"
        "1️⃣ <b>Текст:</b> Просто напиши сообщение с датой и временем\n"
        "   <i>«Встреча с инвестором в пятницу в 11:00»</i>\n\n"
        "2️⃣ <b>Голос:</b> Надиктуй голосовое сообщение\n"
        "   <i>«Надо созвониться с юристом на следующей неделе»</i>\n\n"
        "3️⃣ <b>Пересылка:</b> Перешли сообщение из другого чата\n"
        "   Я извлеку дату и создам событие\n\n"
        "4️⃣ <b>Заметки:</b> Начни с «Идея:» или «Заметка:»\n"
        "   <i>«Идея: добавить геймификацию в приложение»</i>\n\n"
        "<b>Команды:</b>\n"
        "/start - Начать работу\n"
        "/settings - Настройки\n"
        "/calendars - Мои календари\n"
    )

    await callback_query.message.edit_text(text)
    await callback_query.answer()
