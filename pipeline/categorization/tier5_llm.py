
"""
pipeline/categorization/tier5_llm.py

Tier 5: Gemini LLM fallback for merchant categorization.

Uses google-genai SDK (google.genai).

Disabled by default. Requires:
ENABLE_LLM_FALLBACK=true
GEMINI_API_KEY=<your-api-key>

Only sends sanitized merchant text.
Never sends amounts, dates, or account IDs.

All LLM results are tagged needs_review.
LLM output is never treated as ground truth.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time

from typing import Optional

from pipeline.categorization.categories import (
    CANONICAL_CATEGORIES,
    CategoryResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ENABLED = (
    os.environ.get("ENABLE_LLM_FALLBACK", "false").lower() == "true"
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL",
    "gemini-flash-latest"
)

# Retry configuration
MAX_RETRIES_503 = 2
MAX_RETRIES_504 = 1

# API configuration
MAX_OUTPUT_TOKENS = 256
API_TIMEOUT_SECONDS = 15

CATEGORIES_LIST = "\n".join(sorted(CANONICAL_CATEGORIES))


# ---------------------------------------------------------------------------
# Gemini system prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a transaction categorization assistant for India.\n"
    "Given a merchant name or transaction description, classify it into "
    "exactly one of the categories listed below.\n\n"

    "Categories:\n"
    f"{CATEGORIES_LIST}\n\n"

    "Rules:\n"
    "- Respond ONLY with valid JSON.\n"
    "- Do not include markdown or explanations outside JSON.\n"
    '- Format: {"category": "<canonical_category>", '
    '"reason": "<short reason>", "confidence": 0.0}\n'
    "- Confidence must be a float between 0.0 and 1.0.\n"
    '- If unsure or ambiguous, use category "other_unclassified".\n'
    "- Never return a category outside the supplied list.\n"
)


# ---------------------------------------------------------------------------
# HTTP error detection
# ---------------------------------------------------------------------------

def _get_error_status(exc: Exception) -> Optional[int]:
    """
    Extract HTTP status code from Gemini API exceptions.
    """

    # Check common exception attributes.
    for attr in ("code", "status_code"):

        value = getattr(exc, attr, None)

        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            pass

    # Fallback: inspect exception message.
    message = str(exc)

    match = re.search(
        r"\b(429|503|504)\b",
        message
    )

    if match:
        return int(match.group(1))

    return None


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def classify(
    merchant_key: str
) -> Optional[CategoryResult]:
    """
    Use Gemini to classify a merchant description.

    Returns:
        CategoryResult(status='needs_review') on valid response.

        None if:
        - Tier 5 is disabled.
        - API key is missing.
        - Input is invalid.
        - Gemini request fails.
        - Response is invalid.
    """

    if not ENABLED:
        return None

    if not GEMINI_API_KEY:

        logger.info(
            "Tier 5 skipped: GEMINI_API_KEY not set."
        )

        return None

    if not merchant_key or len(merchant_key.strip()) < 2:
        return None

    # Only sanitized merchant text is sent.
    sanitized = merchant_key.strip()[:200]

    # Retry limits by HTTP status.
    retry_limits = {
        503: MAX_RETRIES_503,
        504: MAX_RETRIES_504,
    }

    attempt = 0

    while True:

        try:

            result = _call_gemini(sanitized)

            return result

        except Exception as exc:

            status = _get_error_status(exc)

            logger.warning(
                "Tier 5 Gemini failed. HTTP status=%s, error=%s",
                status,
                str(exc)[:200],
            )

            # ---------------------------------------------------------------
            # 429: Quota exhausted or rate limit.
            # Do not retry immediately.
            # ---------------------------------------------------------------

            if status == 429:

                logger.error(
                    "Gemini returned 429. "
                    "Skipping Tier 5 without retrying."
                )

                return None

            # ---------------------------------------------------------------
            # Retry only configured temporary errors.
            # ---------------------------------------------------------------

            max_retries = retry_limits.get(status, 0)

            if attempt >= max_retries:

                logger.error(
                    "Tier 5 failed. Total retries attempted: %d",
                    attempt,
                )

                return None

            wait_seconds = 2 ** attempt

            logger.info(
                "Retrying Gemini in %d seconds. Retry %d/%d",
                wait_seconds,
                attempt + 1,
                max_retries,
            )

            time.sleep(wait_seconds)

            attempt += 1


# ---------------------------------------------------------------------------
# Gemini API call
# ---------------------------------------------------------------------------

def _call_gemini(
    merchant_text: str
) -> Optional[CategoryResult]:
    """
    Call Gemini API and parse/validate its response.

    Raises API/network errors to classify(), which handles retries.
    """

    try:

        from google import genai
        from google.genai import types

    except ImportError:

        logger.error(
            "Tier 5: google-genai is not installed. "
            "Run: pip install google-genai"
        )

        return None

    client = genai.Client(
        api_key=GEMINI_API_KEY,

        http_options=types.HttpOptions(
            timeout=API_TIMEOUT_SECONDS * 1000
        ),
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

    # Extract response text safely.
    try:

        raw_text = response.text or ""

    except Exception:

        logger.warning(
            "Tier 5 Gemini returned an empty or blocked response."
        )

        return None

    if not raw_text.strip():

        logger.warning(
            "Tier 5 Gemini returned empty text."
        )

        return None

    return _parse_response(
        raw_text,
        merchant_text
    )


# ---------------------------------------------------------------------------
# Response parsing and validation
# ---------------------------------------------------------------------------

def _parse_response(
    raw_text: str,
    merchant_text: str
) -> Optional[CategoryResult]:
    """
    Parse and validate Gemini JSON response.

    Only canonical categories are accepted.
    Every accepted result remains needs_review.
    """

    # Extract JSON object.
    json_match = re.search(
        r"\{.*?\}",
        raw_text.strip(),
        re.DOTALL
    )

    if not json_match:

        logger.warning(
            "Tier 5: No JSON found in Gemini response."
        )

        return None

    try:

        data = json.loads(
            json_match.group()
        )

    except json.JSONDecodeError:

        logger.warning(
            "Tier 5: Invalid JSON returned by Gemini."
        )

        return None

    # Ensure the response is a JSON object.
    if not isinstance(data, dict):

        logger.warning(
            "Tier 5: Gemini response is not a JSON object."
        )

        return None

    category = str(
        data.get("category", "")
    ).strip()

    reason = str(
        data.get("reason", "")
    ).strip()

    raw_confidence = data.get("confidence")

    # Validate category.
    if category not in CANONICAL_CATEGORIES:

        logger.warning(
            "Tier 5 returned non-canonical category: %s",
            category,
        )

        return None

    # Validate confidence.
    try:

        confidence = float(raw_confidence)

    except (TypeError, ValueError):

        logger.warning(
            "Tier 5 returned invalid confidence."
        )

        return None

    # Reject invalid confidence ranges.
    if not 0.0 <= confidence <= 1.0:

        logger.warning(
            "Tier 5 returned confidence outside valid range."
        )

        return None

    # Never treat LLM output as ground truth.
    return CategoryResult(

        category=category,

        subcategory=None,

        merchant_name=None,

        merchant_key=merchant_text,

        tier=5,

        method="gemini",

        confidence=min(confidence, 0.6),

        status="needs_review",

        reason=f"gemini:{reason[:120]}",

    )