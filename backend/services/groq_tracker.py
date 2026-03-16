"""
Groq usage tracker — monitors daily API call quota via Redis.

Redis key patterns:
  groq:usage:{YYYY-MM-DD}  — daily call counter (auto-expires at end of day)
  groq:limit_hit           — set when rate limit was hit; expires same time

Key auto-expires at midnight UTC via TTL.
Threshold: switch to Ollama when > 80% of GROQ_DAILY_LIMIT is used.
"""

import logging
import os
from datetime import datetime, timezone, timedelta

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

GROQ_DAILY_LIMIT = int(os.getenv("GROQ_DAILY_LIMIT", "14400"))
GROQ_WARNING_THRESHOLD = float(os.getenv("GROQ_WARNING_THRESHOLD", "0.80"))

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def _get_redis() -> aioredis.Redis:
    """Return a new async Redis client."""
    return aioredis.from_url(REDIS_URL, decode_responses=True)


def _today_key() -> str:
    """Return the Redis key for today's usage counter (UTC date)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"groq:usage:{today}"


def _seconds_until_midnight_utc() -> int:
    """Return the number of seconds until the next UTC midnight."""
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return int((tomorrow - now).total_seconds())


async def increment_usage() -> int:
    """
    Increment today's Groq API call counter in Redis.

    Sets the key to expire at the next UTC midnight so usage resets daily.

    Returns:
        The new call count for today.
    """
    key = _today_key()
    ttl = _seconds_until_midnight_utc()

    async with _get_redis() as r:
        count = await r.incr(key)
        # Set TTL on first increment (or refresh it)
        await r.expire(key, ttl)

    logger.debug("Groq usage incremented: %d / %d", count, GROQ_DAILY_LIMIT)
    return count


async def is_limit_approaching() -> bool:
    """
    Return True if today's Groq usage exceeds GROQ_WARNING_THRESHOLD.

    Also returns True if the limit was explicitly marked as hit
    (e.g. a RateLimitError was caught from the Groq API).

    Used by analyzer.py to decide whether to route to Ollama proactively.
    """
    async with _get_redis() as r:
        # Check explicit limit-hit flag first
        if await r.exists("groq:limit_hit"):
            logger.info("Groq limit_hit flag is set — routing to Ollama.")
            return True

        raw = await r.get(_today_key())

    count = int(raw) if raw else 0
    usage_pct = count / GROQ_DAILY_LIMIT if GROQ_DAILY_LIMIT > 0 else 0.0

    approaching = usage_pct >= GROQ_WARNING_THRESHOLD
    if approaching:
        logger.warning(
            "Groq usage %.1f%% of daily limit (%d/%d) — routing to Ollama.",
            usage_pct * 100,
            count,
            GROQ_DAILY_LIMIT,
        )
    return approaching


async def mark_limit_hit() -> None:
    """
    Mark that the Groq rate limit was hit (forces Ollama for the rest of the day).

    Sets a Redis flag that expires at the next UTC midnight, ensuring Ollama
    is used for all remaining calls today without hammering the Groq API.
    """
    ttl = _seconds_until_midnight_utc()
    async with _get_redis() as r:
        await r.set("groq:limit_hit", "1", ex=ttl)
    logger.warning("Groq rate limit hit — Ollama will be used for the rest of today.")


async def get_usage_stats() -> dict:
    """
    Return a dict with current usage stats. Useful for /health or debug endpoints.
    """
    async with _get_redis() as r:
        raw = await r.get(_today_key())
        limit_hit = bool(await r.exists("groq:limit_hit"))

    count = int(raw) if raw else 0
    usage_pct = count / GROQ_DAILY_LIMIT if GROQ_DAILY_LIMIT > 0 else 0.0

    return {
        "daily_limit": GROQ_DAILY_LIMIT,
        "used_today": count,
        "usage_percent": round(usage_pct * 100, 1),
        "limit_hit": limit_hit,
        "warning_threshold_percent": GROQ_WARNING_THRESHOLD * 100,
    }
