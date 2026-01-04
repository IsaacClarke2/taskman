"""
Telegram Bot - Main entry point.

Features:
- RedisStorage for FSM state persistence
- Middleware layer (logging, rate limiting, auth)
- Centralized error handling
- Proper resource cleanup
"""

import asyncio
import logging
import os
import sys
from datetime import timedelta

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from bot.config import config
from bot.handlers import edit, errors, messages, start
from bot.middlewares import AuthMiddleware, LoggingMiddleware, RateLimitMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot) -> None:
    """Run on bot startup."""
    logger.info("Bot starting...")

    # Get bot info
    me = await bot.get_me()
    logger.info(f"Bot: @{me.username} (ID: {me.id})")


async def on_shutdown(bot: Bot) -> None:
    """Run on bot shutdown."""
    logger.info("Bot shutting down...")


async def main():
    """Main bot entry point."""
    # Get token from environment
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    # Initialize Redis for FSM storage
    redis = Redis.from_url(
        config.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )

    # Create FSM storage with TTL
    storage = RedisStorage(
        redis=redis,
        state_ttl=timedelta(hours=1),
        data_ttl=timedelta(hours=1),
    )

    # Initialize bot and dispatcher
    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=storage)

    # Register lifecycle hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Register middlewares (order matters!)
    # Outer middlewares run before filters
    dp.message.outer_middleware()(LoggingMiddleware())
    dp.callback_query.outer_middleware()(LoggingMiddleware())

    # Rate limiting
    rate_limiter = RateLimitMiddleware(
        default_limit=20,  # 20 text messages per minute
        voice_limit=10,    # 10 voice messages per minute
        callback_limit=30, # 30 callbacks per minute
    )
    dp.message.outer_middleware()(rate_limiter)
    dp.callback_query.outer_middleware()(rate_limiter)

    # Auth middleware (inner, runs after filters pass)
    dp.message.middleware()(AuthMiddleware())
    dp.callback_query.middleware()(AuthMiddleware())

    # Register error handlers first (catch-all)
    dp.include_router(errors.router)

    # Register handlers
    dp.include_router(start.router)
    dp.include_router(edit.router)  # FSM handlers before general messages
    dp.include_router(messages.router)

    logger.info("Starting bot...")

    # Start polling
    try:
        await dp.start_polling(bot)
    finally:
        # Cleanup resources properly
        logger.info("Cleaning up resources...")

        # Close Redis connections
        from bot.handlers.messages import close_redis
        await close_redis()
        await rate_limiter.close()
        await redis.aclose()

        # Close bot session
        await bot.session.close()

        logger.info("Cleanup complete")


if __name__ == "__main__":
    asyncio.run(main())
