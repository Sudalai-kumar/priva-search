"""
APScheduler service — manages automatic re-crawl jobs every 30 days.

- Re-crawls all stored brand privacy policies on RESCAN_INTERVAL_DAYS schedule
- Before re-crawling, compares new policy's SHA-256 hash to stored hash
- If hash unchanged → skip re-analysis, update last_scanned_at only
- If hash changed → enqueue a full scan job via RQ
"""

import hashlib
import logging
import os
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, update

from db.database import AsyncSessionLocal
from models.brand import Brand
from models.scorecard import Scorecard
from services.crawler import crawl_privacy_policy
from services.queue import enqueue_scan_job

logger = logging.getLogger(__name__)

RESCAN_INTERVAL_DAYS = int(os.getenv("RESCAN_INTERVAL_DAYS", "30"))
STALE_THRESHOLD_DAYS = int(os.getenv("STALE_THRESHOLD_DAYS", "60"))

# Module-level scheduler instance
_scheduler: AsyncIOScheduler | None = None


async def _rescan_all_brands() -> None:
    """
    Re-crawl job: iterates every brand with a stored scorecard and decides
    whether to re-analyse or just update the last_scanned_at timestamp.

    Logic per brand:
      1. Fetch the brand's privacy_url and last Scorecard
      2. Crawl the privacy URL to get fresh Markdown
      3. Compute SHA-256 of new Markdown
      4. Compare to stored policy_hash
         - Same hash  → update last_scanned_at only (skip AI call)
         - Diff hash  → enqueue full scan job via RQ
    """
    logger.info("🔄 Scheduled re-crawl job started.")

    async with AsyncSessionLocal() as db:
        # Fetch all brands that have a privacy_url and at least one scorecard
        stmt = (
            select(Brand)
            .where(Brand.privacy_url.isnot(None))
            .where(Brand.crawl_blocked.is_(False))
        )
        result = await db.execute(stmt)
        brands: list[Brand] = list(result.scalars().all())

    logger.info("Found %d brands eligible for re-crawl.", len(brands))

    for brand in brands:
        try:
            await _process_brand(brand)
        except Exception as exc:
            logger.error(
                "Re-crawl failed for brand '%s' (id=%d): %s",
                brand.slug,
                brand.id,
                exc,
            )


async def _process_brand(brand: Brand) -> None:
    """Process a single brand during the scheduled re-crawl."""
    async with AsyncSessionLocal() as db:
        # Get the latest scorecard
        stmt = (
            select(Scorecard)
            .where(Scorecard.brand_id == brand.id)
            .order_by(Scorecard.last_scanned_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        scorecard: Scorecard | None = result.scalar_one_or_none()

        if scorecard is None:
            # No existing scorecard — enqueue a fresh scan
            logger.info(
                "Brand '%s' has no scorecard — enqueuing fresh scan.", brand.slug
            )
            await enqueue_scan_job(brand.privacy_url)
            return

        # 1. Crawl fresh content
        crawl_result = await crawl_privacy_policy(brand.privacy_url)

        if crawl_result["crawl_status"] != "ok" or not crawl_result["markdown"]:
            logger.warning(
                "Re-crawl failed for brand '%s': %s",
                brand.slug,
                crawl_result.get("reason"),
            )
            return

        # 2. Compute new hash
        new_hash = hashlib.sha256(
            crawl_result["markdown"].encode("utf-8")
        ).hexdigest()

        # 3. Compare to stored hash
        if scorecard.policy_hash and scorecard.policy_hash == new_hash:
            # Policy unchanged — just refresh the timestamp
            logger.info(
                "Brand '%s' policy hash unchanged — updating last_scanned_at only.",
                brand.slug,
            )
            await db.execute(
                update(Scorecard)
                .where(Scorecard.id == scorecard.id)
                .values(last_scanned_at=datetime.now(timezone.utc))
            )
            await db.commit()
        else:
            # Policy changed — queue a full re-analysis
            logger.info(
                "Brand '%s' policy hash changed — enqueuing full re-scan.",
                brand.slug,
            )
            await enqueue_scan_job(brand.privacy_url)


async def _mark_stale_scorecards() -> None:
    """
    Daily housekeeping: marks scorecards as 'stale' if they exceed the threshold.
    This ensures the UI reflects data age even before a re-crawl job runs.
    """
    logger.info("🧹 Housekeeping: marking stale scorecards.")
    limit_date = datetime.now(timezone.utc) - timedelta(days=STALE_THRESHOLD_DAYS)

    async with AsyncSessionLocal() as db:
        # Mark all scorecards as stale if last_scanned_at < limit_date
        stmt = (
            update(Scorecard)
            .where(Scorecard.last_scanned_at < limit_date)
            .where(Scorecard.trust_status != "stale")
            .values(trust_status="stale")
        )
        result = await db.execute(stmt)
        await db.commit()

        count = result.rowcount
        if count > 0:
            logger.info("Marked %d scorecards as 'stale'.", count)


async def start_scheduler() -> None:
    """
    Initialize and start the APScheduler background scheduler.

    Schedules a re-crawl job for all brands every RESCAN_INTERVAL_DAYS days.
    Calling this multiple times is safe — it checks if already running.
    """
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        logger.info("Scheduler already running — skipping re-init.")
        return

    _scheduler = AsyncIOScheduler(timezone="UTC")

    _scheduler.add_job(
        _rescan_all_brands,
        trigger=IntervalTrigger(days=RESCAN_INTERVAL_DAYS),
        id="rescan_all_brands",
        replace_existing=True,
        name=f"Re-crawl all brands every {RESCAN_INTERVAL_DAYS} days",
    )

    _scheduler.add_job(
        _mark_stale_scorecards,
        trigger=IntervalTrigger(days=1),  # Run daily
        id="mark_stale_scorecards",
        replace_existing=True,
        name="Mark scorecards older than threshold as stale",
    )

    _scheduler.start()
    logger.info(
        "✅ Scheduler started. Re-crawl interval: every %d day(s).",
        RESCAN_INTERVAL_DAYS,
    )


async def stop_scheduler() -> None:
    """Gracefully stop the APScheduler on app shutdown."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("🛑 Scheduler stopped.")
