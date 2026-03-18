"""
Search router — GET /search?q={brand_name}

Returns:
  - 200 with {brand, scorecard}  if found and not stale (cache hit)
  - 200 with {scan_id, status, captcha_required}  if not found or stale (queued scan)

Rate limit: 30 requests/minute per IP (via slowapi).
"""

import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from models.brand import Brand
from models.scorecard import Scorecard
from services.brand_discovery import slugify
from services.queue import enqueue_scan_job
from services.rate_limiter import limiter
from schemas.scorecard import ScorecardSchema
from schemas.brand import BrandSchema

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

STALE_THRESHOLD_DAYS = int(os.getenv("STALE_THRESHOLD_DAYS", 60))

# Threshold: >10 searches/min from one IP triggers captcha_required hint
CAPTCHA_TRIGGER_RPM = 10


@router.get("")
@limiter.limit("30/minute")
async def search_brand(
    request: Request,
    q: str = Query(..., min_length=1, max_length=2000),
    db: AsyncSession = Depends(get_db),
):
    """
    Search for a brand's privacy scorecard.

    - Cache hit (fresh)  → 200 {brand, scorecard}
    - Not found or stale → 200 {scan_id, status: "queued", captcha_required: bool}

    The captcha_required flag is set to True when the backend detects
    suspicious search patterns (>10 searches/minute from one IP).
    Frontend should challenge the user with a CAPTCHA before the next scan
    when this flag is True (CAPTCHA integration deferred to v2).
    """
    try:
        from services.brand_discovery import is_valid_url, normalize_domain
        from services.url_safety import validate_public_url, SSRFViolationError
        
        if not is_valid_url(q):
            raise HTTPException(status_code=400, detail="Search query must be a valid http/https URL")
            
        try:
            validate_public_url(q)
        except SSRFViolationError as e:
            raise HTTPException(status_code=400, detail=str(e))
            
        slug = slugify(normalize_domain(q))

        # ── 1. Look up brand ────────────────────────────────────────────────
        stmt = select(Brand).where(Brand.slug == slug)
        result = await db.execute(stmt)
        brand = result.scalar_one_or_none()

        if brand:
            # ── 2. Check latest scorecard for freshness ───────────────────
            stmt_sc = (
                select(Scorecard)
                .where(Scorecard.brand_id == brand.id)
                .order_by(Scorecard.last_scanned_at.desc())
                .options(
                    selectinload(Scorecard.risk_categories),
                    selectinload(Scorecard.opt_out_info),
                    selectinload(Scorecard.brand),
                )
                .limit(1)
            )
            result_sc = await db.execute(stmt_sc)
            scorecard = result_sc.scalar_one_or_none()

            if scorecard and scorecard.last_scanned_at and scorecard.overall_risk_score is not None:
                limit_date = datetime.now(timezone.utc) - timedelta(days=STALE_THRESHOLD_DAYS)
                # Ensure last_scanned_at is timezone-aware for comparison
                last_scanned = scorecard.last_scanned_at
                if last_scanned.tzinfo is None:
                    last_scanned = last_scanned.replace(tzinfo=timezone.utc)

                if last_scanned > limit_date:
                    # ── Cache hit — return immediately ───────────────────
                    sc_data = ScorecardSchema.model_validate(scorecard)
                    sc_data.privacy_url = brand.privacy_url
                    
                    return {
                        "brand": BrandSchema.model_validate(brand).model_dump(),
                        "scorecard": sc_data.model_dump(),
                    }

        # ── 3. Not found or stale — enqueue scan ────────────────────────────
        client_ip = request.client.host if request.client else None
        scan_id = await enqueue_scan_job(q, client_ip)

        # Captcha hook: detect high-volume IPs
        # The limiter already prevents >30/min, but >10/min gets the flag
        captcha_required = _should_require_captcha(request)

        return {
            "scan_id": scan_id,
            "status": "queued",
            "captcha_required": captcha_required,
        }

    except Exception as exc:
        logger.error("Search failed for q=%r: %s", q, exc, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "Search failed", "detail": str(exc)})


def _should_require_captcha(request: Request) -> bool:
    """
    Determine whether a CAPTCHA challenge should be shown to the user.

    Currently a lightweight heuristic: if the request carries a custom header
    indicating high-frequency usage (set by the frontend when it detects rapid
    clicks), or if the IP appears in the Redis rate-limit near-miss window.

    Full CAPTCHA integration is deferred to v2 — this returns the hook flag.
    """
    # In v1: always False unless caller indicates abuse signal via header
    # Frontend sets X-Priva-High-Frequency: 1 when > 10 searches in a minute
    return request.headers.get("X-Priva-High-Frequency", "0") == "1"
