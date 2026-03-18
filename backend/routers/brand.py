from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from models.brand import Brand
from models.scorecard import Scorecard
from schemas.scorecard import ScorecardSchema

router = APIRouter(prefix="/brand", tags=["brand"])

@router.get("/{slug}", response_model=ScorecardSchema)
async def get_brand_scorecard(slug: str, db: AsyncSession = Depends(get_db)):
    """
    Returns the most recent privacy scorecard for a brand identified by its slug.
    Loads associated risk categories and opt-out information.
    """
    # 1. Query brand and its most recent scorecard
    stmt = (
        select(Brand)
        .where(Brand.slug == slug)
        # Note: In a production app, we'd probably want the 'latest' scorecard 
        # but here we assume 1:1 for simplicity or take the first.
    )
    result = await db.execute(stmt)
    brand = result.scalar_one_or_none()
    
    if not brand:
        raise HTTPException(status_code=404, detail=f"Brand '{slug}' not found.")
        
    # 2. Fetch the latest complete scorecard with related data
    stmt_sc = (
        select(Scorecard)
        .where(Scorecard.brand_id == brand.id)
        .where(Scorecard.overall_risk_score.isnot(None))
        .order_by(Scorecard.last_scanned_at.desc())
        .options(
            selectinload(Scorecard.risk_categories),
            selectinload(Scorecard.opt_out_info)
        )
        .limit(1)
    )
    result_sc = await db.execute(stmt_sc)
    scorecard = result_sc.scalar_one_or_none()
    
    if not scorecard:
        raise HTTPException(status_code=404, detail=f"No scorecard found for brand '{slug}'.")
        
    # Map privacy_url from brand table
    scorecard_data = ScorecardSchema.model_validate(scorecard)
    scorecard_data.privacy_url = brand.privacy_url
    
    return scorecard_data
