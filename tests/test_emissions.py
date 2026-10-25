"""
tests/test_emissions.py
Tests for pipeline/emissions.py — Route A, Route B, exclusions, coverage metrics.
No double-counting tests included.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
import pytest

from pipeline.emissions import (
    estimate,
    compute_coverage_metrics,
    _FALLBACK_REGISTRY,
    EmissionsResult,
)
import pandas as pd


# ---------------------------------------------------------------------------
# Route A — spend-based factor
# ---------------------------------------------------------------------------

def test_route_a_electricity():
    res = estimate(1000.0, "INR", "utilities.electricity")
    assert res.emissions_status == "estimated"
    assert res.factor_method == "spend_based"
    assert res.factor_id == "IN-CEA-ELECTRICITY-SPEND"
    assert res.estimated_co2e_kg is not None
    assert res.estimated_co2e_kg > 0
    # Verify formula: 1000 * 0.1325303878714435 ≈ 132.53
    assert abs(res.estimated_co2e_kg - 132.53) < 1.0


def test_route_a_lpg():
    res = estimate(980.0, "INR", "utilities.lpg")
    assert res.emissions_status == "estimated"
    assert res.factor_id == "IN-MOEFCC-LPG-SPEND"
    assert res.estimated_co2e_kg is not None and res.estimated_co2e_kg > 0


def test_route_a_petrol():
    res = estimate(2500.0, "INR", "transport_fuel.petrol")
    assert res.emissions_status == "estimated"
    assert res.factor_id == "IN-BEE-PETROL-SPEND"
    assert res.estimated_co2e_kg > 0


def test_route_a_diesel():
    res = estimate(2000.0, "INR", "transport_fuel.diesel")
    assert res.emissions_status == "estimated"
    assert res.factor_id == "IN-BEE-DIESEL-SPEND"
    assert res.estimated_co2e_kg > 0


def test_route_a_grocery():
    res = estimate(850.0, "INR", "food.basic_grocery")
    assert res.emissions_status == "estimated"
    assert res.factor_id == "IN-HCES-BASIC-GROCERY"
    assert res.estimated_co2e_kg > 0


def test_route_a_dairy():
    res = estimate(320.0, "INR", "food.milk_dairy")
    assert res.emissions_status == "estimated"
    assert res.factor_id == "IN-HCES-MILK-AND-DAIRY"


def test_route_a_full_precision_preserved():
    """Values are stored at full precision — no rounding at calculation time."""
    res = estimate(1.0, "INR", "utilities.electricity")
    # Should preserve the full factor value: 0.1325303878714435
    assert abs(res.estimated_co2e_kg - 0.1325303878714435) < 1e-10


# ---------------------------------------------------------------------------
# Route B — activity-based factor
# ---------------------------------------------------------------------------

def test_route_b_electricity_kwh():
    res = estimate(
        amount=1000.0,
        currency="INR",
        category="utilities.electricity",
        activity_quantity=100.0,
        activity_unit="kWh",
    )
    assert res.emissions_status == "estimated"
    assert res.factor_method == "activity_based"
    assert res.activity_quantity == 100.0
    assert res.estimated_co2e_kg is not None
    # 100 kWh * 0.7117 kgCO2/kWh = 71.17
    assert abs(res.estimated_co2e_kg - 71.17) < 0.5


# ---------------------------------------------------------------------------
# No double-counting
# ---------------------------------------------------------------------------

def test_no_double_application_route_a():
    """Route A uses spend × spend_factor only. No physical factor multiplication."""
    res = estimate(1000.0, "INR", "utilities.electricity")
    assert res.factor_method == "spend_based"
    # The factor_id must be the spend factor, not the physical factor
    assert res.factor_id == "IN-CEA-ELECTRICITY-SPEND"
    # If factor_id were the physical factor, it would be IN-ELEC-CEA-V21-2024-25


def test_route_b_uses_physical_factor_only():
    """Route B uses quantity × physical_factor only."""
    res = estimate(
        amount=1000.0,
        currency="INR",
        category="utilities.electricity",
        activity_quantity=50.0,
        activity_unit="kWh",
    )
    assert res.factor_method == "activity_based"
    assert "CEA" in (res.factor_id or "")


# ---------------------------------------------------------------------------
# Unsupported categories — NULL emissions, never 0
# ---------------------------------------------------------------------------

def test_restaurant_unsupported():
    res = estimate(450.0, "INR", "food.restaurant_delivery")
    assert res.emissions_status == "unsupported"
    assert res.estimated_co2e_kg is None  # NEVER 0
    assert res.factor_id is None


def test_clothing_unsupported():
    res = estimate(1500.0, "INR", "shopping.clothing")
    assert res.estimated_co2e_kg is None
    assert res.emissions_status == "unsupported"


def test_ecommerce_unsupported():
    res = estimate(3200.0, "INR", "shopping.general_ecommerce")
    assert res.estimated_co2e_kg is None
    assert res.factor_id is None


def test_unclassified_unsupported():
    res = estimate(500.0, "INR", "other_unclassified")
    assert res.estimated_co2e_kg is None
    assert res.emissions_status == "unsupported"


# ---------------------------------------------------------------------------
# Excluded categories
# ---------------------------------------------------------------------------

def test_cash_withdrawal_excluded():
    res = estimate(5000.0, "INR", "cash_withdrawal_transfer")
    assert res.emissions_status == "excluded_non_consumption"
    assert res.estimated_co2e_kg is None


def test_refund_credit_excluded():
    res = estimate(800.0, "INR", "refund_credit")
    assert res.emissions_status == "excluded_non_consumption"
    assert res.estimated_co2e_kg is None


def test_negative_amount_excluded():
    """Negative amounts (refunds) are excluded even if not in refund_credit category."""
    res = estimate(-500.0, "INR", "food.basic_grocery")
    assert res.emissions_status == "excluded_refund"
    assert res.estimated_co2e_kg is None


# ---------------------------------------------------------------------------
# Non-INR currency — not estimated
# ---------------------------------------------------------------------------

def test_usd_not_estimated():
    res = estimate(50.0, "USD", "utilities.electricity")
    assert res.emissions_status == "unsupported"
    assert res.estimated_co2e_kg is None
    assert "NON_INR" in (res.estimation_notes or "")


def test_gbp_not_estimated():
    res = estimate(30.0, "GBP", "food.basic_grocery")
    assert res.estimated_co2e_kg is None


# ---------------------------------------------------------------------------
# Coverage metrics
# ---------------------------------------------------------------------------

def test_coverage_metrics_basic():
    df = pd.DataFrame({
        "amount": [1000.0, 500.0, 2000.0, -100.0],
        "currency": ["INR", "INR", "INR", "INR"],
        "emissions_status": ["estimated", "unsupported", "estimated", "excluded_refund"],
        "estimated_co2e_kg": [132.0, None, 200.0, None],
    })
    metrics = compute_coverage_metrics(df)
    assert metrics["estimated_count"] == 2
    assert metrics["unsupported_count"] == 1
    assert metrics["estimated_co2e_kg"] > 0
    assert metrics["supported_spend_pct"] is not None


def test_coverage_metrics_zero_denominator():
    """Supported pct must be None when total spend is 0, not ZeroDivisionError."""
    df = pd.DataFrame({
        "amount": [-100.0],
        "currency": ["INR"],
        "emissions_status": ["excluded_refund"],
        "estimated_co2e_kg": [None],
    })
    metrics = compute_coverage_metrics(df)
    assert metrics["supported_spend_pct"] is None


def test_coverage_metrics_no_unsupported_in_total():
    """Unsupported spend must not inflate the CO2e total."""
    df = pd.DataFrame({
        "amount": [1000.0, 5000.0],  # 1000 estimated, 5000 unsupported
        "currency": ["INR", "INR"],
        "emissions_status": ["estimated", "unsupported"],
        "estimated_co2e_kg": [100.0, None],
    })
    metrics = compute_coverage_metrics(df)
    assert metrics["estimated_co2e_kg"] == pytest.approx(100.0)
