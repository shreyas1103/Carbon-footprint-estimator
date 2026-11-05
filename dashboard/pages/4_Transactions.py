"""
dashboard/pages/4_Transactions.py
EcoTrack — Transaction History Explorer
Full-featured transaction explorer with merchant search, date range filters,
category multiselect, status toggles, sorting, and paginated clean records.
"""
from __future__ import annotations

import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st

from components.sidebar import render_sidebar
from components.transaction_components import render_transactions_explorer
from dashboard_utils import load_dashboard_data


# ── Page Configuration ──
st.set_page_config(
    page_title="Transaction History — EcoTrack",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_sidebar(current_page="Transaction History")


# ── Header ──
st.markdown("""
<div style="margin-bottom: 24px;">
    <div style="font-size: 13px; font-weight: 700; color: #246B45; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">
        Audit & Verification
    </div>
    <div style="font-size: 30px; font-weight: 800; color: #1F2933; letter-spacing: -0.02em; margin-bottom: 6px;">
        Transaction History Explorer
    </div>
    <div style="font-size: 14.5px; color: #78847D; max-width: 700px; line-height: 1.5;">
        Inspect individual spending entries, verify categorization assignments, check emission factors, 
        and filter transactions by merchant or status.
    </div>
</div>
""", unsafe_allow_html=True)


# ── Data Loading ──
raw_session_df = st.session_state.get("processed_df")
df = load_dashboard_data(raw_session_df)

if df is None or df.empty:
    st.markdown("""
    <div class="eco-card" style="text-align: center; padding: 48px 24px;">
        <div style="width: 52px; height: 52px; border-radius: 12px; background: #E7F3EB; color: #246B45; display: flex; align-items: center; justify-content: center; margin: 0 auto 16px auto; font-size: 24px;">
            🔍
        </div>
        <div style="font-size: 19px; font-weight: 700; color: #1F2933; margin-bottom: 8px;">
            No Transactions Found
        </div>
        <div style="font-size: 13.5px; color: #78847D; max-width: 440px; margin: 0 auto 20px auto;">
            Please upload a bank statement on the Upload page to view and explore individual transaction records.
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("📁 Go to Statement Upload", type="primary"):
        st.switch_page("pages/1_Upload.py")
    st.stop()


# ── Render Explorer ──
render_transactions_explorer(df)


# ── CSV Export Option ──
st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
with st.expander("⬇️ Export Filtered Transaction Data (CSV)", expanded=False):
    safe_export_cols = [
        c for c in df.columns if c not in ("raw_description",)
    ]
    csv_bytes = df[safe_export_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download Cleaned Dataset as CSV",
        data=csv_bytes,
        file_name="ecotrack_transactions_export.csv",
        mime="text/csv",
        key="btn_download_full_csv",
    )
    st.caption("Export contains only sanitized merchant descriptors and emissions estimates.")

