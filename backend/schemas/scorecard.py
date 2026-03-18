"""
Pydantic v2 schemas for scorecard API responses.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RiskCategorySchema(BaseModel):
    """One of the five privacy risk categories in a scorecard."""

    category_key: str
    score: int = Field(ge=1, le=10)
    confidence: int = Field(ge=0, le=100)
    found: bool
    plain_summary: str
    score_reason: str
    risk_examples: list[str] = Field(default_factory=list)
    snippet: str | None = None

    model_config = {"from_attributes": True}


class OptOutInfoSchema(BaseModel):
    """Opt-out and data deletion information for a brand."""

    gpc_supported: bool | None = None
    do_not_sell_url: str | None = None
    deletion_request_url: str | None = None
    privacy_contact_email: str | None = None
    opt_out_notes: str | None = None

    model_config = {"from_attributes": True}


class ScorecardSchema(BaseModel):
    """Full privacy scorecard returned by the API."""

    id: int
    brand_id: int
    overall_risk_score: int | None = None
    overall_confidence: int | None = None
    summary: str | None = None
    trust_status: str | None = None
    last_scanned_at: datetime | None = None
    model_used: str | None = None
    crawl_method_used: str | None = None
    legal_review_recommended: bool = False
    privacy_url: str | None = None
    risk_categories: list[RiskCategorySchema] = Field(default_factory=list)
    opt_out_info: OptOutInfoSchema | None = None

    model_config = {"from_attributes": True}


class ScanJobStatusSchema(BaseModel):
    """Status response for a scan job (polling fallback)."""

    scan_id: str
    status: str
    progress: int = 0
    error_message: str | None = None
    slug: str | None = None
