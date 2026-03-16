import asyncio
import logging
import re
from urllib.parse import urlparse
import httpx
from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import AsyncSessionLocal
from models.brand import Brand

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants & Config
# ─────────────────────────────────────────────────────────────────────────────
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
GLOBAL_TIMEOUT = 15.0  # Seconds for entire discovery
PROBE_TIMEOUT = 5.0   # Seconds per URL probe
MAX_REDIRECTS = 3

PRIVACY_PATTERNS = [
    "/privacy",
    "/privacy-policy",
    "/legal/privacy",
    "/legal/privacy-policy",
    "/about/privacy",
]

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Create a URL-safe slug from a brand name."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text)
    return text.strip("-")

def normalize_domain(url: str) -> str:
    """Extract and normalize the domain from a URL (e.g., www.spotify.com -> spotify.com)."""
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path  # Handles "spotify.com" vs "https://spotify.com"
    domain = domain.lower().split(":")[0]  # Remove port
    if domain.startswith("www."):
        domain = domain[4:]
    return domain

# ─────────────────────────────────────────────────────────────────────────────
# Core Discovery Service
# ─────────────────────────────────────────────────────────────────────────────

async def discover_brand(brand_name: str) -> dict:
    """
    Main entry point for brand discovery.
    Resolves a brand name to a normalized domain and privacy URL.
    """
    slug = slugify(brand_name)
    
    # 1. Check Cache / DB
    async with AsyncSessionLocal() as db:
        stmt = select(Brand).where(Brand.slug == slug)
        result = await db.execute(stmt)
        brand_record = result.scalar_one_or_none()
        
        if brand_record and brand_record.domain and brand_record.privacy_url:
            logger.info(f"Found cached brand discovery for '{slug}': {brand_record.domain}")
            return {
                "brand_name": brand_record.name,
                "slug": brand_record.slug,
                "domain": brand_record.domain,
                "privacy_url": brand_record.privacy_url
            }

    # 2. External Discovery with Global Timeout
    try:
        async with httpx.AsyncClient(timeout=GLOBAL_TIMEOUT, follow_redirects=True, max_redirects=MAX_REDIRECTS, headers={"User-Agent": USER_AGENT}) as client:
            discovery_data = await _perform_discovery(client, brand_name, slug)
            
            # 3. Persist to DB (Duplicate Protection via Slug)
            async with AsyncSessionLocal() as db:
                if brand_record:
                    # Update existing record
                    stmt = (
                        update(Brand)
                        .where(Brand.id == brand_record.id)
                        .values(
                            domain=discovery_data["domain"],
                            privacy_url=discovery_data["privacy_url"]
                        )
                    )
                else:
                    # Insert new record
                    stmt = insert(Brand).values(
                        name=brand_name,
                        slug=slug,
                        domain=discovery_data["domain"],
                        privacy_url=discovery_data["privacy_url"],
                        tier=2
                    )
                await db.execute(stmt)
                await db.commit()
            
            logger.info(f"Resolved brand discovery: brand={slug} domain={discovery_data['domain']} privacy_url={discovery_data['privacy_url']}")
            return discovery_data

    except Exception as exc:
        logger.error(f"Discovery failed for '{brand_name}': {exc}")
        raise

async def _perform_discovery(client: httpx.AsyncClient, brand_name: str, slug: str) -> dict:
    """Internal discovery logic using external APIs and probing."""
    
    # 1. Query DuckDuckGo for Official Site
    domain = None
    try:
        ddg_url = f"https://api.duckduckgo.com/?q={brand_name}+official+site&format=json"
        resp = await client.get(ddg_url)
        data = resp.json()
        
        # Check 'AbstractURL' or first search result
        official_url = data.get("AbstractURL")
        if official_url:
            domain = normalize_domain(official_url)
    except Exception as e:
        logger.warning(f"DuckDuckGo query failed for '{brand_name}': {e}")

    # 2. Fallback to slug.com
    if not domain:
        domain = f"{slug}.com"
        logger.info(f"Using fallback domain: {domain}")

    # 3. Probe for Privacy URL (HTTPS First)
    found_privacy_url = None
    base_url = f"https://{domain}"
    
    # Try the candidate paths
    for path in PRIVACY_PATTERNS:
        test_url = f"{base_url}{path}"
        try:
            # Short timeout per probe
            resp = await client.head(test_url, timeout=PROBE_TIMEOUT)
            if resp.status_code in (200, 301, 302):
                # Follow redirect manually if HEAD returned 30x to ensure it's valid
                if resp.status_code != 200:
                   resp = await client.get(test_url, timeout=PROBE_TIMEOUT)
                
                if resp.status_code == 200:
                    found_privacy_url = str(resp.url)
                    break
        except Exception:
            continue

    if not found_privacy_url:
        # Last resort fallback if no pattern matched
        found_privacy_url = f"{base_url}/privacy"
        logger.warning(f"No privacy policy found via probing, using default: {found_privacy_url}")

    return {
        "brand_name": brand_name,
        "slug": slug,
        "domain": domain,
        "privacy_url": found_privacy_url
    }
