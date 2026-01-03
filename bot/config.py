"""
Bot configuration.
"""

import os


class BotConfig:
    """Bot configuration from environment."""

    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    API_URL: str = os.getenv("API_URL", "http://api:8000")
    WEBAPP_URL: str = os.getenv("WEBAPP_URL", "https://corben.pro")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379")


config = BotConfig()
