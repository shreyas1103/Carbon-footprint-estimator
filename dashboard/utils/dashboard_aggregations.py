"""
dashboard/utils/dashboard_aggregations.py
Aggregations and trend calculations for EcoTrack.
"""
from __future__ import annotations

import sys
import os

# Ensure dashboard directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
