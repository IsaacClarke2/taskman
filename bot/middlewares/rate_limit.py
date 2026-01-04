"""
Rate limiting middleware for Telegram bot.

Prevents users from overwhelming the bot with too many requests.
Uses sliding window algorithm with Redis backend.
"""

import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional

import redis.asyncio as redis
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from bot.config import config

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """
    Rate limiting middleware using sliding window.

    Limits:
    - Default: 20 requests per minute
    - Voice messages: 10 per minute (more expensive)
    - Callbacks: 30 per minute (lighter operations)
    """

    def __init__(
        self,
        default_limit: int = 20,
        voice_limit: int = 10,
        callback_limit: int = 30,
        window_seconds: int = 60,
    ):
        """
        Initialize rate limiter.

        Args:
            default_limit: Max requests per window for text messages
            voice_limit: Max requests per window for voice messages
            callback_limit: Max requests per window for callbacks
            window_seconds: Window size in seconds
        """
        self.default_limit = default_limit
        self.voice_limit = voice_limit
        self.callback_limit = callback_limit
        self.window_seconds = window_seconds
        self._redis: Optional[redis.Redis] = None

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(
                config.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Process event with rate limiting."""
        # Extract user from event
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if not user:
            return await handler(event, data)

        user_id = user.id

        # Determine limit based on event type
        if isinstance(event, CallbackQuery):
            limit = self.callback_limit
            key_suffix = "callback"
        elif isinstance(event, Message) and event.voice:
            limit = self.voice_limit
            key_suffix = "voice"
        else:
            limit = self.default_limit
            key_suffix = "default"

        # Check rate limit
        is_limited = await self._check_rate_limit(user_id, key_suffix, limit)

        if is_limited:
            logger.warning(f"Rate limit exceeded for user {user_id} ({key_suffix})")

            # Send rate limit message
            if isinstance(event, Message):
                await event.answer(
                    "⏱ Слишком много запросов. Подождите минуту.",
                    disable_notification=True,
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "⏱ Подождите немного...",
                    show_alert=False,
                )
            return

        return await handler(event, data)

    async def _check_rate_limit(
        self,
        user_id: int,
        key_suffix: str,
        limit: int,
    ) -> bool:
        """
        Check and update rate limit using sliding window.

        Returns:
            True if rate limited, False otherwise
        """
        r = await self._get_redis()
        key = f"ratelimit:{user_id}:{key_suffix}"
        now = time.time()
        window_start = now - self.window_seconds

        # Use Redis pipeline for atomic operations
        async with r.pipeline() as pipe:
            # Remove old entries
            await pipe.zremrangebyscore(key, 0, window_start)
            # Count current entries
            await pipe.zcard(key)
            # Add new entry
            await pipe.zadd(key, {str(now): now})
            # Set expiry
            await pipe.expire(key, self.window_seconds + 1)

            results = await pipe.execute()

        current_count = results[1]
        return current_count >= limit

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None
