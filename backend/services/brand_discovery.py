import logging
import re
from urllib.parse import urlparse
from sqlalchemy import select, insert, update

from db.database import AsyncSessionLocal
from models.brand import Brand

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Create a URL-safe slug from a domain name."""
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

def is_valid_url(text: str) -> bool:
    """Check if the string is a valid HTTP/HTTPS URL."""
    return text.startswith(("http://", "https://"))

# ─────────────────────────────────────────────────────────────────────────────
# Core Discovery Service
# ─────────────────────────────────────────────────────────────────────────────

async def discover_brand(url: str) -> dict:
    """
    Main entry point for brand discovery (Now repurposed for direct URL entry).
    Resolves a privacy policy URL to a domain and creates a Brand record.
    """
    domain = normalize_domain(url)
    slug = slugify(domain)
    brand_name = domain
    
    # Check Cache / DB
    async with AsyncSessionLocal() as db:
        stmt = select(Brand).where(Brand.slug == slug)
        result = await db.execute(stmt)
        brand_record = result.scalar_one_or_none()
        
        if brand_record:
            # Update existing record
            stmt = (
                update(Brand)
                .where(Brand.id == brand_record.id)
                .values(
                    domain=domain,
                    privacy_url=url
                )
            )
        else:
            # Insert new record
            stmt = insert(Brand).values(
                name=brand_name,
                slug=slug,
                domain=domain,
                privacy_url=url,
                tier=2
            )
        await db.execute(stmt)
        await db.commit()
        
        logger.info(f"Resolved brand discovery: brand={slug} domain={domain} privacy_url={url}")
        return {
            "brand_name": brand_name,
            "slug": slug,
            "domain": domain,
            "privacy_url": url
        }
