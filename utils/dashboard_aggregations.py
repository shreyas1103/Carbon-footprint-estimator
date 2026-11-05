"""
utils/dashboard_aggregations.py
Proxy re-export of dashboard.utils.dashboard_aggregations for flexible imports.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard"))

from dashboard_utils import (
    filter_by_period,
    get_date_range,
    get_estimated,
    get_monthly_trend,
    get_category_breakdown,
    get_donut_data,
    get_sustainability_highlights,
)

__all__ = [
    "filter_by_period",
    "get_date_range",
    "get_estimated",
    "get_monthly_trend",
    "get_category_breakdown",
    "get_donut_data",
    "get_sustainability_highlights",
]
