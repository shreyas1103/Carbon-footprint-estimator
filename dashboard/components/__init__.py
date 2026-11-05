"""
dashboard/components/__init__.py
EcoTrack UI Component Library
"""
from .sidebar import render_sidebar, inject_custom_styles
from .metric_cards import render_kpi_cards
from .charts import render_monthly_trend_chart, render_category_bar_chart, render_donut_chart
from .insight_cards import render_sustainability_insights
from .progress_components import render_categorization_quality
from .transaction_components import render_recent_transactions, render_transactions_explorer

__all__ = [
    "render_sidebar",
    "inject_custom_styles",
    "render_kpi_cards",
    "render_monthly_trend_chart",
    "render_category_bar_chart",
    "render_donut_chart",
    "render_sustainability_insights",
    "render_categorization_quality",
    "render_recent_transactions",
    "render_transactions_explorer",
]

