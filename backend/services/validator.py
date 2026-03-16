"""
Validator service — enforces schema and business rules on raw AI output.

Validation steps:
  1. Check valid JSON — reject and retry if not (max 2 retries)
  2. Validate against AnalysisOutput Pydantic schema
  3. All 5 categories must be present
  4. All scores must be integers in range 1–10
  5. All confidence values must be integers in range 0–100
  6. score_reason and risk_examples present for each category
  7. If any category confidence ≤ 40 → set legal_review_recommended = True
  8. If any category score ≥ 8 → set legal_review_recommended = True
"""

import json
import logging
from typing import Callable, Awaitable

from pydantic import ValidationError

from schemas.analysis import AnalysisOutput, CategoryAnalysis

logger = logging.getLogger(__name__)

MAX_RETRIES = 2

REQUIRED_CATEGORIES = [
    "data_selling",
    "ai_training",
    "third_party_sharing",
    "data_retention",
    "deceptive_ux",
]

LOW_CONFIDENCE_CUTOFF = 40
HIGH_RISK_CUTOFF = 8


def _check_legal_review(output: AnalysisOutput) -> bool:
    """
    Return True if the output warrants a legal review recommendation.

    Triggers if:
    - Any category confidence ≤ 40
    - Any category score ≥ 8
    """
    categories: list[CategoryAnalysis] = [
        output.data_selling,
        output.ai_training,
        output.third_party_sharing,
        output.data_retention,
        output.deceptive_ux,
    ]
    for cat in categories:
        if cat.confidence is not None and cat.confidence <= LOW_CONFIDENCE_CUTOFF:
            logger.info(
                "Legal review triggered: category confidence %d ≤ %d",
                cat.confidence,
                LOW_CONFIDENCE_CUTOFF,
            )
            return True
        if cat.score is not None and cat.score >= HIGH_RISK_CUTOFF:
            logger.info(
                "Legal review triggered: category score %d ≥ %d",
                cat.score,
                HIGH_RISK_CUTOFF,
            )
            return True
    return False


def _validate_categories(output: AnalysisOutput) -> None:
    """
    Raise ValueError if any category fails structural validation.

    Rules applied:
    - All 5 required categories present (guaranteed by Pydantic, but explicit here)
    - Each score is an integer in [1, 10]
    - Each confidence is an integer in [0, 100]
    - score_reason is a non-empty string
    - risk_examples is a list (may be empty)
    """
    category_map: dict[str, CategoryAnalysis] = {
        "data_selling": output.data_selling,
        "ai_training": output.ai_training,
        "third_party_sharing": output.third_party_sharing,
        "data_retention": output.data_retention,
        "deceptive_ux": output.deceptive_ux,
    }

    for key, cat in category_map.items():
        # Score range
        if not isinstance(cat.score, int) or not (1 <= cat.score <= 10):
            raise ValueError(
                f"Category '{key}' has invalid score: {cat.score!r}. Must be int 1–10."
            )
        # Confidence range
        if not isinstance(cat.confidence, int) or not (0 <= cat.confidence <= 100):
            raise ValueError(
                f"Category '{key}' has invalid confidence: {cat.confidence!r}. Must be int 0–100."
            )
        # score_reason present
        if not cat.score_reason or not cat.score_reason.strip():
            raise ValueError(f"Category '{key}' is missing 'score_reason'.")
        # risk_examples is a list
        if not isinstance(cat.risk_examples, list):
            raise ValueError(
                f"Category '{key}' 'risk_examples' must be a list, got {type(cat.risk_examples)}."
            )


async def validate_analysis(
    raw_output: str,
    *,
    retry_fn: Callable[[], Awaitable[str]] | None = None,
) -> tuple[AnalysisOutput, bool]:
    """
    Parse and validate raw LLM JSON output against the AnalysisOutput schema.

    Retries up to MAX_RETRIES times if output is invalid JSON or fails schema
    validation, by calling retry_fn() to get a fresh response.

    Sets legal_review_recommended based on:
    - Any category confidence ≤ 40
    - Any category score ≥ 8

    Args:
        raw_output: Raw string response from the LLM.
        retry_fn:   Optional async callable that returns a fresh raw LLM string.
                    Required to enable retries on invalid output.

    Returns:
        Tuple of (AnalysisOutput, legal_review_recommended: bool)

    Raises:
        ValueError: If output fails validation after all retries.
    """
    last_error: Exception | None = None
    current_raw = raw_output

    for attempt in range(MAX_RETRIES + 1):
        try:
            # Step 1: Confirm it is valid JSON before Pydantic parses it
            try:
                json.loads(current_raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON from LLM: {exc}") from exc

            # Step 2: Validate against Pydantic schema
            output = AnalysisOutput.model_validate_json(current_raw)

            # Steps 3–6: Structural validation of categories
            _validate_categories(output)

            # Steps 7–8: Determine legal review flag
            legal_review = _check_legal_review(output)

            logger.info(
                "✅ Validation passed (attempt %d). legal_review_recommended=%s",
                attempt + 1,
                legal_review,
            )
            return output, legal_review

        except (ValueError, ValidationError) as exc:
            last_error = exc
            logger.warning(
                "Validation attempt %d/%d failed: %s",
                attempt + 1,
                MAX_RETRIES + 1,
                exc,
            )

            if attempt < MAX_RETRIES and retry_fn is not None:
                logger.info("Retrying LLM call for fresh output…")
                try:
                    current_raw = await retry_fn()
                except Exception as retry_exc:
                    logger.error("Retry LLM call failed: %s", retry_exc)
                    break
            else:
                break

    raise ValueError(
        f"Validation failed after {MAX_RETRIES + 1} attempts. Last error: {last_error}"
    )
