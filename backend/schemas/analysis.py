"""
Pydantic v2 schemas for AI analysis input/output validation.

The AnalysisOutput schema is the authoritative shape the validator
enforces on raw LLM responses before they touch the database.
"""

from pydantic import BaseModel, Field


class CategoryAnalysis(BaseModel):
    """AI-produced analysis for one of the five risk categories."""

    score: int = Field(ge=1, le=10, description="Risk score: 1 = best privacy, 10 = worst")
    confidence: int = Field(ge=0, le=100, description="Model confidence in this score (0-100)")
    found: bool = Field(description="Whether evidence for this category was found in the policy")
    plain_summary: str = Field(description="Plain-English explanation for non-technical users")
    score_reason: str = Field(description="1-2 sentence reason for the score assigned")
    risk_examples: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Up to 3 concrete examples extracted from the policy text",
    )
    snippet: str | None = Field(
        default=None,
        description="Relevant quote from the privacy policy (max 300 chars)",
    )


class AnalysisOutput(BaseModel):
    """
    Complete structured output from the AI privacy analysis.

    This is the schema the validator enforces on raw LLM responses.
    All five categories must be present with valid scores.
    """

    data_selling: CategoryAnalysis
    ai_training: CategoryAnalysis
    third_party_sharing: CategoryAnalysis
    data_retention: CategoryAnalysis
    deceptive_ux: CategoryAnalysis

    overall_risk_score: int = Field(ge=1, le=10)
    overall_confidence: int = Field(ge=0, le=100)
    summary: str = Field(description="2-3 sentence plain-English summary of the policy")

    # Opt-out data extracted from the policy
    gpc_supported: bool | None = None
    do_not_sell_url: str | None = None
    deletion_request_url: str | None = None
    privacy_contact_email: str | None = None
    opt_out_notes: str | None = None

    # Populated by validator, not LLM
    legal_review_recommended: bool = False
