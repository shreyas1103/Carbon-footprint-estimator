"""
utils/dashboard_metrics.py
Proxy re-export of dashboard.utils.dashboard_metrics for flexible imports.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard"))

from dashboard_utils import (
    compute_kpis,
    get_categorization_stats,
    format_co2e,
    friendly_category,
    load_dashboard_data,
)

__all__ = [
    "compute_kpis",
    "get_categorization_stats",
    "format_co2e",
    "friendly_category",
    "load_dashboard_data",
]
