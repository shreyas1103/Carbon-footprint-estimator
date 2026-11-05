"""
tests/test_components.py
Unit tests for dashboard reusable component rendering functions.
"""
import os
import sys
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard"))

from components.sidebar import inject_custom_styles
from components.metric_cards import render_kpi_cards
from components.charts import (
    render_monthly_trend_chart,
    render_category_bar_chart,
    render_donut_chart,
)
from components.insight_cards import render_sustainability_insights
from components.progress_components import render_categorization_quality
from components.transaction_components import (
    _get_category_icon,
    render_recent_transactions,
)


def test_custom_styles_inject_without_error():
    """Verify CSS injection doesn't raise errors."""
    try:
        inject_custom_styles()
    except Exception as exc:
        pytest.fail(f"inject_custom_styles raised an unexpected exception: {exc}")


def test_category_icon_mapping():
    """Verify category icons match merchant domain."""
    assert _get_category_icon("transport_fuel.petrol") == "⛽"
    assert _get_category_icon("utilities.electricity") == "⚡"
    assert _get_category_icon("utilities.lpg") == "🔥"
    assert _get_category_icon("transport.air_travel") == "✈️"
    assert _get_category_icon("transport.taxi_rideshare") == "🚕"
    assert _get_category_icon("transport.public_transit") == "🚆"
    assert _get_category_icon("food.basic_grocery") == "🛒"
    assert _get_category_icon("food.restaurant_delivery") in ("🍽️", "🛵")
    assert _get_category_icon("shopping.electronics") in ("💻", "🛍️")
    assert _get_category_icon("healthcare") == "💊"
    assert _get_category_icon("entertainment") == "🎬"
    assert _get_category_icon(None) == "❓"


def test_render_kpi_cards_empty():
    """Verify render_kpi_cards handles empty dict without failing."""
    try:
        render_kpi_cards({})
    except Exception as exc:
        pytest.fail(f"render_kpi_cards raised error on empty dict: {exc}")


def test_render_kpi_cards_populated():
    """Verify render_kpi_cards handles valid metrics."""
    kpis = {
        "total_co2e_kg": 1540.5,
        "avg_monthly_co2e_kg": 770.25,
        "top_category": "transport_fuel.petrol",
        "top_category_co2e_kg": 1200.0,
        "top_category_pct": 77.9,
        "total_transactions": 25,
        "estimated_transactions": 20,
    }
    try:
        render_kpi_cards(kpis)
    except Exception as exc:
        pytest.fail(f"render_kpi_cards failed on valid kpis: {exc}")


def test_render_charts_empty():
    """Verify chart rendering functions gracefully handle empty DataFrames."""
    empty_df = pd.DataFrame()
    render_monthly_trend_chart(empty_df)
    render_category_bar_chart(empty_df)
    render_donut_chart(empty_df, total_co2e_kg=0.0)


def test_render_charts_single_month():
    """Verify monthly trend handles single month data without spline crash."""
    single_month = pd.DataFrame([{"month_label": "Oct 2026", "co2e_kg": 240.5}])
    try:
        render_monthly_trend_chart(single_month)
    except Exception as exc:
        pytest.fail(f"render_monthly_trend_chart failed on single month: {exc}")


def test_render_charts_multi_month():
    """Verify monthly trend handles multi-month spline line."""
    multi_month = pd.DataFrame([
        {"month_label": "Sep 2026", "co2e_kg": 150.0},
        {"month_label": "Oct 2026", "co2e_kg": 210.0},
        {"month_label": "Nov 2026", "co2e_kg": 180.0},
    ])
    try:
        render_monthly_trend_chart(multi_month)
    except Exception as exc:
        pytest.fail(f"render_monthly_trend_chart failed on multi month: {exc}")


def test_render_category_bar_populated():
    """Verify category horizontal bar handles data."""
    cats = pd.DataFrame([
        {"category": "transport_fuel.petrol", "category_friendly": "Petrol", "co2e_kg": 120.5},
        {"category": "food.restaurant_delivery", "category_friendly": "Restaurant Delivery", "co2e_kg": 45.2},
    ])
    try:
        render_category_bar_chart(cats)
    except Exception as exc:
        pytest.fail(f"render_category_bar_chart failed on valid data: {exc}")


def test_render_donut_populated():
    """Verify donut handles data and total calculation."""
    donut = pd.DataFrame([
        {"category_friendly": "Petrol", "co2e_kg": 120.5, "pct": 0.72},
        {"category_friendly": "Delivery", "co2e_kg": 45.2, "pct": 0.28},
    ])
    try:
        render_donut_chart(donut, total_co2e_kg=165.7)
    except Exception as exc:
        pytest.fail(f"render_donut_chart failed on valid data: {exc}")


def test_render_insights_empty_and_populated():
    """Verify sustainability insights rendering."""
    render_sustainability_insights([])
    insights = [
        {"icon": "⛽", "title": "Highest Source", "text": "Petrol is 72% of emissions."},
        {"icon": "📈", "title": "Monthly Trajectory", "text": "Emissions up 12% MoM."},
    ]
    render_sustainability_insights(insights)


def test_render_progress_components():
    """Verify categorization quality progress component."""
    render_categorization_quality({})
    render_categorization_quality({
        "total": 50,
        "categorized": 45,
        "needs_review": 3,
        "unclassified": 2,
        "pct_categorized": 90.0,
        "estimated_emissions_count": 40,
        "pct_with_emissions": 80.0,
    })


def test_render_recent_transactions():
    """Verify recent transactions rendering."""
    render_recent_transactions(pd.DataFrame())
    txs = pd.DataFrame([
        {
            "date": "2026-10-15",
            "cleaned_description": "SWIGGY BANGALORE",
            "amount": 450.0,
            "category": "food.restaurant_delivery",
            "emissions_status": "estimated",
            "estimated_co2e_kg": 0.81,
        },
        {
            "date": "2026-10-18",
            "cleaned_description": "HP PETROL PUMP",
            "amount": 2500.0,
            "category": "transport_fuel.petrol",
            "emissions_status": "estimated",
            "estimated_co2e_kg": 57.75,
        },
    ])
    render_recent_transactions(txs, limit=5)


def test_standardized_kpi_contract():
    """Verify all 10 required standardized KPI keys and aliases exist."""
    from dashboard_utils import compute_kpis

    # Test with populated df
    sample = pd.DataFrame([
        {
            "date": "2026-09-01",
            "amount": 1000.0,
            "category": "transport_fuel.petrol",
            "category_status": "categorized",
            "emissions_status": "estimated",
            "estimated_co2e_kg": 23.1,
        },
        {
            "date": "2026-09-15",
            "amount": 500.0,
            "category": "food.basic_grocery",
            "category_status": "categorized",
            "emissions_status": "estimated",
            "estimated_co2e_kg": 0.6,
        },
        {
            "date": "2026-09-20",
            "amount": 200.0,
            "category": None,
            "category_status": "unclassified",
            "emissions_status": "unsupported",
            "estimated_co2e_kg": None,
        },
    ])

    kpis = compute_kpis(sample)

    # 10 Required Keys
    required_keys = [
        "total_co2e_kg",
        "average_monthly_co2e",
        "top_category",
        "top_category_co2e_kg",
        "top_category_pct",
        "total_transactions",
        "estimated_transactions",
        "categorized_transactions",
        "unclassified_transactions",
        "categorization_rate",
    ]
    for key in required_keys:
        assert key in kpis, f"Missing required KPI key: {key}"

    # Backward compatibility aliases
    assert "avg_monthly_co2e_kg" in kpis
    assert "estimated_count" in kpis
    assert "categorized_count" in kpis

    # Value assertions
    assert kpis["total_transactions"] == 3
    assert kpis["categorized_transactions"] == 2
    assert kpis["estimated_transactions"] == 2
    assert kpis["unclassified_transactions"] == 1
    assert kpis["top_category"] == "transport_fuel.petrol"
    assert kpis["top_category_pct"] > 90.0  # 23.1 / 23.7 * 100
    assert kpis["categorization_rate"] == round((2 / 3) * 100, 2)


def test_standardized_kpi_contract_empty():
    """Verify compute_kpis handles empty DataFrame with all required keys."""
    from dashboard_utils import compute_kpis
    kpis = compute_kpis(pd.DataFrame())

    required_keys = [
        "total_co2e_kg",
        "average_monthly_co2e",
        "top_category",
        "top_category_co2e_kg",
        "top_category_pct",
        "total_transactions",
        "estimated_transactions",
        "categorized_transactions",
        "unclassified_transactions",
        "categorization_rate",
    ]
    for key in required_keys:
        assert key in kpis, f"Missing required KPI key on empty: {key}"

    assert kpis["total_transactions"] == 0
    assert kpis["total_co2e_kg"] == 0.0
    assert kpis["average_monthly_co2e"] is None
    assert kpis["top_category"] is None
    assert kpis["top_category_pct"] == 0.0


def test_filter_by_period_keyword_and_positional():
    """Verify filter_by_period accepts keyword args (start_date, end_date) and positional."""
    from dashboard_utils import filter_by_period
    from datetime import date

    df = pd.DataFrame([
        {"date": pd.Timestamp("2026-08-01"), "val": 1},
        {"date": pd.Timestamp("2026-08-15"), "val": 2},
        {"date": pd.Timestamp("2026-09-01"), "val": 3},
    ])

    # Keyword args (start_date, end_date)
    res_kw = filter_by_period(df, start_date=date(2026, 8, 1), end_date=date(2026, 8, 31))
    assert len(res_kw) == 2

    # Positional args (df, start_date, end_date)
    res_pos = filter_by_period(df, date(2026, 8, 10), date(2026, 9, 10))
    assert len(res_pos) == 2

    # Backward compatibility (start=..., end=...)
    res_compat = filter_by_period(df, start=date(2026, 8, 1), end=date(2026, 8, 31))
    assert len(res_compat) == 2


def test_dashboard_utils_reexports():
    """Verify utils.dashboard_metrics and utils.dashboard_aggregations work."""
    from utils.dashboard_metrics import compute_kpis, format_co2e, friendly_category
    from utils.dashboard_aggregations import filter_by_period, get_monthly_trend

    assert callable(compute_kpis)
    assert callable(format_co2e)
    assert callable(friendly_category)
    assert callable(filter_by_period)
    assert callable(get_monthly_trend)

