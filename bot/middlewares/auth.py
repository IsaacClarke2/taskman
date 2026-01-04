"""
Authentication middleware for Telegram bot.

Checks if user is registered and injects user data into handler context.
"""

import logging
from typing import Any, Awaitable, Callable, Dict, Optional

import httpx
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from bot.config import config

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    """
    Authentication middleware.

    Verifies user exists in database and injects user data into handlers.
    """

    def __init__(self, require_calendar: bool = False):
        """
        Initialize auth middleware.

        Args:
            require_calendar: If True, also check for connected calendar
        """
        self.require_calendar = require_calendar
        self._user_cache: Dict[int, Dict] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Process event with authentication check."""
        # Extract user from event
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if not user:
            return await handler(event, data)

        user_id = user.id

        # Check cache first
        cached = self._user_cache.get(user_id)
        if cached:
            data["db_user"] = cached
            return await handler(event, data)

        # Fetch user from API
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{config.API_URL}/users/{user_id}",
                )

                if response.status_code == 200:
                    db_user = response.json()
                    self._user_cache[user_id] = db_user
                    data["db_user"] = db_user
                elif response.status_code == 404:
                    # User not registered - still allow /start
                    data["db_user"] = None
                else:
                    logger.warning(f"Failed to fetch user {user_id}: {response.status_code}")
                    data["db_user"] = None

        except Exception as e:
            logger.error(f"Auth check failed for {user_id}: {e}")
            data["db_user"] = None

        return await handler(event, data)

    def clear_cache(self, user_id: int) -> None:
        """Clear cached user data."""
        self._user_cache.pop(user_id, None)
