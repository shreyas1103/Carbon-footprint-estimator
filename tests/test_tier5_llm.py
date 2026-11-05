
"""
Unit tests for Tier 5 Gemini LLM fallback.

Tests:
- 429 quota handling
- 503 retry handling
- 504 timeout handling
- Successful classification
- Invalid JSON
- Invalid category
- Invalid confidence
- Missing API key
- Disabled Tier 5
- Empty merchant input

All Gemini API calls are mocked.
No real API quota is consumed.
"""

import pytest
from unittest.mock import patch

from pipeline.categorization import tier5_llm


# ---------------------------------------------------------------------
# Configuration fixture
# ---------------------------------------------------------------------

@pytest.fixture(autouse=True)
def enable_tier5(monkeypatch):
    """Enable Tier 5 for tests without requiring a real API key."""

    monkeypatch.setattr(tier5_llm, "ENABLED", True)
    monkeypatch.setattr(tier5_llm, "GEMINI_API_KEY", "test-api-key")


# ---------------------------------------------------------------------
# 429 RESOURCE_EXHAUSTED
# ---------------------------------------------------------------------

def test_429_quota_exceeded_no_retry():

    error = Exception(
        "429 RESOURCE_EXHAUSTED: quota exceeded"
    )

    with patch.object(
        tier5_llm,
        "_call_gemini",
        side_effect=error
    ) as mock_call:

        result = tier5_llm.classify("unknown merchant")

    assert result is None

    # 429 must not be retried.
    assert mock_call.call_count == 1


# ---------------------------------------------------------------------
# 503 UNAVAILABLE
# ---------------------------------------------------------------------

def test_503_retries_twice_then_fails():

    error = Exception(
        "503 UNAVAILABLE: service unavailable"
    )

    with patch.object(
        tier5_llm,
        "_call_gemini",
        side_effect=error
    ) as mock_call:

        with patch.object(
            tier5_llm.time,
            "sleep"
        ) as mock_sleep:

            result = tier5_llm.classify("unknown merchant")

    assert result is None

    # Initial call + 2 retries.
    assert mock_call.call_count == 3

    assert mock_sleep.call_count == 2


# ---------------------------------------------------------------------
# 504 DEADLINE_EXCEEDED
# ---------------------------------------------------------------------

def test_504_retries_once_then_fails():

    error = Exception(
        "504 DEADLINE_EXCEEDED: timeout"
    )

    with patch.object(
        tier5_llm,
        "_call_gemini",
        side_effect=error
    ) as mock_call:

        with patch.object(
            tier5_llm.time,
            "sleep"
        ) as mock_sleep:

            result = tier5_llm.classify("unknown merchant")

    assert result is None

    # Initial call + 1 retry.
    assert mock_call.call_count == 2

    assert mock_sleep.call_count == 1


# ---------------------------------------------------------------------
# Successful classification
# ---------------------------------------------------------------------

def test_successful_gemini_classification():

    category = next(
        iter(tier5_llm.CANONICAL_CATEGORIES)
    )

    mock_result = tier5_llm.CategoryResult(
        category=category,
        subcategory=None,
        merchant_name=None,
        merchant_key="test merchant",
        tier=5,
        method="gemini",
        confidence=0.6,
        status="needs_review",
        reason="gemini:test reason",
    )

    with patch.object(
        tier5_llm,
        "_call_gemini",
        return_value=mock_result
    ) as mock_call:

        result = tier5_llm.classify("test merchant")

    assert result is not None
    assert result.category == category
    assert result.tier == 5
    assert result.method == "gemini"
    assert result.status == "needs_review"

    assert mock_call.call_count == 1


# ---------------------------------------------------------------------
# Invalid JSON
# ---------------------------------------------------------------------

def test_invalid_json_rejected():

    result = tier5_llm._parse_response(
        "This is not valid JSON",
        "test merchant"
    )

    assert result is None


# ---------------------------------------------------------------------
# Invalid category
# ---------------------------------------------------------------------

def test_invalid_category_rejected():

    response = """
    {
        "category": "invalid_category",
        "reason": "test",
        "confidence": 0.9
    }
    """

    result = tier5_llm._parse_response(
        response,
        "test merchant"
    )

    assert result is None


# ---------------------------------------------------------------------
# Invalid confidence
# ---------------------------------------------------------------------

@pytest.mark.parametrize(
    "confidence",
    [
        -0.5,
        1.5,
        "invalid",
        None,
    ]
)
def test_invalid_confidence_rejected(confidence):

    category = next(
        iter(tier5_llm.CANONICAL_CATEGORIES)
    )

    response = f"""
    {{
        "category": "{category}",
        "reason": "test",
        "confidence": {confidence if isinstance(confidence, (int, float)) else '"invalid"'}
    }}
    """

    result = tier5_llm._parse_response(
        response,
        "test merchant"
    )

    assert result is None


# ---------------------------------------------------------------------
# Missing API key
# ---------------------------------------------------------------------

def test_missing_api_key_skips_tier5(monkeypatch):

    monkeypatch.setattr(
        tier5_llm,
        "GEMINI_API_KEY",
        ""
    )

    with patch.object(
        tier5_llm,
        "_call_gemini"
    ) as mock_call:

        result = tier5_llm.classify("test merchant")

    assert result is None
    mock_call.assert_not_called()


# ---------------------------------------------------------------------
# Disabled Tier 5
# ---------------------------------------------------------------------

def test_disabled_tier5_skips_classification(monkeypatch):

    monkeypatch.setattr(
        tier5_llm,
        "ENABLED",
        False
    )

    with patch.object(
        tier5_llm,
        "_call_gemini"
    ) as mock_call:

        result = tier5_llm.classify("test merchant")

    assert result is None
    mock_call.assert_not_called()


# ---------------------------------------------------------------------
# Empty merchant input
# ---------------------------------------------------------------------

@pytest.mark.parametrize(
    "merchant",
    [
        "",
        " ",
        "a",
        None,
    ]
)
def test_invalid_merchant_input(merchant):

    with patch.object(
        tier5_llm,
        "_call_gemini"
    ) as mock_call:

        result = tier5_llm.classify(merchant)

    assert result is None
    mock_call.assert_not_called()


# ---------------------------------------------------------------------
# Confidence cap
# ---------------------------------------------------------------------

def test_confidence_is_capped_at_point_six():

    category = next(
        iter(tier5_llm.CANONICAL_CATEGORIES)
    )

    response = f"""
    {{
        "category": "{category}",
        "reason": "test",
        "confidence": 0.95
    }}
    """

    result = tier5_llm._parse_response(
        response,
        "test merchant"
    )

    assert result is not None
    assert result.confidence == 0.6
    assert result.status == "needs_review"


# ---------------------------------------------------------------------
# Category outside canonical list
# ---------------------------------------------------------------------

def test_other_unclassified_is_accepted_if_canonical():

    if "other_unclassified" not in tier5_llm.CANONICAL_CATEGORIES:
        pytest.skip(
            "other_unclassified is not in canonical categories"
        )

    response = """
    {
        "category": "other_unclassified",
        "reason": "Merchant is unclear",
        "confidence": 0.3
    }
    """

    result = tier5_llm._parse_response(
        response,
        "unknown merchant"
    )

    assert result is not None
    assert result.category == "other_unclassified"
    assert result.status == "needs_review"
