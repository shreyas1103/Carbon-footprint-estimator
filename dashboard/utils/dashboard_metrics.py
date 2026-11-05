"""
dashboard/utils/dashboard_metrics.py
Standardized KPI and metrics calculations for EcoTrack.
"""
from __future__ import annotations

import sys
import os

# Ensure dashboard directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
