import urllib.parse
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from models.brand import Brand
from models.scorecard import Scorecard, OptOutInfo
from schemas.scorecard import OptOutInfoSchema

router = APIRouter(prefix="/optout", tags=["optout"])

@router.get("/{slug}", response_model=OptOutInfoSchema)
async def get_optout_info(slug: str, db: AsyncSession = Depends(get_db)):
    """
    Returns opt-out and data deletion information for a brand.
    Generates mailto: links if direct URLs are missing.
    """
    # 1. Query brand and latest scorecard
    stmt = (
        select(Brand)
        .where(Brand.slug == slug)
    )
    res_b = await db.execute(stmt)
    brand = res_b.scalar_one_or_none()
    
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found.")
        
    stmt_sc = (
        select(Scorecard)
        .where(Scorecard.brand_id == brand.id)
        .order_by(Scorecard.last_scanned_at.desc())
        .options(selectinload(Scorecard.opt_out_info))
        .limit(1)
    )
    res_sc = await db.execute(stmt_sc)
    scorecard = res_sc.scalar_one_or_none()
    
    if not scorecard or not scorecard.opt_out_info:
        raise HTTPException(status_code=404, detail="Opt-out info not available for this brand.")
        
    info = scorecard.opt_out_info
    
    # Logic: if deletion_request_url is missing but contact email exists, generate mailto
    if not info.deletion_request_url and info.privacy_contact_email:
        subject = f"Data Deletion Request - {brand.name}"
        body = f"Hello,\n\nI would like to request the deletion of all personal data associated with my account at {brand.name} under the CCPA/GDPR right to be forgotten.\n\nThank you."
        mailto = f"mailto:{info.privacy_contact_email}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
        # We can either return this as a field or just populate info object
        # The schema has deletion_request_url, so we can override it if empty for the API response.
        return {
            "gpc_supported": info.gpc_supported,
            "do_not_sell_url": info.do_not_sell_url,
            "deletion_request_url": mailto if not info.deletion_request_url else info.deletion_request_url,
            "privacy_contact_email": info.privacy_contact_email,
            "opt_out_notes": info.opt_out_notes
        }

    return info
