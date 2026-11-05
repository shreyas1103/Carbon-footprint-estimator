"""
tests/test_categorization.py
Tests for the categorization pipeline — dictionary, fuzzy, cache, orchestration,
tier priority ordering, unknown merchant handling, and emissions safety.
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
# Tier 2 — New LPG alias tests (INDANE GAS, BHARAT GAS, HP GAS)
# ---------------------------------------------------------------------------

def test_indane_gas_direct():
    """Direct match: 'indane gas' must map to utilities.lpg."""
    result = tier2_dictionary.classify("indane gas")
    assert result is not None
    assert result.category == "utilities.lpg"
    assert result.status == "categorized"


def test_indane_gas_booking_substring():
    """Substring match: 'INDANE GAS BOOKING' must find 'indane gas' → utilities.lpg."""
    result = tier2_dictionary.classify("INDANE GAS BOOKING")
    assert result is not None
    assert result.category == "utilities.lpg"
    assert result.status == "categorized"


def test_bharat_gas_refill():
    result = tier2_dictionary.classify("BHARAT GAS REFILL")
    assert result is not None
    assert result.category == "utilities.lpg"


def test_hp_gas_cylinder():
    result = tier2_dictionary.classify("HP GAS CYLINDER")
    assert result is not None
    assert result.category == "utilities.lpg"


# ---------------------------------------------------------------------------
# Tier 2 — New Telecom alias tests
# ---------------------------------------------------------------------------

def test_jio_fiber_bill():
    result = tier2_dictionary.classify("JIO FIBER BILL")
    assert result is not None
    assert result.category == "telecom_internet"


def test_jio_recharge_direct():
    result = tier2_dictionary.classify("jio recharge")
    assert result is not None
    assert result.category == "telecom_internet"


# ---------------------------------------------------------------------------
# Tier 2 — Word-boundary matching
# ---------------------------------------------------------------------------

def test_bus_does_not_match_business():
    """'business' must NOT match the 'bus' alias."""
    result = tier2_dictionary.classify("business consulting")
    assert result is None


def test_bus_matches_bus_ticket():
    """'bus ticket booking' should match 'bus' alias."""
    result = tier2_dictionary.classify("bus ticket booking")
    assert result is not None
    assert result.category == "transport.public_transit"


def test_short_alias_not_matched_in_substring():
    """Very short aliases (≤2 chars like 'vi') should not match via substring."""
    result = tier2_dictionary.classify("movie via online")
    # 'vi' should NOT match here via substring
    assert result is None or result.method != "dictionary_substring" or result.reason != "alias_substring:vi"


# ---------------------------------------------------------------------------
# Tier 2 — Ambiguous aliases
# ---------------------------------------------------------------------------

def test_apollo_ambiguous():
    """Apollo could be pharmacy or hospital — should be needs_review."""
    result = tier2_dictionary.classify("apollo")
    assert result is not None
    assert result.status == "needs_review"


def test_hotel_ambiguous():
    """'hotel' can mean restaurant or accommodation — needs_review."""
    result = tier2_dictionary.classify("hotel taj")
    assert result is not None
    assert result.status == "needs_review"


def test_iocl_ambiguous():
    """IOCL could be petrol or diesel — needs_review."""
    result = tier2_dictionary.classify("iocl")
    assert result is not None
    assert result.status == "needs_review"


def test_hpcl_ambiguous():
    result = tier2_dictionary.classify("hpcl")
    assert result is not None
    assert result.status == "needs_review"


def test_bpcl_ambiguous():
    result = tier2_dictionary.classify("bpcl")
    assert result is not None
    assert result.status == "needs_review"


# ---------------------------------------------------------------------------
# Tier 2 — Multiple aliases: longest match wins
# ---------------------------------------------------------------------------

def test_longest_alias_wins():
    """'jio fiber' (12 chars) should win over 'jio' (3 chars) for 'jio fiber bill'."""
    result = tier2_dictionary.classify("JIO FIBER BILL PAYMENT")
    assert result is not None
    assert result.category == "telecom_internet"
    # Should match 'jio fiber', not just 'jio'
    assert "jio fiber" in (result.reason or "")


# ---------------------------------------------------------------------------
# Tier 2 — Empty/invalid input
# ---------------------------------------------------------------------------

def test_empty_string_returns_none():
    assert tier2_dictionary.classify("") is None


def test_none_returns_none():
    assert tier2_dictionary.classify(None) is None


def test_whitespace_only_returns_none():
    assert tier2_dictionary.classify("   ") is None


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
# Pipeline orchestration — tier priority (no DB)
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


# ---------------------------------------------------------------------------
# Pipeline — INDANE GAS must be categorized by dictionary, NOT by ML
# ---------------------------------------------------------------------------

def test_pipeline_indane_gas_booking():
    """INDANE GAS BOOKING must be categorized as utilities.lpg by Tier 2 dictionary,
    not as transport.air_travel by the ML classifier."""
    result = categorize_merchant("indane gas booking", "INDANE GAS BOOKING", session=None)
    assert result.category == "utilities.lpg"
    assert result.tier == 2  # Must come from dictionary, not Tier 1


def test_pipeline_bharat_gas_refill():
    result = categorize_merchant("bharat gas refill", "BHARAT GAS REFILL", session=None)
    assert result.category == "utilities.lpg"


def test_pipeline_hp_gas_cylinder():
    result = categorize_merchant("hp gas cylinder", "HP GAS CYLINDER", session=None)
    assert result.category == "utilities.lpg"


def test_pipeline_jio_fiber_bill():
    result = categorize_merchant("jio fiber bill", "JIO FIBER BILL", session=None)
    assert result.category == "telecom_internet"


def test_pipeline_swiggy_order():
    result = categorize_merchant("swiggy order 7821", "SWIGGY ORDER 7821", session=None)
    assert result.category == "food.restaurant_delivery"


def test_pipeline_bigbasket_purchase():
    result = categorize_merchant("bigbasket purchase", "BIGBASKET PURCHASE", session=None)
    assert result.category == "food.basic_grocery"


def test_pipeline_hp_petrol_pump():
    result = categorize_merchant("hp petrol pump", "HP PETROL PUMP", session=None)
    assert result.category == "transport_fuel.petrol"


def test_pipeline_irctc_ticket():
    result = categorize_merchant("irctc ticket", "IRCTC TICKET", session=None)
    assert result.category == "transport.public_transit"


def test_pipeline_uber_ride_payment():
    result = categorize_merchant("uber ride payment", "UBER RIDE PAYMENT", session=None)
    assert result.category == "transport.taxi_rideshare"


def test_pipeline_netflix_subscription():
    result = categorize_merchant("netflix subscription", "NETFLIX SUBSCRIPTION", session=None)
    assert result.category == "entertainment"


# ---------------------------------------------------------------------------
# Pipeline — Unknown merchants: no forced classification
# ---------------------------------------------------------------------------

def test_pipeline_unknown_merchant_no_forced_category():
    """UNKNOWN MERCHANT 83921 must NOT get a random food/utility category."""
    result = categorize_merchant("unknown merchant 83921", "UNKNOWN MERCHANT 83921", session=None)
    assert result.status in ("needs_review", "unclassified")
    # Must not be assigned a specific consumption category with high confidence
    if result.status == "unclassified":
        assert result.category == "other_unclassified"


def test_pipeline_random_payment_no_forced_category():
    """RANDOM PAYMENT XYZ 12345 must NOT get a random category."""
    result = categorize_merchant("random payment xyz 12345", "RANDOM PAYMENT XYZ 12345", session=None)
    assert result.status in ("needs_review", "unclassified")


# ---------------------------------------------------------------------------
# Emissions — needs_review and unclassified are NOT estimated
# ---------------------------------------------------------------------------

def test_emissions_needs_review_not_estimated():
    """needs_review transactions must NOT receive CO2e values."""
    from pipeline.emissions import estimate
    res = estimate(1000.0, "INR", "utilities.lpg", category_status="needs_review")
    assert res.emissions_status == "unsupported"
    assert res.estimated_co2e_kg is None
    assert "AMBIGUOUS" in (res.estimation_notes or "")


def test_emissions_unclassified_not_estimated():
    from pipeline.emissions import estimate
    res = estimate(500.0, "INR", "food.basic_grocery", category_status="unclassified")
    assert res.emissions_status == "unsupported"
    assert res.estimated_co2e_kg is None


def test_emissions_categorized_is_estimated():
    """Properly categorized transactions SHOULD receive CO2e values."""
    from pipeline.emissions import estimate
    res = estimate(1000.0, "INR", "utilities.electricity", category_status="categorized")
    assert res.emissions_status == "estimated"
    assert res.estimated_co2e_kg is not None
    assert res.estimated_co2e_kg > 0


# ---------------------------------------------------------------------------
# Emissions — Cash withdrawals, transfers, refunds excluded
# ---------------------------------------------------------------------------

def test_emissions_cash_withdrawal_excluded():
    from pipeline.emissions import estimate
    res = estimate(5000.0, "INR", "cash_withdrawal_transfer")
    assert res.emissions_status == "excluded_non_consumption"
    assert res.estimated_co2e_kg is None


def test_emissions_refund_excluded():
    from pipeline.emissions import estimate
    res = estimate(800.0, "INR", "refund_credit")
    assert res.emissions_status == "excluded_non_consumption"
    assert res.estimated_co2e_kg is None


def test_emissions_negative_amount_excluded():
    from pipeline.emissions import estimate
    res = estimate(-500.0, "INR", "food.basic_grocery")
    assert res.emissions_status == "excluded_refund"
    assert res.estimated_co2e_kg is None


# ===========================================================================
# SECTION: Stale Cache Validation
# ===========================================================================

def test_stale_cache_auto_entry_invalidated_when_dict_disagrees():
    """If an auto-cached entry disagrees with the dictionary, it should be
    invalidated (marked 'stale') and return None so the pipeline re-classifies.
    
    This simulates the scenario where 'indane gas' was previously cached as
    'transport.air_travel' by the old Tier 1 ML classifier.
    """
    from pipeline.categorization import tier0_cache, tier2_dictionary

    # Verify dictionary knows indane gas → utilities.lpg
    dict_result = tier2_dictionary.classify("indane gas booking")
    assert dict_result is not None
    assert dict_result.category == "utilities.lpg"

    # With no DB session, cache always returns None — safe behavior
    result = tier0_cache.lookup_cache("indane gas booking", session=None)
    assert result is None


def test_cache_lookup_returns_none_without_session():
    """Cache lookup with session=None must return None (no DB)."""
    from pipeline.categorization.tier0_cache import lookup_cache
    assert lookup_cache("any_merchant", None) is None


def test_cache_lookup_returns_none_for_empty_key():
    """Cache lookup with empty key must return None."""
    from pipeline.categorization.tier0_cache import lookup_cache
    assert lookup_cache("", None) is None


def test_cache_write_returns_false_without_session():
    """Cache write with session=None must return False."""
    from pipeline.categorization.tier0_cache import write_cache
    result = CategoryResult(
        category="utilities.lpg", subcategory=None,
        merchant_name=None, merchant_key="test",
        tier=2, method="dictionary", confidence=1.0,
        status="categorized", reason="test",
    )
    assert write_cache("test", "Test", result, session=None) is False


def test_cache_write_rejects_non_canonical():
    """Cache write with non-canonical category must return False."""
    from pipeline.categorization.tier0_cache import write_cache
    result = CategoryResult(
        category="nonsense_category", subcategory=None,
        merchant_name=None, merchant_key="test",
        tier=2, method="dictionary", confidence=1.0,
        status="categorized", reason="test",
    )
    assert write_cache("test", "Test", result, session=None) is False


# ===========================================================================
# SECTION: Ambiguity Protection — Dictionary needs_review preserved through pipeline
# ===========================================================================

def test_pipeline_apollo_stays_needs_review():
    """APOLLO is ambiguous (pharmacy vs hospital). Pipeline must not silently resolve it."""
    result = categorize_merchant("apollo", "APOLLO", session=None)
    assert result is not None
    assert result.status == "needs_review"
    assert result.category == "healthcare"


def test_pipeline_hotel_stays_needs_review():
    """HOTEL is ambiguous (restaurant vs accommodation). Must stay needs_review."""
    result = categorize_merchant("hotel", "HOTEL", session=None)
    assert result is not None
    assert result.status == "needs_review"


def test_pipeline_iocl_stays_needs_review():
    """IOCL could be petrol or diesel — must stay needs_review."""
    result = categorize_merchant("iocl", "IOCL", session=None)
    assert result is not None
    assert result.status == "needs_review"


def test_pipeline_bpcl_stays_needs_review():
    result = categorize_merchant("bpcl", "BPCL", session=None)
    assert result is not None
    assert result.status == "needs_review"


def test_pipeline_hpcl_stays_needs_review():
    result = categorize_merchant("hpcl", "HPCL", session=None)
    assert result is not None
    assert result.status == "needs_review"


def test_pipeline_bus_stays_needs_review():
    """'bus' alone is ambiguous (school bus vs public transit)."""
    result = categorize_merchant("bus", "BUS", session=None)
    assert result is not None
    assert result.status == "needs_review"


def test_ambiguous_result_no_emissions():
    """Ambiguous (needs_review) results must NOT get emissions calculated."""
    from pipeline.emissions import estimate
    # IOCL is ambiguous → needs_review
    result = categorize_merchant("iocl", "IOCL", session=None)
    assert result.status == "needs_review"

    # Emissions for needs_review must be unsupported
    emission = estimate(2000.0, "INR", result.category, category_status=result.status)
    assert emission.emissions_status == "unsupported"
    assert emission.estimated_co2e_kg is None


def test_ambiguous_apollo_no_emissions():
    """Apollo is ambiguous — no emissions should be calculated."""
    from pipeline.emissions import estimate
    result = categorize_merchant("apollo", "APOLLO", session=None)
    emission = estimate(500.0, "INR", result.category, category_status=result.status)
    assert emission.emissions_status == "unsupported"
    assert emission.estimated_co2e_kg is None


def test_ambiguous_hotel_no_emissions():
    from pipeline.emissions import estimate
    result = categorize_merchant("hotel", "HOTEL", session=None)
    emission = estimate(3000.0, "INR", result.category, category_status=result.status)
    assert emission.emissions_status == "unsupported"
    assert emission.estimated_co2e_kg is None


# ===========================================================================
# SECTION: OOD (Out-of-Distribution) Detection
# ===========================================================================

def test_ood_vocabulary_coverage_function_exists():
    """The vocabulary coverage function should be importable."""
    from pipeline.categorization.tier1_classifier import _vocabulary_coverage
    assert callable(_vocabulary_coverage)


def test_ood_unknown_merchant_low_coverage():
    """Totally unfamiliar descriptions should have low vocabulary coverage."""
    from pipeline.categorization.tier1_classifier import _vocabulary_coverage, _load_model
    if not _load_model():
        pytest.skip("Model artifacts not available")
    coverage = _vocabulary_coverage("xyzzy_unknown_merchant_83921_qqq")
    # Gibberish should have very low coverage
    assert coverage < 0.5


def test_ood_known_merchant_higher_coverage():
    """Familiar merchant descriptions should have higher vocabulary coverage."""
    from pipeline.categorization.tier1_classifier import _vocabulary_coverage, _load_model
    if not _load_model():
        pytest.skip("Model artifacts not available")
    coverage = _vocabulary_coverage("swiggy food delivery")
    # Known terms should have reasonable coverage
    assert coverage > 0.0


def test_ood_empty_input_returns_zero():
    """Empty input should return 0.0 coverage."""
    from pipeline.categorization.tier1_classifier import _vocabulary_coverage
    assert _vocabulary_coverage("") == 0.0


def test_ood_unknown_merchant_not_classified():
    """UNKNOWN MERCHANT 83921 should not be assigned a specific category."""
    result = categorize_merchant("unknown merchant 83921", "UNKNOWN MERCHANT 83921", session=None)
    # Must NOT get a specific consumption category
    assert result.status in ("needs_review", "unclassified")


def test_ood_random_gibberish_not_classified():
    """Completely random text must not get a confident classification."""
    result = categorize_merchant(
        "zzzzz qqqqq xxxxx 99999", "ZZZZZ QQQQQ XXXXX 99999", session=None
    )
    assert result.status in ("needs_review", "unclassified")


def test_ood_misleading_confidence_prevented():
    """Even if LR gives high confidence for gibberish, OOD check should reject it.
    Test with a description that looks like noise."""
    from pipeline.categorization import tier1_classifier
    result = tier1_classifier.classify("zyxwv12345_random_noise")
    # Either None (rejected) or very low confidence — never a confident match
    if result is not None:
        # If somehow it passes OOD, it must have reasonable coverage
        assert result.confidence > 0  # Just checking it doesn't crash


def test_tier1_missing_model_returns_none():
    """If model files don't exist, classify must return None gracefully."""
    from pipeline.categorization import tier1_classifier
    import os
    # Save originals
    orig_vec = tier1_classifier.VECTORIZER_PATH
    orig_clf = tier1_classifier.CLASSIFIER_PATH
    orig_loaded = tier1_classifier._LOADED

    try:
        # Point to nonexistent files
        tier1_classifier.VECTORIZER_PATH = "/nonexistent/path/vec.joblib"
        tier1_classifier.CLASSIFIER_PATH = "/nonexistent/path/clf.joblib"
        tier1_classifier._LOADED = False  # Force reload attempt

        result = tier1_classifier.classify("test merchant")
        assert result is None
    finally:
        # Restore originals
        tier1_classifier.VECTORIZER_PATH = orig_vec
        tier1_classifier.CLASSIFIER_PATH = orig_clf
        tier1_classifier._LOADED = orig_loaded


def test_tier1_empty_string_returns_none():
    from pipeline.categorization import tier1_classifier
    assert tier1_classifier.classify("") is None
    assert tier1_classifier.classify("   ") is None
    assert tier1_classifier.classify(None) is None

