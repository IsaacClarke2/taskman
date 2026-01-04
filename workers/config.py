"""
ARQ worker configuration.

Background job processing for:
- Calendar event creation
- Voice transcription
- GPT parsing
- Notifications
"""

import logging
from datetime import timedelta
from typing import Optional

from arq import cron
from arq.connections import RedisSettings

logger = logging.getLogger(__name__)


def get_redis_settings() -> RedisSettings:
    """Get Redis settings from environment."""
    import os

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Parse Redis URL
    # Format: redis://[[user]:[password]@]host[:port][/db]
    if redis_url.startswith("redis://"):
        redis_url = redis_url[8:]

    # Extract auth if present
    password = None
    if "@" in redis_url:
        auth, redis_url = redis_url.rsplit("@", 1)
        if ":" in auth:
            _, password = auth.split(":", 1)

    # Extract host and port
    if "/" in redis_url:
        redis_url, db = redis_url.split("/", 1)
    else:
        db = "0"

    if ":" in redis_url:
        host, port = redis_url.split(":", 1)
        port = int(port)
    else:
        host = redis_url
        port = 6379

    return RedisSettings(
        host=host,
        port=port,
        password=password,
        database=int(db),
    )


class WorkerSettings:
    """ARQ worker settings class."""

    # Redis connection
    redis_settings = get_redis_settings()

    # Job functions (imported dynamically to avoid circular imports)
    functions = [
        "workers.jobs.create_calendar_event",
        "workers.jobs.transcribe_voice",
        "workers.jobs.parse_message_gpt",
        "workers.jobs.send_notification",
        "workers.jobs.sync_calendars",
        "workers.jobs.check_upcoming_events",
    ]

    # Cron jobs
    cron_jobs = [
        cron(
            "workers.jobs.check_upcoming_events",
            hour=None,  # Every hour
            minute=0,
            run_at_startup=False,
        ),
        cron(
            "workers.jobs.sync_calendars",
            hour={6, 12, 18},  # 3 times a day
            minute=0,
            run_at_startup=False,
        ),
    ]

    # Worker options
    max_jobs = 10  # Maximum concurrent jobs
    job_timeout = 300  # 5 minutes default timeout
    keep_result = 3600  # Keep results for 1 hour
    retry_jobs = True
    max_tries = 3

    # Queue settings
    queue_name = "arq:queue"

    # Job retry delays
    retry_delay = timedelta(seconds=10)

    @staticmethod
    async def on_startup(ctx: dict):
        """Called when worker starts."""
        logger.info("ARQ Worker starting up...")

        # Initialize database connection
        from db.database import init_db
        await init_db()

        # Initialize Redis store
        from api.services.redis_store import get_redis
        ctx["redis"] = await get_redis()

        logger.info("ARQ Worker ready")

    @staticmethod
    async def on_shutdown(ctx: dict):
        """Called when worker shuts down."""
        logger.info("ARQ Worker shutting down...")

        from db.database import close_db
        await close_db()

        from api.services.redis_store import close_redis
        await close_redis()

        logger.info("ARQ Worker stopped")


# Export for arq CLI
class WorkerSettingsExport(WorkerSettings):
    """Exportable worker settings for arq CLI."""

    @classmethod
    def get_functions(cls):
        """Dynamically import job functions."""
        from workers.jobs import (
            check_upcoming_events,
            create_calendar_event,
            parse_message_gpt,
            send_notification,
            sync_calendars,
            transcribe_voice,
        )

        return [
            create_calendar_event,
            transcribe_voice,
            parse_message_gpt,
            send_notification,
            sync_calendars,
            check_upcoming_events,
        ]

    functions = property(get_functions)
