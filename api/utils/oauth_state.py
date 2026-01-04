"""
Redis-based OAuth state storage with TTL.

Replaces in-memory dict to support:
- Multi-instance deployments
- Server restarts
- Automatic expiration
"""

import logging
import secrets
from typing import Optional

import redis.asyncio as redis

from api.config import get_settings

logger = logging.getLogger(__name__)

# Redis client singleton
_redis_client: Optional[redis.Redis] = None

# OAuth state TTL (10 minutes)
OAUTH_STATE_TTL = 600


async def get_redis() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Close Redis connection properly."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("OAuth Redis connection closed")


async def create_oauth_state(provider: str) -> str:
    """
    Create and store OAuth state token.

    Args:
        provider: OAuth provider name (google, outlook, notion, zoom)

    Returns:
        State token for CSRF protection
    """
    r = await get_redis()
    state = secrets.token_urlsafe(32)

    await r.setex(
        f"oauth:state:{state}",
        OAUTH_STATE_TTL,
        provider,
    )

    logger.debug(f"Created OAuth state for {provider}")
    return state


async def validate_oauth_state(state: str, expected_provider: str) -> bool:
    """
    Validate OAuth state token.

    Args:
        state: State token from callback
        expected_provider: Expected provider name

    Returns:
        True if valid, False otherwise
    """
    if not state:
        return False

    r = await get_redis()
    provider = await r.get(f"oauth:state:{state}")

    if provider != expected_provider:
        logger.warning(f"Invalid OAuth state: expected {expected_provider}, got {provider}")
        return False

    return True


async def consume_oauth_state(state: str) -> Optional[str]:
    """
    Validate and consume OAuth state (one-time use).

    Args:
        state: State token from callback

    Returns:
        Provider name if valid, None otherwise
    """
    if not state:
        return None

    r = await get_redis()
    key = f"oauth:state:{state}"

    # Get and delete atomically
    provider = await r.get(key)
    if provider:
        await r.delete(key)
        logger.debug(f"Consumed OAuth state for {provider}")

    return provider
