"""
Redis store service for state management.

Handles pending events, user sessions, and caching.
"""

import json
import logging
from datetime import timedelta
from typing import Any, Optional

import redis.asyncio as redis

from api.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Global Redis client
_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client

    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        logger.info("Redis client initialized")

    return _redis_client


async def close_redis():
    """Close Redis connection."""
    global _redis_client

    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis connection closed")


# Key prefixes
PENDING_EVENT_PREFIX = "pending:event:"
PENDING_NOTE_PREFIX = "pending:note:"
USER_STATE_PREFIX = "state:user:"
RATE_LIMIT_PREFIX = "rate:"
CACHE_PREFIX = "cache:"


class RedisStore:
    """Redis store for application state."""

    def __init__(self, client: redis.Redis):
        self.client = client

    # Pending Events
    async def save_pending_event(
        self,
        event_id: str,
        event_data: dict,
        ttl_minutes: int = 30,
    ) -> bool:
        """
        Save a pending event for user confirmation.

        Args:
            event_id: Unique event ID (e.g., "user_id_message_id").
            event_data: Event data dictionary.
            ttl_minutes: Time to live in minutes.

        Returns:
            True if saved successfully.
        """
        key = f"{PENDING_EVENT_PREFIX}{event_id}"
        try:
            await self.client.setex(
                key,
                timedelta(minutes=ttl_minutes),
                json.dumps(event_data, default=str),
            )
            logger.debug(f"Saved pending event: {event_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save pending event: {e}")
            return False

    async def get_pending_event(self, event_id: str) -> Optional[dict]:
        """Get a pending event by ID."""
        key = f"{PENDING_EVENT_PREFIX}{event_id}"
        try:
            data = await self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get pending event: {e}")
            return None

    async def delete_pending_event(self, event_id: str) -> bool:
        """Delete a pending event."""
        key = f"{PENDING_EVENT_PREFIX}{event_id}"
        try:
            await self.client.delete(key)
            logger.debug(f"Deleted pending event: {event_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete pending event: {e}")
            return False

    # User State (for multi-step dialogs)
    async def set_user_state(
        self,
        user_id: int,
        state: str,
        data: Optional[dict] = None,
        ttl_minutes: int = 60,
    ) -> bool:
        """
        Set user state for multi-step dialogs.

        Args:
            user_id: Telegram user ID.
            state: State name (e.g., "awaiting_time", "selecting_calendar").
            data: Additional state data.
            ttl_minutes: Time to live.

        Returns:
            True if saved successfully.
        """
        key = f"{USER_STATE_PREFIX}{user_id}"
        state_data = {
            "state": state,
            "data": data or {},
        }
        try:
            await self.client.setex(
                key,
                timedelta(minutes=ttl_minutes),
                json.dumps(state_data, default=str),
            )
            return True
        except Exception as e:
            logger.error(f"Failed to set user state: {e}")
            return False

    async def get_user_state(self, user_id: int) -> Optional[dict]:
        """Get current user state."""
        key = f"{USER_STATE_PREFIX}{user_id}"
        try:
            data = await self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get user state: {e}")
            return None

    async def clear_user_state(self, user_id: int) -> bool:
        """Clear user state."""
        key = f"{USER_STATE_PREFIX}{user_id}"
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Failed to clear user state: {e}")
            return False

    # Rate Limiting
    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """
        Check rate limit for a key.

        Args:
            key: Rate limit key (e.g., "openai:user:123").
            max_requests: Maximum allowed requests.
            window_seconds: Time window in seconds.

        Returns:
            Tuple of (is_allowed, remaining_requests).
        """
        rate_key = f"{RATE_LIMIT_PREFIX}{key}"
        try:
            current = await self.client.incr(rate_key)

            if current == 1:
                await self.client.expire(rate_key, window_seconds)

            remaining = max(0, max_requests - current)
            is_allowed = current <= max_requests

            return is_allowed, remaining
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return True, max_requests  # Fail open

    # Caching
    async def cache_set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int = 300,
    ) -> bool:
        """Set a cache value."""
        cache_key = f"{CACHE_PREFIX}{key}"
        try:
            await self.client.setex(
                cache_key,
                timedelta(seconds=ttl_seconds),
                json.dumps(value, default=str),
            )
            return True
        except Exception as e:
            logger.error(f"Cache set failed: {e}")
            return False

    async def cache_get(self, key: str) -> Optional[Any]:
        """Get a cached value."""
        cache_key = f"{CACHE_PREFIX}{key}"
        try:
            data = await self.client.get(cache_key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Cache get failed: {e}")
            return None

    async def cache_delete(self, key: str) -> bool:
        """Delete a cached value."""
        cache_key = f"{CACHE_PREFIX}{key}"
        try:
            await self.client.delete(cache_key)
            return True
        except Exception as e:
            logger.error(f"Cache delete failed: {e}")
            return False


async def get_store() -> RedisStore:
    """Get RedisStore instance."""
    client = await get_redis()
    return RedisStore(client)
