"""
Rate limiting middleware using slowapi + Redis.

Per-IP limits (enforced via slowapi):
  GET  /search          → 30 requests/minute
  POST /scan            → 5 requests/minute, 100 requests/day
  GET  /brand/{slug}    → 60 requests/minute

Abuse prevention:
  - Reject POST /scan where brand_name looks like an IP address or localhost
  - Reject domains that are not valid public TLDs
  - Block IPs that submit > 20 unique brand scans in one hour (1-hour block)
  - Store ip_address on every scan_jobs record for audit purposes (done in queue.py)
"""

import ipaddress
import logging
import os
import re

import redis.asyncio as aioredis
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Maximum unique brand scans per hour before IP is temporarily blocked
ABUSE_SCAN_THRESHOLD = 20
ABUSE_BLOCK_SECONDS = 3600  # 1 hour

# ─────────────────────────────────────────────────────────────────────────────
# Limiter instance (imported by routers that need rate limiting)
# ─────────────────────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address, storage_uri=REDIS_URL)


def setup_rate_limiter(app) -> None:
    """
    Attach slowapi rate limiting middleware to the FastAPI app.

    This must be called in main.py before the app starts serving requests.
    Adds a custom error handler so limit violations return a clean JSON response
    instead of a 429 with HTML body.

    Args:
        app: The FastAPI application instance.
    """
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.middleware import SlowAPIMiddleware

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    logger.info("✅ Rate limiting middleware configured (slowapi + Redis).")


# ─────────────────────────────────────────────────────────────────────────────
# Suspicious input detection
# ─────────────────────────────────────────────────────────────────────────────

_LOCALHOST_PATTERNS = re.compile(
    r"^(localhost|127\.\d+\.\d+\.\d+|::1|0\.0\.0\.0|internal|local)$",
    re.IGNORECASE,
)


def is_suspicious_brand_name(brand_name: str) -> bool:
    """
    Return True if the brand_name looks like an IP address, localhost,
    or otherwise invalid input that could be used for SSRF or abuse.

    Rejects:
    - Raw IPv4 or IPv6 addresses
    - 'localhost', '127.x.x.x', '::1', '0.0.0.0', 'internal', 'local'
    - Brand names that are extremely short (< 2 chars)
    - Brand names with no letters at all

    Args:
        brand_name: Raw user-supplied brand name from POST /scan body.
    """
    cleaned = brand_name.strip()

    # Too short
    if len(cleaned) < 2:
        return True

    # Must contain at least one letter
    if not re.search(r"[a-zA-Z]", cleaned):
        return True

    # Check for localhost patterns
    if _LOCALHOST_PATTERNS.match(cleaned):
        return True

    # Check for raw IP address (IPv4 or IPv6)
    try:
        ipaddress.ip_address(cleaned)
        return True  # It parsed as an IP address
    except ValueError:
        pass

    return False


# ─────────────────────────────────────────────────────────────────────────────
# Hourly scan abuse tracking
# ─────────────────────────────────────────────────────────────────────────────

async def check_and_record_scan(ip_address: str, brand_slug: str) -> bool:
    """
    Track unique brand scans per IP per hour and block abusive IPs.

    - Records each (IP, brand_slug) pair in a Redis set with a 1-hour TTL
    - If the set size exceeds ABUSE_SCAN_THRESHOLD:
        → Sets a block flag for the IP for ABUSE_BLOCK_SECONDS
        → Returns False (caller should reject the scan)
    - Returns True if the scan should be allowed.

    Args:
        ip_address: The client's IP address (from Request).
        brand_slug:  Normalised slug of the brand being scanned.

    Returns:
        True if allowed, False if the IP should be blocked.
    """
    if not ip_address:
        return True  # Can't track without an IP

    block_key = f"abuse:block:{ip_address}"
    scan_set_key = f"abuse:scans:{ip_address}"

    try:
        async with aioredis.from_url(REDIS_URL, decode_responses=True) as r:
            # Check if already blocked
            if await r.exists(block_key):
                logger.warning("Blocked IP %s attempted scan (abuse block active).", ip_address)
                return False

            # Add this brand to the hourly set
            await r.sadd(scan_set_key, brand_slug)
            await r.expire(scan_set_key, ABUSE_BLOCK_SECONDS)  # 1-hour window

            unique_count = await r.scard(scan_set_key)

            if unique_count > ABUSE_SCAN_THRESHOLD:
                # Block the IP for 1 hour
                await r.set(block_key, "1", ex=ABUSE_BLOCK_SECONDS)
                logger.warning(
                    "IP %s has submitted %d unique brand scans in 1 hour — blocked for %ds.",
                    ip_address,
                    unique_count,
                    ABUSE_BLOCK_SECONDS,
                )
                return False

    except Exception as exc:
        # Don't block legitimate traffic due to Redis errors
        logger.error("Abuse check Redis error for IP %s: %s", ip_address, exc)

    return True
