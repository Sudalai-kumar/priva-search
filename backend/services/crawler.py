"""
Crawler service — fetches privacy policy pages and converts them to Markdown.

Fallback chain (per spec §5.3):
  1. Firecrawl (primary) — best quality Markdown
  2. sitemap.xml parsing — find privacy URL from sitemap, then direct fetch
  3. Direct httpx GET — fetch raw HTML, convert with markdownify
  4. Google Cache — GET https://webcache.googleusercontent.com/search?q=cache:{url}
  5. Fail gracefully — return { crawl_status: "failed", ... }

Also tracks Firecrawl consecutive failure count per domain.
If Firecrawl fails > 3 times for a domain → marks brand as crawl_blocked=True.
"""

import logging
import os
import xml.etree.ElementTree as ET
from typing import TypedDict

import httpx
from markdownify import markdownify as md
from sqlalchemy import select, update

from db.database import AsyncSessionLocal
from models.brand import Brand

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT}

# Redis key pattern for Firecrawl consecutive failure count: crawl_fail:{domain}
FIRECRAWL_FAIL_THRESHOLD = 3


class CrawlResult(TypedDict):
    """Result returned by any crawl method."""
    crawl_status: str       # 'ok' | 'failed'
    markdown: str | None
    crawl_method: str       # 'firecrawl' | 'sitemap' | 'direct' | 'google_cache'
    reason: str | None      # Only populated on failure


def _domain_from_url(url: str) -> str:
    """Extract the bare domain from a URL (e.g. 'https://spotify.com/x' → 'spotify.com')."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.netloc.lower().lstrip("www.")


async def _increment_firecrawl_failures(domain: str) -> int:
    """Increment Firecrawl failure counter in Redis and return the new count."""
    try:
        import redis.asyncio as aioredis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        async with aioredis.from_url(redis_url, decode_responses=True) as r:
            key = f"crawl_fail:{domain}"
            count = await r.incr(key)
            await r.expire(key, 86400 * 7)  # keep for 7 days
            return count
    except Exception as exc:
        logger.warning("Could not update Firecrawl failure counter: %s", exc)
        return 0


async def _reset_firecrawl_failures(domain: str) -> None:
    """Reset Firecrawl failure counter on success."""
    try:
        import redis.asyncio as aioredis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        async with aioredis.from_url(redis_url, decode_responses=True) as r:
            await r.delete(f"crawl_fail:{domain}")
    except Exception:
        pass


async def _mark_brand_crawl_blocked(domain: str) -> None:
    """Mark a brand as crawl_blocked in the DB after too many Firecrawl failures."""
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Brand)
                .where(Brand.domain == domain)
                .values(crawl_blocked=True)
            )
            await db.commit()
        logger.warning("Marked domain '%s' as crawl_blocked after %d failures.", domain, FIRECRAWL_FAIL_THRESHOLD)
    except Exception as exc:
        logger.error("Could not mark brand crawl_blocked: %s", exc)


def _html_to_markdown(html: str) -> str | None:
    """Convert HTML to Markdown and return None if content is too sparse."""
    result = md(html, heading_style="ATX")
    return result if len(result.strip()) > 100 else None


async def crawl_privacy_policy(url: str) -> CrawlResult:
    """
    Attempt to fetch and convert a privacy policy URL to Markdown.

    Uses the 4-step fallback chain defined in spec §5.3.
    Logs which method succeeded for every crawl.

    Args:
        url: Full URL of the privacy policy page.

    Returns:
        CrawlResult with status, markdown, method used, and optional reason.
    """
    domain = _domain_from_url(url)
    api_key = os.getenv("FIRECRAWL_API_KEY", "")

    # ── Step 1: Firecrawl ─────────────────────────────────────────────────────
    if api_key and api_key not in ("your_firecrawl_key_here", "REPLACE_ME"):
        try:
            from firecrawl import FirecrawlApp
            logger.info("Firecrawl attempt for: %s", url)
            app = FirecrawlApp(api_key=api_key)

            # firecrawl-py 4.x uses .scrape(), older uses .scrape_url()
            markdown = None
            success = False

            if hasattr(app, "scrape"):
                doc = app.scrape(url, formats=["markdown"])
                markdown = getattr(doc, "markdown", None)
                success = (markdown is not None)
            else:
                result = app.scrape_url(url, params={"formats": ["markdown"]})
                markdown = result.get("markdown") if result else None
                success = result.get("success") if result else False

            if success and markdown:
                logger.info("✅ Firecrawl success for %s", url)
                await _reset_firecrawl_failures(domain)
                return {
                    "crawl_status": "ok",
                    "markdown": markdown,
                    "crawl_method": "firecrawl",
                    "reason": None,
                }
            else:
                logger.warning("Firecrawl returned no markdown for %s", url)

        except Exception as exc:
            logger.error("Firecrawl error for %s: %s", url, exc)

        # Count Firecrawl failure
        fail_count = await _increment_firecrawl_failures(domain)
        logger.warning("Firecrawl failure #%d for domain '%s'.", fail_count, domain)
        if fail_count >= FIRECRAWL_FAIL_THRESHOLD:
            await _mark_brand_crawl_blocked(domain)

    # ── Step 2: sitemap.xml parsing ───────────────────────────────────────────
    logger.info("Attempting sitemap.xml lookup for: %s", url)
    sitemap_markdown = await _try_sitemap(url, domain)
    if sitemap_markdown:
        logger.info("✅ sitemap.xml fallback success for %s", url)
        return {
            "crawl_status": "ok",
            "markdown": sitemap_markdown,
            "crawl_method": "sitemap",
            "reason": None,
        }

    # ── Step 3: Direct httpx + markdownify ───────────────────────────────────
    logger.info("Attempting direct crawl for: %s", url)
    direct_result = await _try_direct(url)
    if direct_result:
        logger.info("✅ Direct crawl success for %s", url)
        return {
            "crawl_status": "ok",
            "markdown": direct_result,
            "crawl_method": "direct",
            "reason": None,
        }

    # ── Step 4: Google Cache ──────────────────────────────────────────────────
    logger.info("Attempting Google Cache for: %s", url)
    cache_result = await _try_google_cache(url)
    if cache_result:
        logger.info("✅ Google Cache fallback success for %s", url)
        return {
            "crawl_status": "ok",
            "markdown": cache_result,
            "crawl_method": "google_cache",
            "reason": None,
        }

    # ── Step 5: Fail gracefully ───────────────────────────────────────────────
    reason = f"All crawl methods exhausted for: {url}"
    logger.error(reason)
    return {
        "crawl_status": "failed",
        "markdown": None,
        "crawl_method": "none",
        "reason": reason,
    }


async def _try_sitemap(original_url: str, domain: str) -> str | None:
    """
    Try to find the privacy policy URL from sitemap.xml and fetch it directly.
    Returns Markdown content or None if unsuccessful.
    """
    sitemap_url = f"https://{domain}/sitemap.xml"
    privacy_keywords = ["privacy", "datenschutz", "privacidad"]

    try:
        async with httpx.AsyncClient(timeout=10.0, headers=HEADERS, follow_redirects=True) as client:
            resp = await client.get(sitemap_url)
            resp.raise_for_status()

            # Parse XML and look for privacy-related URLs
            root = ET.fromstring(resp.text)
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

            candidate_url: str | None = None
            for loc in root.findall(".//sm:loc", ns):
                href = (loc.text or "").strip().lower()
                if any(kw in href for kw in privacy_keywords):
                    candidate_url = loc.text.strip()
                    break

            if not candidate_url:
                return None

            # Fetch the found privacy URL
            page_resp = await client.get(candidate_url)
            page_resp.raise_for_status()
            return _html_to_markdown(page_resp.text)

    except Exception as exc:
        logger.debug("sitemap.xml fallback failed for %s: %s", domain, exc)
        return None


async def _try_direct(url: str) -> str | None:
    """
    Fetch the URL directly with httpx and convert HTML to Markdown.
    Returns Markdown content or None if unsuccessful.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=HEADERS, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return _html_to_markdown(resp.text)
    except Exception as exc:
        logger.debug("Direct crawl failed for %s: %s", url, exc)
        return None


async def _try_google_cache(url: str) -> str | None:
    """
    Try Google's cache of the URL as a last resort.
    Returns Markdown content or None if unsuccessful or if Google blocks the request.
    """
    cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{url}"
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=HEADERS, follow_redirects=True) as client:
            resp = await client.get(cache_url)
            if resp.status_code == 200:
                return _html_to_markdown(resp.text)
            logger.debug("Google Cache returned %d for %s", resp.status_code, url)
    except Exception as exc:
        logger.debug("Google Cache fallback failed for %s: %s", url, exc)
    return None
