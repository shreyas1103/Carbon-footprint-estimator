"""
tests/test_dashboard_utils.py
Unit tests for dashboard helper functions in dashboard/dashboard_utils.py.
All tests are pure-pandas, no DB connection required.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard"))

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, date

from dashboard_utils import (
    _normalise_columns,
    filter_by_period,
    get_date_range,
    get_estimated,
    compute_kpis,
    get_monthly_trend,
    get_category_breakdown,
    get_donut_data,
    get_categorization_stats,
    get_sustainability_highlights,
    format_co2e,
    _friendly_category,
    SMALL_CATEGORY_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_df(rows: list[dict]) -> pd.DataFrame:
    """Construct a test DataFrame with normalised date column."""
    df = pd.DataFrame(rows)
    return _normalise_columns(df)


def _estimated_row(date_str: str, category: str, co2e: float, amount: float = 1000.0) -> dict:
    return {
        "date": date_str,
        "cleaned_description": f"Test {category}",
        "amount": amount,
        "currency": "INR",
        "category": category,
        "category_status": "categorized",
        "emissions_status": "estimated",
        "estimated_co2e_kg": co2e,
    }


def _unsupported_row(date_str: str, category: str, amount: float = 500.0) -> dict:
    return {
        "date": date_str,
        "cleaned_description": f"Test {category}",
        "amount": amount,
        "currency": "INR",
        "category": category,
        "category_status": "categorized",
        "emissions_status": "unsupported",
        "estimated_co2e_kg": None,
    }


def _needs_review_row(date_str: str) -> dict:
    return {
        "date": date_str,
        "cleaned_description": "IOCL",
        "amount": 2000.0,
        "currency": "INR",
        "category": "transport_fuel.unknown",
        "category_status": "needs_review",
        "emissions_status": "unsupported",
        "estimated_co2e_kg": None,
    }


def _unclassified_row(date_str: str) -> dict:
    return {
        "date": date_str,
        "cleaned_description": "Unknown XYZ",
        "amount": 300.0,
        "currency": "INR",
        "category": None,
        "category_status": "unclassified",
        "emissions_status": "unsupported",
        "estimated_co2e_kg": None,
    }


SAMPLE_DF = _make_df([
    _estimated_row("2024-01-15", "utilities.electricity", 12.5, 1500),
    _estimated_row("2024-01-22", "food.basic_grocery", 4.2, 800),
    _estimated_row("2024-02-10", "utilities.lpg", 8.0, 1000),
    _estimated_row("2024-02-18", "transport_fuel.petrol", 22.3, 3000),
    _unsupported_row("2024-01-05", "food.restaurant_delivery"),
    _needs_review_row("2024-02-07"),
    _unclassified_row("2024-02-20"),
])


# ---------------------------------------------------------------------------
# _normalise_columns
# ---------------------------------------------------------------------------

def test_normalise_renames_transaction_date():
    df = pd.DataFrame([{"transaction_date": "2024-01-01", "amount": 100}])
    result = _normalise_columns(df)
    assert "date" in result.columns
    assert "transaction_date" not in result.columns


def test_normalise_parses_date():
    df = pd.DataFrame([{"date": "2024-03-15", "amount": 200}])
    result = _normalise_columns(df)
    assert pd.api.types.is_datetime64_any_dtype(result["date"])


def test_normalise_coerces_invalid_date_to_nat():
    df = pd.DataFrame([{"date": "not-a-date", "amount": 200}])
    result = _normalise_columns(df)
    assert pd.isna(result["date"].iloc[0])


def test_normalise_handles_missing_columns():
    df = pd.DataFrame([{"amount": 100}])
    result = _normalise_columns(df)
    assert "category_status" in result.columns


# ---------------------------------------------------------------------------
# get_date_range
# ---------------------------------------------------------------------------

def test_date_range_correct():
    min_d, max_d = get_date_range(SAMPLE_DF)
    assert min_d.date() == date(2024, 1, 5)
    assert max_d.date() == date(2024, 2, 20)


def test_date_range_empty_df():
    min_d, max_d = get_date_range(pd.DataFrame())
    assert min_d is None and max_d is None


def test_date_range_all_nat():
    df = _make_df([{"date": "not-a-date", "amount": 100}])
    min_d, max_d = get_date_range(df)
    assert min_d is None and max_d is None


# ---------------------------------------------------------------------------
# filter_by_period
# ---------------------------------------------------------------------------

def test_filter_by_period_restricts_rows():
    filtered = filter_by_period(SAMPLE_DF, datetime(2024, 1, 1), datetime(2024, 1, 31))
    dates = filtered["date"].dropna()
    assert all(d.month == 1 for d in dates)


def test_filter_by_period_none_bounds_returns_all():
    filtered = filter_by_period(SAMPLE_DF, None, None)
    assert len(filtered) == len(SAMPLE_DF)


def test_filter_no_date_column():
    df = pd.DataFrame([{"amount": 100, "category": "food"}])
    # Should not crash
    result = filter_by_period(df, datetime(2024, 1, 1), datetime(2024, 12, 31))
    assert len(result) == 1


# ---------------------------------------------------------------------------
# get_estimated
# ---------------------------------------------------------------------------

def test_get_estimated_returns_only_estimated_rows():
    est = get_estimated(SAMPLE_DF)
    assert all(est["emissions_status"] == "estimated")
    assert all(est["estimated_co2e_kg"] > 0)


def test_get_estimated_excludes_none_co2e():
    df = _make_df([
        _estimated_row("2024-01-01", "utilities.electricity", 5.0),
        {"date": "2024-01-02", "emissions_status": "estimated", "estimated_co2e_kg": None,
         "category_status": "categorized", "amount": 100, "currency": "INR", "category": "food"},
    ])
    est = get_estimated(df)
    assert len(est) == 1
    assert est["estimated_co2e_kg"].iloc[0] == 5.0


def test_get_estimated_empty_df():
    est = get_estimated(pd.DataFrame())
    assert est.empty


def test_get_estimated_nan_co2e_excluded():
    df = _make_df([
        {"date": "2024-01-01", "emissions_status": "estimated",
         "estimated_co2e_kg": float("nan"),
         "category_status": "categorized", "amount": 100, "currency": "INR", "category": "food"},
    ])
    est = get_estimated(df)
    assert est.empty


# ---------------------------------------------------------------------------
# compute_kpis
# ---------------------------------------------------------------------------

def test_compute_kpis_total_co2e():
    kpis = compute_kpis(SAMPLE_DF)
    # Sum of all estimated rows: 12.5 + 4.2 + 8.0 + 22.3 = 47.0
    assert abs(kpis["total_co2e_kg"] - 47.0) < 0.01


def test_compute_kpis_transactions_count():
    kpis = compute_kpis(SAMPLE_DF)
    assert kpis["total_transactions"] == len(SAMPLE_DF)


def test_compute_kpis_estimated_count():
    kpis = compute_kpis(SAMPLE_DF)
    assert kpis["estimated_count"] == 4


def test_compute_kpis_top_category_is_petrol():
    kpis = compute_kpis(SAMPLE_DF)
    assert kpis["top_category"] == "transport_fuel.petrol"
    assert abs(kpis["top_category_co2e_kg"] - 22.3) < 0.01


def test_compute_kpis_avg_monthly():
    kpis = compute_kpis(SAMPLE_DF)
    # Jan: 12.5 + 4.2 = 16.7, Feb: 8.0 + 22.3 = 30.3, avg = 23.5
    assert kpis["avg_monthly_co2e_kg"] is not None
    assert abs(kpis["avg_monthly_co2e_kg"] - 23.5) < 0.01


def test_compute_kpis_empty_df():
    kpis = compute_kpis(pd.DataFrame())
    assert kpis["total_co2e_kg"] == 0.0
    assert kpis["avg_monthly_co2e_kg"] is None
    assert kpis["top_category"] is None
    assert kpis["total_transactions"] == 0


def test_compute_kpis_no_estimated_rows():
    df = _make_df([_unsupported_row("2024-01-01", "food.restaurant")])
    kpis = compute_kpis(df)
    assert kpis["total_co2e_kg"] == 0.0
    assert kpis["avg_monthly_co2e_kg"] is None
    assert kpis["top_category"] is None


def test_compute_kpis_nan_emissions_not_counted():
    """NaN emission values must not add to total CO2e."""
    df = _make_df([
        _estimated_row("2024-01-01", "utilities.electricity", 10.0),
        {"date": "2024-01-02", "emissions_status": "estimated",
         "estimated_co2e_kg": float("nan"),
         "category_status": "categorized", "amount": 200, "currency": "INR", "category": "food"},
    ])
    kpis = compute_kpis(df)
    assert abs(kpis["total_co2e_kg"] - 10.0) < 0.01


# ---------------------------------------------------------------------------
# get_monthly_trend
# ---------------------------------------------------------------------------

def test_monthly_trend_two_months():
    monthly = get_monthly_trend(SAMPLE_DF)
    assert len(monthly) == 2
    assert "2024-01" in monthly["month_str"].values
    assert "2024-02" in monthly["month_str"].values


def test_monthly_trend_jan_total():
    monthly = get_monthly_trend(SAMPLE_DF)
    jan = monthly[monthly["month_str"] == "2024-01"]["co2e_kg"].iloc[0]
    assert abs(jan - 16.7) < 0.01


def test_monthly_trend_feb_total():
    monthly = get_monthly_trend(SAMPLE_DF)
    feb = monthly[monthly["month_str"] == "2024-02"]["co2e_kg"].iloc[0]
    assert abs(feb - 30.3) < 0.01


def test_monthly_trend_sorted_ascending():
    monthly = get_monthly_trend(SAMPLE_DF)
    assert list(monthly["month_str"]) == sorted(monthly["month_str"].tolist())


def test_monthly_trend_empty():
    monthly = get_monthly_trend(pd.DataFrame())
    assert monthly.empty


def test_monthly_trend_unsupported_not_included():
    """Only estimated rows contribute to monthly CO2e."""
    df = _make_df([_unsupported_row("2024-01-01", "food.restaurant")])
    monthly = get_monthly_trend(df)
    assert monthly.empty


# ---------------------------------------------------------------------------
# get_category_breakdown
# ---------------------------------------------------------------------------

def test_category_breakdown_sorted_descending():
    cat = get_category_breakdown(SAMPLE_DF)
    assert cat["co2e_kg"].is_monotonic_decreasing


def test_category_breakdown_top_is_petrol():
    cat = get_category_breakdown(SAMPLE_DF)
    assert cat.iloc[0]["category"] == "transport_fuel.petrol"


def test_category_breakdown_unsupported_not_included():
    """Unsupported categories must not appear in category breakdown."""
    cat = get_category_breakdown(SAMPLE_DF)
    assert "food.restaurant_delivery" not in cat["category"].values


def test_category_breakdown_empty():
    cat = get_category_breakdown(pd.DataFrame())
    assert cat.empty


# ---------------------------------------------------------------------------
# get_donut_data
# ---------------------------------------------------------------------------

def test_donut_data_groups_small_categories():
    cat = get_category_breakdown(SAMPLE_DF)
    donut = get_donut_data(cat, threshold=0.3)
    # electricity (12.5) = 26.6% and grocery (4.2) = 8.9% should be grouped into Other
    assert "Other" in donut["category"].values


def test_donut_data_total_preserved():
    cat = get_category_breakdown(SAMPLE_DF)
    donut = get_donut_data(cat, threshold=0.03)
    assert abs(donut["co2e_kg"].sum() - cat["co2e_kg"].sum()) < 0.01


def test_donut_data_pct_sums_to_one():
    cat = get_category_breakdown(SAMPLE_DF)
    donut = get_donut_data(cat, threshold=0.03)
    assert abs(donut["pct"].sum() - 1.0) < 0.01


def test_donut_data_empty_input():
    donut = get_donut_data(pd.DataFrame(columns=["category", "co2e_kg"]))
    assert donut.empty


# ---------------------------------------------------------------------------
# get_categorization_stats
# ---------------------------------------------------------------------------

def test_cat_stats_totals():
    stats = get_categorization_stats(SAMPLE_DF)
    assert stats["total"] == len(SAMPLE_DF)
    assert stats["categorized"] == 5  # estimated + unsupported rows
    assert stats["needs_review"] == 1
    assert stats["unclassified"] == 1
    assert stats["estimated"] == 4


def test_cat_stats_pct_categorized():
    stats = get_categorization_stats(SAMPLE_DF)
    assert 0 < stats["pct_categorized"] <= 100


def test_cat_stats_empty():
    stats = get_categorization_stats(pd.DataFrame())
    assert stats["total"] == 0
    assert stats["pct_categorized"] == 0.0


# ---------------------------------------------------------------------------
# get_sustainability_highlights
# ---------------------------------------------------------------------------

def test_highlights_returns_list():
    cat = get_category_breakdown(SAMPLE_DF)
    highlights = get_sustainability_highlights(SAMPLE_DF, cat)
    assert isinstance(highlights, list)
    assert len(highlights) <= 3


def test_highlights_each_has_icon_and_text():
    cat = get_category_breakdown(SAMPLE_DF)
    highlights = get_sustainability_highlights(SAMPLE_DF, cat)
    for h in highlights:
        assert "icon" in h
        assert "text" in h
        assert len(h["text"]) > 10


def test_highlights_empty_when_no_data():
    highlights = get_sustainability_highlights(pd.DataFrame(), pd.DataFrame())
    assert highlights == []


def test_highlights_top_category_mentioned():
    cat = get_category_breakdown(SAMPLE_DF)
    highlights = get_sustainability_highlights(SAMPLE_DF, cat)
    # First highlight should mention the top category
    assert len(highlights) > 0
    assert "%" in highlights[0]["text"]


def test_highlights_month_comparison_two_months():
    """Two months of data → should include month-over-month comparison."""
    cat = get_category_breakdown(SAMPLE_DF)
    highlights = get_sustainability_highlights(SAMPLE_DF, cat)
    texts = " ".join(h["text"] for h in highlights)
    assert "month" in texts.lower() or "%" in texts


# ---------------------------------------------------------------------------
# format_co2e
# ---------------------------------------------------------------------------

def test_format_co2e_kg():
    assert format_co2e(47.5) == "47.50 kg CO₂e"


def test_format_co2e_tonnes():
    assert format_co2e(1500.0) == "1.50 t CO₂e"


def test_format_co2e_none():
    assert format_co2e(None) == "—"


def test_format_co2e_zero():
    assert "0.00" in format_co2e(0.0)


# ---------------------------------------------------------------------------
# _friendly_category
# ---------------------------------------------------------------------------

def test_friendly_category_simple():
    assert _friendly_category("utilities.electricity") == "Utilities — Electricity"


def test_friendly_category_multi_word():
    assert _friendly_category("food.basic_grocery") == "Food — Basic Grocery"


def test_friendly_category_single():
    assert _friendly_category("healthcare") == "Healthcare"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_single_month_data():
    """Single-month data should not crash any calculation."""
    df = _make_df([
        _estimated_row("2024-03-10", "utilities.electricity", 15.0),
        _estimated_row("2024-03-20", "food.basic_grocery", 5.0),
    ])
    kpis = compute_kpis(df)
    assert abs(kpis["total_co2e_kg"] - 20.0) < 0.01
    assert kpis["avg_monthly_co2e_kg"] is not None  # 1 month = avg = total

    monthly = get_monthly_trend(df)
    assert len(monthly) == 1

    cat = get_category_breakdown(df)
    assert len(cat) == 2


def test_all_unsupported_data():
    """All-unsupported dataset → no emissions metrics, no crash."""
    df = _make_df([_unsupported_row("2024-01-01", "food.restaurant")] * 3)
    kpis = compute_kpis(df)
    assert kpis["total_co2e_kg"] == 0.0
    assert kpis["top_category"] is None
    monthly = get_monthly_trend(df)
    assert monthly.empty


def test_mixed_nan_and_valid_emissions():
    """NaN emissions must be excluded from totals without crashing."""
    df = _make_df([
        _estimated_row("2024-01-01", "utilities.electricity", 10.0),
        {
            "date": "2024-01-02", "emissions_status": "estimated",
            "estimated_co2e_kg": float("nan"),
            "category_status": "categorized", "amount": 100, "currency": "INR", "category": "food",
        },
        _estimated_row("2024-01-03", "utilities.lpg", 6.0),
    ])
    kpis = compute_kpis(df)
    assert abs(kpis["total_co2e_kg"] - 16.0) < 0.01


def test_invalid_dates_handled():
    """Invalid date values should not cause crashes."""
    df = _make_df([
        {"date": "not-a-date", "emissions_status": "estimated",
         "estimated_co2e_kg": 10.0, "category": "utilities.electricity",
         "category_status": "categorized", "amount": 100, "currency": "INR"},
        _estimated_row("2024-01-05", "utilities.lpg", 8.0),
    ])
    monthly = get_monthly_trend(df)
    assert len(monthly) >= 1  # only the valid one


def test_kpi_total_matches_category_breakdown_total():
    """Dashboard KPI total must match sum of category breakdown."""
    kpis = compute_kpis(SAMPLE_DF)
    cat = get_category_breakdown(SAMPLE_DF)
    cat_total = float(cat["co2e_kg"].sum())
    assert abs(kpis["total_co2e_kg"] - cat_total) < 0.01


def test_monthly_total_matches_kpi_total():
    """Sum of monthly totals must equal KPI total CO2e."""
    kpis = compute_kpis(SAMPLE_DF)
    monthly = get_monthly_trend(SAMPLE_DF)
    monthly_total = float(monthly["co2e_kg"].sum())
    assert abs(kpis["total_co2e_kg"] - monthly_total) < 0.01


def test_donut_total_matches_category_breakdown_total():
    """Donut data total must equal category breakdown total."""
    cat = get_category_breakdown(SAMPLE_DF)
    donut = get_donut_data(cat, threshold=0.03)
    assert abs(donut["co2e_kg"].sum() - cat["co2e_kg"].sum()) < 0.01
