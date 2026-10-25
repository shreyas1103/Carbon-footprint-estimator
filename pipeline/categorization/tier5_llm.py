"""
pipeline/categorization/tier5_llm.py
Tier 5: Gemini LLM fallback for merchant categorization.
Uses google-genai SDK (google.genai) — the current, non-deprecated package.

Disabled by default. Requires ENABLE_LLM_FALLBACK=true and GEMINI_API_KEY.

Only sends sanitized merchant text — never amounts, dates, or account IDs.
All results are tagged needs_review; LLM output is never treated as ground truth.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Optional

from pipeline.categorization.categories import CANONICAL_CATEGORIES, CategoryResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------------------
ENABLED = os.environ.get("ENABLE_LLM_FALLBACK", "false").lower() == "true"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
MAX_RETRIES = 3
MAX_OUTPUT_TOKENS = 256
API_TIMEOUT_SECONDS = 15

CATEGORIES_LIST = "\n".join(sorted(CANONICAL_CATEGORIES))

SYSTEM_PROMPT = (
    "You are a transaction categorization assistant for India.\n"
    "Given a merchant name or transaction description, classify it into exactly one "
    "of the categories listed below.\n\n"
    "Categories:\n"
    f"{CATEGORIES_LIST}\n\n"
    "Rules:\n"
    "- Respond ONLY with valid JSON — no markdown, no explanation outside the JSON.\n"
    '- Format: {"category": "<canonical_category>", "reason": "<short reason>", "confidence": 0.0}\n'
    "- confidence is a float from 0.0 to 1.0.\n"
    '- If unsure or ambiguous, use category "other_unclassified".\n'
    "- Never return a category not in the list above.\n"
)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def classify(merchant_key: str) -> Optional[CategoryResult]:
    """
    Use Gemini to classify a merchant description.
    Returns CategoryResult(status='needs_review') on success.
    Returns None if disabled, no key, or any error.
    """
    if not ENABLED:
        return None
    if not GEMINI_API_KEY:
        logger.info("Tier 5 LLM skipped: GEMINI_API_KEY not set.")
        return None
    if not merchant_key or len(merchant_key) < 2:
        return None

    # Only send the sanitized merchant text — never raw transaction data
    sanitized = merchant_key[:200]

    last_exc: Optional[Exception] = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = _call_gemini(sanitized)
            if result:
                return result
            return None  # Gemini responded but result was invalid/non-canonical
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "Tier 5 Gemini attempt %d/%d failed: %s",
                attempt + 1, MAX_RETRIES + 1, str(exc)[:200],
            )
            if attempt < MAX_RETRIES:
                wait = 2.0 ** attempt  # exponential: 1s, 2s, 4s
                logger.info("Tier 5 retrying in %.1fs...", wait)
                time.sleep(wait)

    if last_exc:
        logger.error("Tier 5 Gemini all retries exhausted: %s", str(last_exc)[:200])
    return None


# ---------------------------------------------------------------------------
# Gemini API call — uses google.genai (new SDK, not deprecated google-generativeai)
# ---------------------------------------------------------------------------

def _call_gemini(merchant_text: str) -> Optional[CategoryResult]:
    """
    Call the Gemini API and parse / validate the response.
    Raises on API / network errors (caller handles retries).
    """
    try:
        from google import genai  # type: ignore[import-not-found]
        from google.genai import types  # type: ignore[import-not-found]
    except ImportError:
        logger.error(
            "Tier 5: google-genai not installed. Run: pip install google-genai"
        )
        return None

    client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=API_TIMEOUT_SECONDS * 1000),
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=f"Merchant: {merchant_text}",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.0,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            response_mime_type="application/json",
        ),
    )

    raw_text: str = ""
    try:
        raw_text = response.text or ""
    except Exception:
        # response.text raises if the generation was blocked or empty
        logger.warning(
            "Tier 5 Gemini: Empty or blocked response for '%s'.", merchant_text[:50]
        )
        return None

    if not raw_text.strip():
        logger.warning("Tier 5 Gemini: Empty text for '%s'.", merchant_text[:50])
        return None

    return _parse_response(raw_text, merchant_text)


# ---------------------------------------------------------------------------
# Response parsing & validation
# ---------------------------------------------------------------------------

def _parse_response(raw_text: str, merchant_text: str) -> Optional[CategoryResult]:
    """Parse and validate the JSON response from Gemini."""
    # Extract JSON object (handles stray whitespace or markdown fences)
    json_match = re.search(r"\{.*?\}", raw_text.strip(), re.DOTALL)
    if not json_match:
        logger.warning("Tier 5: No JSON in Gemini response: %.80r", raw_text)
        return None

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError:
        logger.warning("Tier 5: Invalid JSON from Gemini: %.80r", raw_text)
        return None

    category = str(data.get("category", "")).strip()
    reason = str(data.get("reason", "")).strip()
    raw_confidence = data.get("confidence", 0.3)

    try:
        confidence = float(raw_confidence)
    except (TypeError, ValueError):
        confidence = 0.3

    # Validate against canonical enum
    if category not in CANONICAL_CATEGORIES:
        logger.warning(
            "Tier 5 Gemini returned non-canonical category '%s' for '%s'.",
            category, merchant_text[:50],
        )
        return None

    # LLM results always get needs_review — capped confidence
    return CategoryResult(
        category=category,
        subcategory=None,
        merchant_name=None,
        merchant_key=merchant_text,
        tier=5,
        method="gemini",
        confidence=min(confidence, 0.6),  # cap at 0.6 — LLM output is uncalibrated
        status="needs_review",
        reason=f"gemini:{reason[:120]}",
    )
