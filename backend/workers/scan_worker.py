"""
Scan worker — RQ async pipeline that drives the full scan lifecycle.

Stages:
  queued → discovery → crawling → analyzing → validating → done | failed

Publishes Redis pub/sub progress events at each stage for the WebSocket
endpoint (/ws/scan/{scan_id}) to forward to connected frontend clients.

Channel pattern: scan:{scan_id}:progress
"""

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timezone

import httpx
import redis as sync_redis
from sqlalchemy import delete, select, update

from db.database import AsyncSessionLocal
from models.brand import Brand
from models.scorecard import OptOutInfo, RiskCategory, ScanJob, Scorecard
from schemas.analysis import AnalysisOutput

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] worker: %(message)s",
)
logger = logging.getLogger("scan_worker")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ─────────────────────────────────────────────────────────────────────────────
# Progress pub/sub helper
# ─────────────────────────────────────────────────────────────────────────────

STAGE_MESSAGES = {
    "queued":     ("Your scan is queued",             5),
    "discovery":  ("Processing URL",                  20),
    "crawling":   ("Reading privacy policy",          40),
    "analyzing":  ("AI is analyzing the policy",      65),
    "validating": ("Verifying results",               85),
    "done":       ("Scan complete",                   100),
    "failed":     ("Scan failed",                      0),
}


def _publish_progress(scan_id: str, stage: str, *, slug: str | None = None, error: str | None = None) -> None:
    """
    Publish a progress event to the Redis pub/sub channel for this scan.

    Uses synchronous Redis client since this function is called from within
    the asyncio event loop via asyncio.run() — the sync client is safer here
    to avoid nested event-loop issues.
    """
    message_text, progress = STAGE_MESSAGES.get(stage, ("Processing…", 0))

    payload: dict = {
        "stage": stage,
        "message": error or message_text,
        "progress": progress,
    }
    if slug:
        payload["slug"] = slug

    try:
        r = sync_redis.from_url(REDIS_URL)
        channel = f"scan:{scan_id}:progress"
        r.publish(channel, json.dumps(payload))
        r.close()
        logger.info("Published progress: scan_id=%s stage=%s", scan_id, stage)
    except Exception as exc:
        logger.warning("Failed to publish progress event: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# RQ Entry Point (Synchronous)
# ─────────────────────────────────────────────────────────────────────────────

def run_scan_job(scan_id: str) -> None:
    """Synchronous bridge for RQ to call the async pipeline."""
    try:
        asyncio.run(_async_scan_pipeline(scan_id))
    except Exception as exc:
        logger.critical("Unhandled exception in worker bridge for %s: %s", scan_id, exc)


# ─────────────────────────────────────────────────────────────────────────────
# Async Scan Pipeline
# ─────────────────────────────────────────────────────────────────────────────

async def _async_scan_pipeline(scan_id: str) -> None:
    """
    Full scan pipeline: discovery → crawling → analyzing → validating → done.
    Publishes Redis pub/sub events at every stage for the WebSocket endpoint.
    """
    logger.info("Starting scan job: %s", scan_id)

    # ── State variables shared across stages ──
    job_brand_id: int | None = None
    job_privacy_url: str | None = None
    scored_markdown: str | None = None
    brand_slug: str | None = None
    brand_tier: int = 2

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(ScanJob).where(ScanJob.id == scan_id))
            job = result.scalar_one_or_none()
            if not job:
                logger.error("Scan job %s not found in database.", scan_id)
                return
            job_url = job.brand_name  # The queue stores the URL in the brand_name column

        # ── DISCOVERY ──────────────────────────────────────────────────────
        await _update_job_status(scan_id, "discovery")
        _publish_progress(scan_id, "discovery")

        from services.brand_discovery import discover_brand
        discovery_data = await discover_brand(job_url)
        brand_slug = discovery_data["slug"]
        job_privacy_url = discovery_data["privacy_url"]

        async with AsyncSessionLocal() as db:
            res = await db.execute(select(Brand).where(Brand.slug == brand_slug))
            brand_obj = res.scalar_one()
            job_brand_id = brand_obj.id
            brand_tier = brand_obj.tier

        # ── CRAWLING ───────────────────────────────────────────────────────
        await _update_job_status(scan_id, "crawling")
        _publish_progress(scan_id, "crawling")

        from services.crawler import crawl_privacy_policy
        crawl_res = await crawl_privacy_policy(job_privacy_url)

        if crawl_res["crawl_status"] != "ok" or not crawl_res.get("markdown"):
            raise RuntimeError(f"Crawl failed: {crawl_res.get('reason', 'unknown')}")

        scored_markdown = crawl_res["markdown"]
        policy_hash = hashlib.sha256(scored_markdown.encode("utf-8")).hexdigest()
        crawl_method = crawl_res["crawl_method"]

        # ── HASH CHECK (Skip if Unchanged) ───────────────────────────────
        async with AsyncSessionLocal() as db:
            res_sc = await db.execute(
                select(Scorecard).where(Scorecard.brand_id == job_brand_id).where(Scorecard.overall_risk_score.isnot(None))
            )
            scorecard = res_sc.scalar_one_or_none()
            if scorecard and scorecard.policy_hash == policy_hash:
                logger.info("Policy hash unchanged — skipping re-analysis.")
                scorecard.last_scanned_at = datetime.now(timezone.utc)
                scorecard.crawl_method_used = crawl_method
                await db.commit()
                await _finish_job(scan_id, brand_slug)
                _publish_progress(scan_id, "done", slug=brand_slug)
                return

        # ── ANALYZING ──────────────────────────────────────────────────────
        await _update_job_status(scan_id, "analyzing")
        _publish_progress(scan_id, "analyzing")

        from services.analyzer import analyze_policy

        # Define a retry function for the validator
        async def retry_ai_call() -> str:
            logger.info("Validator requested retry — calling analyzer again.")
            res_obj = await analyze_policy(scored_markdown)
            return res_obj.model_dump_json()

        # Initial AI Analysis Call
        try:
            analysis_obj = await analyze_policy(scored_markdown)
            raw_json = analysis_obj.model_dump_json()
        except Exception as ai_exc:
            logger.error("AI analysis failed: %s", ai_exc)
            raise

        # ── VALIDATING ─────────────────────────────────────────────────────
        await _update_job_status(scan_id, "validating")
        _publish_progress(scan_id, "validating")

        from services.validator import validate_analysis
        validated_analysis, legal_review = await validate_analysis(raw_json, retry_fn=retry_ai_call)

        # ── WRITE ALL RESULTS TO DB (Single Transaction) ───────────────────
        async with AsyncSessionLocal() as db:
            res_sc = await db.execute(
                select(Scorecard).where(Scorecard.brand_id == job_brand_id)
            )
            scorecard = res_sc.scalar_one_or_none()
            trust_status = _determine_trust_status(tier=brand_tier, legal_review=legal_review)

            if not scorecard:
                scorecard = Scorecard(brand_id=job_brand_id)
                db.add(scorecard)
            
            scorecard.raw_markdown_snapshot = scored_markdown
            scorecard.policy_hash = policy_hash
            scorecard.crawl_method_used = crawl_method
            scorecard.last_scanned_at = datetime.now(timezone.utc)
            scorecard.overall_risk_score = validated_analysis.overall_risk_score
            scorecard.overall_confidence = validated_analysis.overall_confidence
            scorecard.summary = validated_analysis.summary
            scorecard.model_used = "llama-3.3-70b"
            scorecard.trust_status = trust_status
            scorecard.legal_review_recommended = legal_review

            # Clear old and Insert new child records
            await db.execute(delete(RiskCategory).where(RiskCategory.scorecard_id == scorecard.id) if scorecard.id else select(1))
            await db.execute(delete(OptOutInfo).where(OptOutInfo.scorecard_id == scorecard.id) if scorecard.id else select(1))
            await db.flush()

            category_map = {
                "data_selling":       validated_analysis.data_selling,
                "ai_training":        validated_analysis.ai_training,
                "third_party_sharing": validated_analysis.third_party_sharing,
                "data_retention":     validated_analysis.data_retention,
                "deceptive_ux":       validated_analysis.deceptive_ux,
            }
            for key, cat in category_map.items():
                db.add(RiskCategory(
                    scorecard_id=scorecard.id,
                    category_key=key,
                    score=cat.score,
                    confidence=cat.confidence,
                    found=cat.found,
                    plain_summary=cat.plain_summary,
                    score_reason=cat.score_reason,
                    risk_examples=cat.risk_examples,
                    snippet=cat.snippet,
                ))

            db.add(OptOutInfo(
                scorecard_id=scorecard.id,
                gpc_supported=validated_analysis.gpc_supported,
                do_not_sell_url=validated_analysis.do_not_sell_url,
                deletion_request_url=validated_analysis.deletion_request_url,
                privacy_contact_email=validated_analysis.privacy_contact_email,
                opt_out_notes=validated_analysis.opt_out_notes,
            ))

            await db.commit()

        # ── DONE ────────────────────────────────────────────────────────────
        await _finish_job(scan_id, brand_slug)
        _publish_progress(scan_id, "done", slug=brand_slug)
        logger.info("Successfully completed scan job: %s", scan_id)

    except Exception as exc:
        import traceback
        error_trace = traceback.format_exc()
        logger.error("Error in scan job %s: %s\n%s", scan_id, exc, error_trace)
        async with AsyncSessionLocal() as db:
            await db.execute(update(ScanJob).where(ScanJob.id == scan_id).values(
                status="failed", error_message=str(exc), completed_at=datetime.now(timezone.utc),
            ))
            await db.commit()
        _publish_progress(scan_id, "failed", error=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _update_job_status(scan_id: str, status: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(update(ScanJob).where(ScanJob.id == scan_id).values(status=status))
        await db.commit()

async def _finish_job(scan_id: str, slug: str | None) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(update(ScanJob).where(ScanJob.id == scan_id).values(status="done", completed_at=datetime.now(timezone.utc)))
        await db.commit()

def _determine_trust_status(tier: int, legal_review: bool) -> str:
    if legal_review: return "needs_review"
    if tier == 1: return "verified"
    return "ai_generated"
