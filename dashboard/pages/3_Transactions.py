"""
dashboard/pages/3_Transactions.py
Transaction browser with filters.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Transactions — Carbon Footprint Estimator",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 Transaction Browser")

df = st.session_state.get("processed_df")

if df is None:
    try:
        from database.connection import get_session
        from database.models import Transaction
        session = get_session()
        if session:
            rows = session.query(Transaction).order_by(Transaction.transaction_date.desc()).all()
            session.close()
            if rows:
                df = pd.DataFrame([{
                    "date": r.transaction_date,
                    "cleaned_description": r.cleaned_description,
                    "amount": float(r.amount) if r.amount else 0,
                    "currency": r.currency,
                    "category": r.category,
                    "category_status": r.category_status,
                    "categorization_tier": r.categorization_tier,
                    "categorization_method": r.categorization_method,
                    "categorization_confidence": float(r.categorization_confidence) if r.categorization_confidence else None,
                    "emissions_status": r.emissions_status,
                    "estimated_co2e_kg": float(r.estimated_co2e_kg) if r.estimated_co2e_kg else None,
                    "emissions_confidence": r.emissions_confidence,
                    "factor_id": r.factor_id,
                    "factor_source": r.factor_source,
                    "estimation_notes": r.estimation_notes,
                } for r in rows])
    except Exception:
        pass

if df is None or df.empty:
    st.info("No processed data found. Upload a file first.", icon="📁")
    st.stop()

# ---- Filters ----
st.subheader("Filters")
col1, col2, col3 = st.columns(3)

with col1:
    all_cats = sorted(df["category"].dropna().unique().tolist()) if "category" in df.columns else []
    selected_cats = st.multiselect("Category", all_cats, key="filter_categories")

with col2:
    all_statuses = sorted(df["emissions_status"].dropna().unique().tolist()) if "emissions_status" in df.columns else []
    selected_statuses = st.multiselect("Emissions Status", all_statuses, key="filter_statuses")

with col3:
    search = st.text_input("Search description", key="filter_search")

filtered_df = df.copy()
if selected_cats:
    filtered_df = filtered_df[filtered_df["category"].isin(selected_cats)]
if selected_statuses:
    filtered_df = filtered_df[filtered_df["emissions_status"].isin(selected_statuses)]
if search:
    mask = filtered_df["cleaned_description"].str.contains(search, case=False, na=False)
    filtered_df = filtered_df[mask]

st.caption(f"Showing {len(filtered_df)} of {len(df)} transactions")

# ---- Display ----
display_cols = [
    "date", "cleaned_description", "amount", "currency",
    "category", "category_status", "categorization_tier", "categorization_method",
    "emissions_status", "estimated_co2e_kg", "emissions_confidence",
    "factor_id", "factor_source", "estimation_notes",
]
available = [c for c in display_cols if c in filtered_df.columns]

# Color coding for emissions status
def _highlight_status(val):
    colors = {
        "estimated": "background-color: #D8F3DC",
        "unsupported": "background-color: #FFF3CD",
        "excluded_refund": "background-color: #F8D7DA",
        "excluded_non_consumption": "background-color: #E2E3E5",
        "needs_review": "background-color: #FFF3CD",
        "error": "background-color: #F8D7DA",
    }
    return colors.get(str(val), "")

st.dataframe(
    filtered_df[available].style.applymap(
        _highlight_status, subset=["emissions_status"] if "emissions_status" in available else []
    ),
    use_container_width=True,
    height=500,
)

st.caption(
    "🟢 Estimated = CO₂e calculated | 🟡 Unsupported/Review = No India factor | "
    "🔴 Excluded = Refund, transfer, or non-consumption | ⬜ Error = Processing issue"
)
