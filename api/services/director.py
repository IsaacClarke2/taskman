"""
AI Director - Load management and smart routing service.

Decides when to use local parsing vs GPT, manages rate limits,
and optimizes API usage for cost efficiency.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from api.services.redis_store import RedisStore, get_store

logger = logging.getLogger(__name__)


class ProcessingMode(Enum):
    """Processing mode for message parsing."""

    LOCAL_ONLY = "local_only"  # Use only dateparser
    LOCAL_WITH_GPT_FALLBACK = "local_with_gpt_fallback"  # Try local, then GPT
    GPT_ONLY = "gpt_only"  # Use only GPT
    QUEUE_FOR_LATER = "queue_for_later"  # Rate limited, queue for later


class ConfidenceLevel(Enum):
    """Confidence threshold levels."""

    LOW = 0.5
    MEDIUM = 0.7
    HIGH = 0.85


@dataclass
class DirectorDecision:
    """Decision from AI Director about how to process a request."""

    mode: ProcessingMode
    reason: str
    confidence_threshold: float = 0.7
    max_tokens: int = 1000
    temperature: float = 0.1
    delay_seconds: int = 0  # For queued requests


@dataclass
class UsageStats:
    """API usage statistics for a user."""

    gpt_calls_hour: int = 0
    gpt_calls_day: int = 0
    whisper_calls_hour: int = 0
    whisper_calls_day: int = 0
    local_parses_hour: int = 0
    local_parses_day: int = 0
    last_reset_hour: Optional[datetime] = None
    last_reset_day: Optional[datetime] = None


class AIDirector:
    """
    AI Director service for intelligent request routing.

    Manages:
    - When to use local parsing vs GPT
    - Rate limiting per user
    - Cost optimization
    - Load balancing
    """

    # Rate limits per user
    GPT_LIMIT_HOUR = 50  # Max GPT calls per hour
    GPT_LIMIT_DAY = 200  # Max GPT calls per day
    WHISPER_LIMIT_HOUR = 20  # Max Whisper calls per hour
    WHISPER_LIMIT_DAY = 100  # Max Whisper calls per day

    # Confidence thresholds
    LOCAL_CONFIDENCE_THRESHOLD = 0.7  # Below this, use GPT

    def __init__(self, store: Optional[RedisStore] = None):
        """
        Initialize AI Director.

        Args:
            store: Redis store for state. If None, will be fetched on first use.
        """
        self._store = store

    async def get_store(self) -> RedisStore:
        """Get or create Redis store."""
        if self._store is None:
            self._store = await get_store()
        return self._store

    async def decide_parsing_mode(
        self,
        user_id: int,
        message_text: str,
        is_voice: bool = False,
        is_forwarded: bool = False,
    ) -> DirectorDecision:
        """
        Decide how to process a parsing request.

        Args:
            user_id: Telegram user ID.
            message_text: Text to parse.
            is_voice: Whether this is a voice message (already transcribed).
            is_forwarded: Whether message was forwarded.

        Returns:
            DirectorDecision with processing mode and parameters.
        """
        store = await self.get_store()

        # Check rate limits
        gpt_allowed, gpt_remaining = await store.check_rate_limit(
            f"gpt:hour:{user_id}",
            max_requests=self.GPT_LIMIT_HOUR,
            window_seconds=3600,
        )

        gpt_day_allowed, gpt_day_remaining = await store.check_rate_limit(
            f"gpt:day:{user_id}",
            max_requests=self.GPT_LIMIT_DAY,
            window_seconds=86400,
        )

        # Analyze message complexity
        complexity = self._analyze_complexity(message_text)

        # Decision logic
        if not gpt_allowed or not gpt_day_allowed:
            # Rate limited - try local only
            return DirectorDecision(
                mode=ProcessingMode.LOCAL_ONLY,
                reason=f"Rate limit reached (remaining: {gpt_remaining}/hour)",
                confidence_threshold=0.5,  # Accept lower confidence
            )

        if complexity == "simple":
            # Simple messages - local only
            return DirectorDecision(
                mode=ProcessingMode.LOCAL_ONLY,
                reason="Simple message pattern detected",
                confidence_threshold=0.6,
            )

        if complexity == "medium":
            # Medium - try local first
            return DirectorDecision(
                mode=ProcessingMode.LOCAL_WITH_GPT_FALLBACK,
                reason="Medium complexity - local with fallback",
                confidence_threshold=0.7,
            )

        # Complex or forwarded messages - use GPT
        if is_forwarded or complexity == "complex":
            return DirectorDecision(
                mode=ProcessingMode.GPT_ONLY,
                reason="Complex or forwarded message",
                confidence_threshold=0.8,
                max_tokens=1500,  # Allow more tokens for complex parsing
            )

        # Default: local with GPT fallback
        return DirectorDecision(
            mode=ProcessingMode.LOCAL_WITH_GPT_FALLBACK,
            reason="Default processing mode",
            confidence_threshold=0.7,
        )

    async def decide_transcription_mode(
        self,
        user_id: int,
        audio_duration_seconds: int,
    ) -> DirectorDecision:
        """
        Decide how to handle voice transcription.

        Args:
            user_id: Telegram user ID.
            audio_duration_seconds: Voice message duration.

        Returns:
            DirectorDecision for transcription.
        """
        store = await self.get_store()

        # Check Whisper rate limits
        allowed, remaining = await store.check_rate_limit(
            f"whisper:hour:{user_id}",
            max_requests=self.WHISPER_LIMIT_HOUR,
            window_seconds=3600,
        )

        if not allowed:
            # Queue for later
            return DirectorDecision(
                mode=ProcessingMode.QUEUE_FOR_LATER,
                reason=f"Whisper rate limit reached",
                delay_seconds=60,  # Retry in 1 minute
            )

        # Check daily limit
        day_allowed, _ = await store.check_rate_limit(
            f"whisper:day:{user_id}",
            max_requests=self.WHISPER_LIMIT_DAY,
            window_seconds=86400,
        )

        if not day_allowed:
            return DirectorDecision(
                mode=ProcessingMode.QUEUE_FOR_LATER,
                reason="Daily Whisper limit reached",
                delay_seconds=3600,  # Retry in 1 hour
            )

        # Long audio might cost more - still allow but note it
        if audio_duration_seconds > 120:
            logger.info(f"Long audio from user {user_id}: {audio_duration_seconds}s")

        return DirectorDecision(
            mode=ProcessingMode.GPT_ONLY,  # Whisper is always needed
            reason="Transcription allowed",
        )

    def _analyze_complexity(self, text: str) -> str:
        """
        Analyze message complexity.

        Returns:
            "simple", "medium", or "complex"
        """
        text_lower = text.lower()

        # Simple patterns - can be parsed locally
        simple_patterns = [
            # Clear time mentions
            r"завтра в \d{1,2}",
            r"сегодня в \d{1,2}",
            r"в \d{1,2}:\d{2}",
            r"в \d{1,2} час",
            # Simple actions
            r"встреча с \w+",
            r"звонок \w+",
            r"созвон с \w+",
        ]

        import re

        for pattern in simple_patterns:
            if re.search(pattern, text_lower):
                # But check for complexity indicators
                if len(text) > 200:
                    return "medium"
                return "simple"

        # Complex indicators
        complex_indicators = [
            "если", "когда", "после того как", "при условии",
            "перенести", "сдвинуть", "изменить время",
            "каждый", "еженедельно", "ежемесячно",  # Recurring events
            "напомни", "за час до", "за день до",  # Reminders
        ]

        complexity_score = sum(1 for ind in complex_indicators if ind in text_lower)

        if complexity_score >= 2:
            return "complex"
        elif complexity_score == 1 or len(text) > 150:
            return "medium"
        else:
            return "simple"

    async def record_usage(
        self,
        user_id: int,
        usage_type: str,  # "gpt", "whisper", "local"
    ):
        """
        Record API usage for analytics.

        Args:
            user_id: Telegram user ID.
            usage_type: Type of API used.
        """
        store = await self.get_store()

        # Increment hourly counter
        await store.check_rate_limit(
            f"{usage_type}:hour:{user_id}",
            max_requests=999999,  # Just for counting
            window_seconds=3600,
        )

        # Increment daily counter
        await store.check_rate_limit(
            f"{usage_type}:day:{user_id}",
            max_requests=999999,
            window_seconds=86400,
        )

        logger.debug(f"Recorded {usage_type} usage for user {user_id}")

    async def get_user_stats(self, user_id: int) -> dict:
        """
        Get usage statistics for a user.

        Args:
            user_id: Telegram user ID.

        Returns:
            Dictionary with usage stats.
        """
        store = await self.get_store()

        # This is a simplified version - actual implementation would
        # track exact counts rather than rate limit checks
        return {
            "user_id": user_id,
            "message": "Detailed stats tracking requires additional implementation",
        }

    async def should_add_conference(
        self,
        user_id: int,
        event_title: str,
        participants: list[str],
    ) -> Optional[str]:
        """
        Decide if a conference link should be added.

        Args:
            user_id: Telegram user ID.
            event_title: Event title.
            participants: List of participants.

        Returns:
            "google_meet", "zoom", or None.
        """
        title_lower = event_title.lower()

        # Explicit conference mentions
        if "zoom" in title_lower or "зум" in title_lower:
            return "zoom"

        if "meet" in title_lower or "мит" in title_lower:
            return "google_meet"

        # Keywords suggesting online meeting
        online_keywords = ["созвон", "звонок", "онлайн", "online", "remote", "удаленн"]

        if any(kw in title_lower for kw in online_keywords):
            # Default to Google Meet for now
            # Could check user preferences
            return "google_meet"

        # Multiple participants might suggest online meeting
        if len(participants) >= 2:
            # Could suggest adding conference
            return None  # Don't auto-add, but could prompt user

        return None


# Global director instance
_director: Optional[AIDirector] = None


async def get_director() -> AIDirector:
    """Get or create AI Director instance."""
    global _director
    if _director is None:
        _director = AIDirector()
    return _director
