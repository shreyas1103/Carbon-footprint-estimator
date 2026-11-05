"""
dashboard/utils/__init__.py
Modular re-exports for metrics and aggregations.
"""
from dashboard_utils import (
    load_dashboard_data,
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
    friendly_category,
)

__all__ = [
    "load_dashboard_data",
    "filter_by_period",
    "get_date_range",
    "get_estimated",
    "compute_kpis",
    "get_monthly_trend",
    "get_category_breakdown",
    "get_donut_data",
    "get_categorization_stats",
    "get_sustainability_highlights",
    "format_co2e",
    "friendly_category",
]
