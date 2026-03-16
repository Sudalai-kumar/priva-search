"""
pytest tests for core backend services.

Covers:
  - Validator: all 8 rules + retry logic
  - Groq tracker: Redis key patterns + limit detection
  - Brand discovery: slugify helper + suspicious input detection
  - Rate limiter: is_suspicious_brand_name
  - Analyzer: routing logic (mocked)
"""

import json
import pytest
import pytest_asyncio

# ─────────────────────────────────────────────────────────────────────────────
# Validator tests
# ─────────────────────────────────────────────────────────────────────────────

VALID_CATEGORY = {
    "score": 5,
    "confidence": 70,
    "found": True,
    "plain_summary": "They share data with some partners.",
    "score_reason": "The policy mentions data sharing with advertising partners.",
    "risk_examples": ["Example 1", "Example 2"],
    "snippet": "We share your data with...",
}

VALID_ANALYSIS_JSON = json.dumps({
    "data_selling": VALID_CATEGORY,
    "ai_training": {**VALID_CATEGORY, "score": 3, "confidence": 90},
    "third_party_sharing": {**VALID_CATEGORY, "score": 6},
    "data_retention": {**VALID_CATEGORY, "score": 2, "confidence": 80},
    "deceptive_ux": {**VALID_CATEGORY, "score": 1, "confidence": 95},
    "overall_risk_score": 4,
    "overall_confidence": 82,
    "summary": "This policy is moderately privacy-friendly.",
    "gpc_supported": False,
    "do_not_sell_url": "https://example.com/optout",
    "deletion_request_url": None,
    "privacy_contact_email": "privacy@example.com",
    "opt_out_notes": "CCPA opt-out available.",
})


class TestValidator:
    @pytest.mark.asyncio
    async def test_valid_analysis_passes(self):
        from services.validator import validate_analysis
        output, legal_review = await validate_analysis(VALID_ANALYSIS_JSON)
        assert output.data_selling.score == 5
        assert legal_review is False

    @pytest.mark.asyncio
    async def test_invalid_json_raises(self):
        from services.validator import validate_analysis
        with pytest.raises(ValueError, match="Validation failed"):
            await validate_analysis("{not valid json}")

    @pytest.mark.asyncio
    async def test_score_out_of_range_raises(self):
        from services.validator import validate_analysis
        bad = json.loads(VALID_ANALYSIS_JSON)
        bad["data_selling"]["score"] = 11  # Invalid
        with pytest.raises(ValueError):
            await validate_analysis(json.dumps(bad))

    @pytest.mark.asyncio
    async def test_confidence_out_of_range_raises(self):
        from services.validator import validate_analysis
        bad = json.loads(VALID_ANALYSIS_JSON)
        bad["ai_training"]["confidence"] = 101  # Invalid
        with pytest.raises(ValueError):
            await validate_analysis(json.dumps(bad))

    @pytest.mark.asyncio
    async def test_missing_score_reason_raises(self):
        from services.validator import validate_analysis
        bad = json.loads(VALID_ANALYSIS_JSON)
        bad["deceptive_ux"]["score_reason"] = ""  # Missing
        with pytest.raises(ValueError):
            await validate_analysis(json.dumps(bad))

    @pytest.mark.asyncio
    async def test_legal_review_triggered_by_high_score(self):
        from services.validator import validate_analysis
        high_risk = json.loads(VALID_ANALYSIS_JSON)
        high_risk["data_selling"]["score"] = 8  # ≥8 triggers review
        output, legal_review = await validate_analysis(json.dumps(high_risk))
        assert legal_review is True

    @pytest.mark.asyncio
    async def test_legal_review_triggered_by_low_confidence(self):
        from services.validator import validate_analysis
        low_conf = json.loads(VALID_ANALYSIS_JSON)
        low_conf["third_party_sharing"]["confidence"] = 40  # ≤40 triggers review
        output, legal_review = await validate_analysis(json.dumps(low_conf))
        assert legal_review is True

    @pytest.mark.asyncio
    async def test_retry_fn_called_on_invalid_json(self):
        from services.validator import validate_analysis
        call_count = 0

        async def retry_fn():
            nonlocal call_count
            call_count += 1
            return VALID_ANALYSIS_JSON  # Return valid on retry

        output, legal_review = await validate_analysis("{bad json}", retry_fn=retry_fn)
        assert call_count == 1  # Should retry once
        assert output.overall_risk_score == 4


# ─────────────────────────────────────────────────────────────────────────────
# Brand discovery: slugify helper
# ─────────────────────────────────────────────────────────────────────────────

class TestSlugify:
    def test_basic(self):
        from services.brand_discovery import slugify
        assert slugify("Spotify") == "spotify"

    def test_spaces_become_hyphens(self):
        from services.brand_discovery import slugify
        assert slugify("Google Play") == "google-play"

    def test_special_chars_removed(self):
        from services.brand_discovery import slugify
        assert slugify("AT&T!") == "att"

    def test_already_slug(self):
        from services.brand_discovery import slugify
        assert slugify("facebook") == "facebook"

    def test_leading_trailing_hyphens_stripped(self):
        from services.brand_discovery import slugify
        result = slugify("  --  Meta  --  ")
        assert not result.startswith("-")
        assert not result.endswith("-")


# ─────────────────────────────────────────────────────────────────────────────
# Rate limiter: suspicious brand name detection
# ─────────────────────────────────────────────────────────────────────────────

class TestSuspiciousBrandName:
    def test_raw_ipv4_is_suspicious(self):
        from services.rate_limiter import is_suspicious_brand_name
        assert is_suspicious_brand_name("192.168.1.1") is True

    def test_localhost_is_suspicious(self):
        from services.rate_limiter import is_suspicious_brand_name
        assert is_suspicious_brand_name("localhost") is True

    def test_loopback_is_suspicious(self):
        from services.rate_limiter import is_suspicious_brand_name
        assert is_suspicious_brand_name("127.0.0.1") is True

    def test_ipv6_is_suspicious(self):
        from services.rate_limiter import is_suspicious_brand_name
        assert is_suspicious_brand_name("::1") is True

    def test_normal_brand_is_ok(self):
        from services.rate_limiter import is_suspicious_brand_name
        assert is_suspicious_brand_name("Spotify") is False

    def test_brand_with_number_is_ok(self):
        from services.rate_limiter import is_suspicious_brand_name
        assert is_suspicious_brand_name("3M") is False

    def test_single_char_is_suspicious(self):
        from services.rate_limiter import is_suspicious_brand_name
        assert is_suspicious_brand_name("x") is True

    def test_no_letters_is_suspicious(self):
        from services.rate_limiter import is_suspicious_brand_name
        assert is_suspicious_brand_name("12345") is True


# ─────────────────────────────────────────────────────────────────────────────
# Analyzer: routing logic (mocked — no real API calls)
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyzerRouting:
    @pytest.mark.asyncio
    async def test_routes_to_ollama_when_limit_approaching(self, monkeypatch):
        """When Groq quota is high, analyzer should route to Ollama."""
        import services.analyzer as analyzer_module
        from schemas.analysis import AnalysisOutput

        ollama_called = []

        async def mock_is_limit_approaching():
            return True

        async def mock_analyze_with_ollama(text):
            ollama_called.append(True)
            from schemas.analysis import CategoryAnalysis
            cat = CategoryAnalysis(
                score=5, confidence=70, found=True,
                plain_summary="test", score_reason="test reason",
                risk_examples=[], snippet=None,
            )
            return AnalysisOutput(
                data_selling=cat, ai_training=cat, third_party_sharing=cat,
                data_retention=cat, deceptive_ux=cat,
                overall_risk_score=5, overall_confidence=70,
                summary="test summary",
            )

        monkeypatch.setattr("services.groq_tracker.is_limit_approaching", mock_is_limit_approaching)
        monkeypatch.setattr(analyzer_module, "_analyze_with_ollama", mock_analyze_with_ollama)

        await analyzer_module.analyze_policy("some policy text")
        assert len(ollama_called) == 1, "Should have called Ollama when limit is approaching"
