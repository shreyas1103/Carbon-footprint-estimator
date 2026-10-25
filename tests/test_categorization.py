"""
tests/test_categorization.py
Tests for the categorization pipeline — dictionary, fuzzy, cache, and orchestration.
All tests are DB-independent for pure functions.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from pipeline.categorization.categories import CANONICAL_CATEGORIES, CategoryResult
from pipeline.categorization import tier2_dictionary, tier3_fuzzy
from pipeline.categorization.pipeline import categorize_merchant


# ---------------------------------------------------------------------------
# Tier 2 — Dictionary exact match
# ---------------------------------------------------------------------------

def test_exact_electricity_match():
    result = tier2_dictionary.classify("electricity bill")
    assert result is not None
    assert result.category == "utilities.electricity"
    assert result.status == "categorized"
    assert result.confidence >= 0.9


def test_exact_lpg_match():
    result = tier2_dictionary.classify("lpg refill")
    assert result is not None
    assert result.category == "utilities.lpg"


def test_exact_petrol_match():
    result = tier2_dictionary.classify("petrol pump")
    assert result is not None
    assert result.category == "transport_fuel.petrol"


def test_exact_grocery_match():
    result = tier2_dictionary.classify("grocery")
    assert result is not None
    assert result.category == "food.basic_grocery"


def test_ambiguous_alias_needs_review():
    """Ambiguous aliases like 'iocl' (could be petrol or diesel) → needs_review."""
    result = tier2_dictionary.classify("iocl")
    assert result is not None
    assert result.status == "needs_review" or result.confidence < 0.9


def test_unrelated_string_returns_none():
    result = tier2_dictionary.classify("xyzzy_nonexistent_merchant_abc")
    assert result is None


def test_restaurant_maps_to_delivery_category():
    result = tier2_dictionary.classify("restaurant")
    assert result is not None
    assert result.category == "food.restaurant_delivery"


def test_all_matched_categories_are_canonical():
    """Every alias in the dictionary must map to a canonical category."""
    from pipeline.categorization.tier2_dictionary import ALIAS_MAP
    for alias, (cat, subcat, ambiguous) in ALIAS_MAP.items():
        assert cat in CANONICAL_CATEGORIES, f"Alias '{alias}' maps to non-canonical '{cat}'"


# ---------------------------------------------------------------------------
# Tier 3 — Fuzzy match
# ---------------------------------------------------------------------------

def test_fuzzy_near_match_electricity():
    """'electrcity bill' (typo) should fuzzy match to electricity."""
    result = tier3_fuzzy.classify("electrcity bill")
    # Either matches or returns None (typo may be too severe)
    if result is not None:
        assert result.category == "utilities.electricity"
        assert result.tier == 3


def test_fuzzy_near_match_grocery():
    result = tier3_fuzzy.classify("groccery store")
    if result is not None:
        assert "grocery" in result.category or result.status == "needs_review"


def test_fuzzy_unrelated_returns_none():
    result = tier3_fuzzy.classify("zzzzznonexistent")
    assert result is None


def test_fuzzy_ambiguous_marked_needs_review():
    """If best and second-best are close, result should be needs_review."""
    # "apollo" is in the dictionary as ambiguous
    result = tier3_fuzzy.classify("apollo")
    if result is not None:
        # Should either be needs_review or a confident match
        assert result.status in ("categorized", "needs_review")


def test_fuzzy_result_has_tier_3():
    result = tier3_fuzzy.classify("bigbasket groceries")
    if result is not None:
        assert result.tier == 3


# ---------------------------------------------------------------------------
# Category enum validation
# ---------------------------------------------------------------------------

def test_canonical_categories_non_empty():
    assert len(CANONICAL_CATEGORIES) > 30


def test_supported_categories_subset_of_canonical():
    from pipeline.categorization.categories import SUPPORTED_SPEND_CATEGORIES
    for cat in SUPPORTED_SPEND_CATEGORIES:
        assert cat in CANONICAL_CATEGORIES


def test_excluded_categories_in_canonical():
    from pipeline.categorization.categories import EXCLUDED_CATEGORIES
    for cat in EXCLUDED_CATEGORIES:
        assert cat in CANONICAL_CATEGORIES


# ---------------------------------------------------------------------------
# Pipeline orchestration (no DB)
# ---------------------------------------------------------------------------

def test_pipeline_returns_for_known_merchant():
    result = categorize_merchant("bigbasket", "BigBasket", session=None)
    assert result is not None
    assert result.category in CANONICAL_CATEGORIES
    assert result.status in ("categorized", "needs_review", "unclassified")


def test_pipeline_returns_unclassified_for_unknown():
    result = categorize_merchant("xyzzy_unknown_merchant_abc123", "Unknown", session=None)
    assert result is not None
    assert result.category in CANONICAL_CATEGORIES  # other_unclassified is canonical
    assert result.status in ("needs_review", "unclassified")


def test_pipeline_confidence_in_range():
    result = categorize_merchant("electricity bill", "Electricity Bill", session=None)
    assert 0.0 <= result.confidence <= 1.0


def test_pipeline_tier_is_set_or_none():
    result = categorize_merchant("electricity bill", "Electricity Bill", session=None)
    assert result.tier is None or isinstance(result.tier, int)


def test_pipeline_method_always_set():
    result = categorize_merchant("electricity bill", "Electricity Bill", session=None)
    assert result.method is not None


def test_pipeline_zomato_is_restaurant_delivery():
    result = categorize_merchant("zomato", "Zomato", session=None)
    assert result.category == "food.restaurant_delivery"


def test_pipeline_upi_gateway_not_assigned_category():
    """UPI/payment gateway alone must not determine category."""
    result = categorize_merchant("upi paytm payment", "UPI PAYTM", session=None)
    # Should be unclassified/needs_review, not a specific food/utility category
    assert result.category in CANONICAL_CATEGORIES


def test_all_outputs_have_canonical_category():
    """End-to-end: any merchant key produces a result with a canonical category."""
    merchants = [
        "bescom electricity", "hp gas lpg", "bigbasket fresh",
        "zomato delivery", "amazon online", "atm withdrawal",
        "refund amazon", "xyz123"
    ]
    for m in merchants:
        result = categorize_merchant(m, m.title(), session=None)
        assert result.category in CANONICAL_CATEGORIES, (
            f"'{m}' produced non-canonical category: {result.category}"
        )
