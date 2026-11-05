"""
dashboard/pages/2_Dashboard.py
EcoTrack — Personal Carbon Intelligence Dashboard
Flagship executive sustainability dashboard featuring:
  A. Header & Period Filter
  B. Key Metric Cards (KPIs)
  C. Monthly Emissions Trend (Plotly Area)
  D. Emissions by Category (Plotly Horizontal Bar)
  E. Emission Composition (Plotly Donut)
  F. Sustainability Highlights
  G. Categorization Quality & Factor Coverage
  H. Recent Transactions (Compact List)
"""
from __future__ import annotations

import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st

from dashboard_utils import (
    load_dashboard_data,
    get_date_range,
    filter_by_period,
    compute_kpis,
    get_monthly_trend,
    get_category_breakdown,
    get_donut_data,
    get_categorization_stats,
    get_sustainability_highlights,
    format_co2e,
)
from components.sidebar import render_sidebar
from components.metric_cards import render_kpi_cards
from components.charts import (
    render_monthly_trend_chart,
    render_category_bar_chart,
    render_donut_chart,
)
from components.insight_cards import render_sustainability_insights
from components.progress_components import render_categorization_quality
from components.transaction_components import render_recent_transactions


# ── Streamlit Page Configuration ─────────────────────────────────────────────
st.set_page_config(
    page_title="Dashboard — EcoTrack Carbon Intelligence",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Render Custom Sidebar & Styles ───────────────────────────────────────────
render_sidebar(current_page="Dashboard")


# ── Load Data ─────────────────────────────────────────────────────────────────
raw_session_df = st.session_state.get("processed_df")
full_df = load_dashboard_data(raw_session_df)


# ── Section A: Header ─────────────────────────────────────────────────────────
header_col1, header_col2 = st.columns([3, 1])

with header_col1:
    st.markdown("""
    <div style="margin-bottom: 24px;">
        <div style="font-size: 14px; font-weight: 600; color: #246B45; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;">
            <span>Good morning, Shreyas</span>
            <span>👋</span>
        </div>
        <div style="font-size: 32px; font-weight: 800; color: #1F2933; letter-spacing: -0.03em; line-height: 1.15; margin-bottom: 6px;">
            Your Carbon Footprint
        </div>
        <div style="font-size: 14.5px; color: #78847D; max-width: 650px;">
            Understand the environmental impact of your everyday spending through India-specific hybrid emissions factors.
        </div>
    </div>
    """, unsafe_allow_html=True)

with header_col2:
    st.markdown("""
    <div style="text-align: right; margin-top: 8px;">
        <span class="pill pill-green">
            <span style="width: 6px; height: 6px; border-radius: 50%; background: #246B45;"></span>
            Reporting Period Active
        </span>
    </div>
    """, unsafe_allow_html=True)


# ── Check Data Availability ───────────────────────────────────────────────────
if full_df is None or full_df.empty:
    st.markdown("""
    <div class="eco-card" style="text-align: center; padding: 48px 24px;">
        <div style="width: 54px; height: 54px; border-radius: 14px; background: #E7F3EB; color: #246B45; display: flex; align-items: center; justify-content: center; margin: 0 auto 16px auto; font-size: 24px;">
            🌿
        </div>
        <div style="font-size: 20px; font-weight: 700; color: #1F2933; margin-bottom: 8px;">
            No Transaction Data Loaded Yet
        </div>
        <div style="font-size: 14px; color: #78847D; max-width: 480px; margin: 0 auto 24px auto;">
            Upload your bank statement (PDF or CSV) on the Upload page to categorize your spending and analyze your emissions.
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("📁 Go to Statement Upload", type="primary"):
        st.switch_page("pages/1_Upload.py")
    st.stop()


# ── Period Filter Bar ─────────────────────────────────────────────────────────
min_date, max_date = get_date_range(full_df)

filter_container = st.container()
with filter_container:
    col_f1, col_f2, col_f3 = st.columns([2, 2, 3])

    with col_f1:
        start_bound = min_date if min_date else None
        filter_start = st.date_input(
            "📅 From Date",
            value=min_date,
            min_value=min_date,
            max_value=max_date,
            key="dash_from_date",
        )

    with col_f2:
        filter_end = st.date_input(
            "📅 To Date",
            value=max_date,
            min_value=min_date,
            max_value=max_date,
            key="dash_to_date",
        )

    with col_f3:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if min_date and max_date:
            st.markdown(f"""
            <div style="font-size: 12.5px; color: #78847D; padding-top: 4px;">
                Statement Range: <strong>{min_date.strftime('%d %b %Y')}</strong> — <strong>{max_date.strftime('%d %b %Y')}</strong>
            </div>
            """, unsafe_allow_html=True)

# Filter dataset to selected range
filtered_df = filter_by_period(full_df, start_date=filter_start, end_date=filter_end)

if filtered_df.empty:
    st.warning("No transactions found within the selected date range. Please broaden your filter.", icon="⚠️")
    st.stop()


# ── Calculate Real Analytics ──────────────────────────────────────────────────
kpis = compute_kpis(filtered_df)
monthly_trend_df = get_monthly_trend(filtered_df)
category_breakdown_df = get_category_breakdown(filtered_df)
donut_df = get_donut_data(category_breakdown_df)
cat_stats = get_categorization_stats(filtered_df)
highlights = get_sustainability_highlights(filtered_df, category_breakdown_df)


# ── Section B: Custom KPI Cards ───────────────────────────────────────────────
render_kpi_cards(kpis)


# ── Section C & Section D: Monthly Trend and Category Breakdown ───────────────
chart_col1, chart_col2 = st.columns([1, 1])

with chart_col1:
    st.markdown("""
    <div class="eco-card">
        <div class="eco-card-header">
            <div>
                <h3 class="eco-card-title">Carbon Footprint Over Time</h3>
                <p class="eco-card-subtitle">Track how your estimated emissions change month by month</p>
            </div>
        </div>
    """, unsafe_allow_html=True)
    render_monthly_trend_chart(monthly_trend_df)
    st.markdown("</div>", unsafe_allow_html=True)

with chart_col2:
    st.markdown("""
    <div class="eco-card">
        <div class="eco-card-header">
            <div>
                <h3 class="eco-card-title">Where Your Emissions Come From</h3>
                <p class="eco-card-subtitle">CO₂e emissions ranked by transaction spending category</p>
            </div>
        </div>
    """, unsafe_allow_html=True)
    render_category_bar_chart(category_breakdown_df)
    st.markdown("</div>", unsafe_allow_html=True)


# ── Section E & Section F: Composition Donut & Sustainability Highlights ──────
bottom_col1, bottom_col2 = st.columns([1, 1])

with bottom_col1:
    st.markdown("""
    <div class="eco-card">
        <div class="eco-card-header">
            <div>
                <h3 class="eco-card-title">Carbon Footprint Distribution</h3>
                <p class="eco-card-subtitle">Proportional breakdown of estimated spending emissions</p>
            </div>
        </div>
    """, unsafe_allow_html=True)
    render_donut_chart(donut_df, total_co2e_kg=kpis["total_co2e_kg"])
    st.markdown("</div>", unsafe_allow_html=True)

with bottom_col2:
    st.markdown("""
    <div class="eco-card">
        <div class="eco-card-header">
            <div>
                <h3 class="eco-card-title">Sustainability Highlights</h3>
                <p class="eco-card-subtitle">Automated rule-based insights from your spending profile</p>
            </div>
        </div>
    """, unsafe_allow_html=True)
    render_sustainability_insights(highlights)
    st.markdown("</div>", unsafe_allow_html=True)


# ── Section G: Categorization Quality ─────────────────────────────────────────
st.markdown("""
<div class="eco-card">
    <div class="eco-card-header">
        <div>
            <h3 class="eco-card-title">Transaction Categorization & Factor Coverage</h3>
            <p class="eco-card-subtitle">Pipeline transparency: identifying activity vs. applying verified India factors</p>
        </div>
    </div>
""", unsafe_allow_html=True)
render_categorization_quality(cat_stats)
st.markdown("</div>", unsafe_allow_html=True)


# ── Section H: Recent Transactions ────────────────────────────────────────────
st.markdown("""
<div class="eco-card">
    <div class="eco-card-header">
        <div>
            <h3 class="eco-card-title">Recent Transactions</h3>
            <p class="eco-card-subtitle">Latest spending activity with estimated emissions</p>
        </div>
    </div>
""", unsafe_allow_html=True)

render_recent_transactions(filtered_df, limit=5)

col_act1, col_act2 = st.columns([3, 1])
with col_act2:
    if st.button("🔍 View All Transactions", key="btn_view_all_tx"):
        st.switch_page("pages/4_Transactions.py")

st.markdown("</div>", unsafe_allow_html=True)


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align: center; font-size: 12px; color: #78847D; margin-top: 36px; padding-top: 18px; border-top: 1px solid #E7EAE5;">
    EcoTrack · India Emissions Engine (CEA V21.0, HCES, BEE, MoEFCC) · Confidential & Privacy-First
</div>
""", unsafe_allow_html=True)
