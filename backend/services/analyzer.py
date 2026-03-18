"""
AI analyzer service — routes privacy policy analysis to Groq or Ollama fallback.

Routing logic:
  1. Check groq_tracker.is_limit_approaching() — if True, use Ollama
  2. Try Groq (llama-3.3-70b-versatile) with json_object response format
  3. On RateLimitError → call groq_tracker.mark_limit_hit(), fall back to Ollama
  4. On any other Groq error → fall back to Ollama

System prompt is loaded from backend/prompts/systemInstruction.md at runtime.
"""

import logging
import os
from functools import lru_cache
from pathlib import Path

import httpx
from groq import AsyncGroq, RateLimitError

from schemas.analysis import AnalysisOutput
from services import groq_tracker

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
GROQ_MODEL = "llama-3.3-70b-versatile"
OLLAMA_MODEL = "qwen2.5:7b"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Max tokens per spec: 2048; truncate input to stay within 6k token/min limit
GROQ_MAX_INPUT_CHARS = 30_000
OLLAMA_MAX_INPUT_CHARS = 20_000


# ─────────────────────────────────────────────────────────────────────────────
# System prompt (loaded from file, cached after first read)
# ─────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    """
    Load the AI system prompt from backend/prompts/systemInstruction.md.

    Cached after the first call to avoid repeated disk reads.
    The prompt lives in the file so it can be edited without touching Python code.
    """
    prompt_path = Path(__file__).parent.parent / "prompts" / "systemInstruction.md"
    try:
        content = prompt_path.read_text(encoding="utf-8")
        logger.info("Loaded system prompt from %s (%d chars)", prompt_path, len(content))
        return content
    except FileNotFoundError:
        logger.error(
            "System prompt file not found at %s — falling back to minimal prompt.", prompt_path
        )
        # Minimal fallback so the app doesn't crash in dev without the file
        return (
            "You are a privacy policy analyst. Analyze the given policy and return "
            "a structured JSON assessment with scores for: data_selling, ai_training, "
            "third_party_sharing, data_retention, deceptive_ux. "
            "Each must have: score (1-10), confidence (0-100), found (bool), "
            "plain_summary, score_reason, risk_examples (list), snippet. "
            "Also include overall_risk_score, overall_confidence, summary, "
            "gpc_supported, do_not_sell_url, deletion_request_url, "
            "privacy_contact_email, opt_out_notes."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

async def analyze_policy(markdown_text: str) -> AnalysisOutput:
    """
    Analyze a privacy policy markdown document and return a structured AnalysisOutput.

    Routes to Groq first (free tier, fast). Falls back to Ollama (local CUDA)
    when the daily Groq quota is at or above 80%, or when a RateLimitError occurs.

    Args:
        markdown_text: Markdown-formatted privacy policy content.

    Returns:
        AnalysisOutput — fully parsed Pydantic model.
    """
    if await groq_tracker.is_limit_approaching():
        logger.warning("Groq limit approaching — routing to Ollama.")
        return await _analyze_with_ollama(markdown_text)

    try:
        return await _analyze_with_groq(markdown_text)
    except RateLimitError:
        logger.warning("Groq RateLimitError — marking limit hit and falling back to Ollama.")
        await groq_tracker.mark_limit_hit()
        return await _analyze_with_ollama(markdown_text)
    except Exception as exc:
        logger.error("Groq analysis failed (%s) — falling back to Ollama.", exc)
        return await _analyze_with_ollama(markdown_text)


# ─────────────────────────────────────────────────────────────────────────────
# Groq
# ─────────────────────────────────────────────────────────────────────────────

async def _analyze_with_groq(markdown_text: str) -> AnalysisOutput:
    """
    Use Groq API (llama-3.3-70b-versatile) to analyze the policy.

    Enforces json_object response format and increments the daily usage counter.

    Raises:
        RateLimitError: Caller should catch and fall back to Ollama.
        Exception: All other errors propagate to caller for fallback.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key in ("REPLACE_ME", "your_groq_api_key_here"):
        raise ValueError("GROQ_API_KEY is not configured.")

    system_prompt = load_system_prompt()
    truncated = markdown_text[:GROQ_MAX_INPUT_CHARS]

    client = AsyncGroq(api_key=api_key)
    response = await client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Analyze this privacy policy:\n\n{truncated}"},
        ],
        response_format={"type": "json_object"},
        max_tokens=2048,
        temperature=0.1,
    )

    await groq_tracker.increment_usage()

    raw_json = response.choices[0].message.content
    logger.info("Groq analysis complete. Output length: %d chars.", len(raw_json or ""))
    return AnalysisOutput.model_validate_json(raw_json)


# ─────────────────────────────────────────────────────────────────────────────
# Ollama (local fallback)
# ─────────────────────────────────────────────────────────────────────────────

async def _analyze_with_ollama(markdown_text: str) -> AnalysisOutput:
    """
    Use Ollama local API (qwen2.5:7b) to analyze the policy.

    Uses the /api/chat endpoint with format: "json" per spec.

    Raises:
        Exception: If Ollama is unreachable or returns invalid output.
    """
    system_prompt = load_system_prompt()
    truncated = markdown_text[:OLLAMA_MAX_INPUT_CHARS]

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Analyze this privacy policy:\n\n{truncated}"},
                ],
                "stream": False,
                "format": "json",
            },
        )
        resp.raise_for_status()

    result = resp.json()
    raw_json = result.get("message", {}).get("content")
    if not raw_json:
        raise ValueError(f"Ollama returned empty or malformed message: {result}")
    
    logger.info("Ollama analysis complete. Output length: %d chars.", len(raw_json))
    return AnalysisOutput.model_validate_json(raw_json)
