"""
dashboard/pages/2_Dashboard.py
Overview dashboard: CO2e totals, category breakdown, monthly trend.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Dashboard — Carbon Footprint Estimator",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Emissions Dashboard")
st.caption("Carbon footprint overview for the last processed batch")


def _load_from_session() -> pd.DataFrame | None:
    return st.session_state.get("processed_df")


def _load_from_db() -> pd.DataFrame | None:
    try:
        from database.connection import get_session
        from database.models import Transaction
        session = get_session()
        if session is None:
            return None
        rows = session.query(Transaction).order_by(Transaction.transaction_date.desc()).limit(500).all()
        session.close()
        if not rows:
            return None
        return pd.DataFrame([{
            "date": r.transaction_date,
            "cleaned_description": r.cleaned_description,
            "amount": float(r.amount) if r.amount else 0,
            "currency": r.currency,
            "category": r.category,
            "subcategory": r.subcategory,
            "category_status": r.category_status,
            "emissions_status": r.emissions_status,
            "estimated_co2e_kg": float(r.estimated_co2e_kg) if r.estimated_co2e_kg else None,
            "emissions_confidence": r.emissions_confidence,
            "factor_id": r.factor_id,
            "factor_source": r.factor_source,
            "estimation_notes": r.estimation_notes,
            "batch_id": r.batch_id,
        } for r in rows])
    except Exception:
        return None


df = _load_from_session()
if df is None:
    df = _load_from_db()

if df is None or df.empty:
    st.info(
        "No processed transaction data found. "
        "Go to **Upload Transactions** to process a file first.",
        icon="📁",
    )
    st.stop()

# ---- Coverage metrics ----
from pipeline.emissions import compute_coverage_metrics
metrics = compute_coverage_metrics(df)

st.subheader("Summary")
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric(
    "🌿 Total CO₂e",
    f"{metrics['estimated_co2e_kg']:.2f} kg" if metrics['estimated_co2e_kg'] else "—",
    help="Supported transactions only",
)
col2.metric("💰 Total Eligible Spend", f"₹{metrics['total_expense_spend_inr']:,.0f}")
col3.metric(
    "📊 Spend Coverage",
    f"{metrics['supported_spend_pct']:.1f}%" if metrics['supported_spend_pct'] else "—",
)
col4.metric("✅ Estimated Txns", metrics["estimated_count"])
col5.metric("❓ Unsupported", metrics["unsupported_count"])

st.info(
    "⚠️ **Partial estimate** — only transactions with supported India-specific factors are included. "
    "This is not your complete carbon footprint.",
    icon="ℹ️",
)
st.divider()

# ---- Category breakdown chart ----
try:
    import plotly.express as px

    st.subheader("Category Emissions Breakdown")
    estimated_df = df[df.get("emissions_status", pd.Series(dtype=str)) == "estimated"].copy() if "emissions_status" in df.columns else pd.DataFrame()

    if estimated_df.empty:
        st.info("No estimated transactions to chart.")
    else:
        cat_group = (
            estimated_df.groupby("category")["estimated_co2e_kg"]
            .sum()
            .reset_index()
            .rename(columns={"category": "Category", "estimated_co2e_kg": "CO₂e (kg)"})
            .sort_values("CO₂e (kg)", ascending=True)
        )

        fig = px.bar(
            cat_group,
            x="CO₂e (kg)",
            y="Category",
            orientation="h",
            title="CO₂e by Category (estimated transactions only)",
            color="CO₂e (kg)",
            color_continuous_scale=["#D8F3DC", "#2D6A4F"],
            labels={"CO₂e (kg)": "kg CO₂e"},
        )
        fig.update_layout(
            plot_bgcolor="#FAF8F5",
            paper_bgcolor="#FAF8F5",
            coloraxis_showscale=False,
            height=max(300, len(cat_group) * 35),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ---- Monthly trend ----
    st.subheader("Monthly Trend")
    if "date" in df.columns and "estimated_co2e_kg" in df.columns:
        trend_df = df.copy()
        trend_df["date"] = pd.to_datetime(trend_df["date"], errors="coerce")
        trend_df = trend_df.dropna(subset=["date"])
        if not trend_df.empty:
            trend_df["month"] = trend_df["date"].dt.to_period("M").astype(str)
            monthly = (
                trend_df[trend_df.get("emissions_status", pd.Series(dtype=str)) == "estimated"]
                .groupby("month")["estimated_co2e_kg"]
                .sum()
                .reset_index()
                .rename(columns={"month": "Month", "estimated_co2e_kg": "CO₂e (kg)"})
            )
            if len(monthly) > 1:
                fig2 = px.line(
                    monthly,
                    x="Month",
                    y="CO₂e (kg)",
                    title="Monthly CO₂e Trend",
                    markers=True,
                    color_discrete_sequence=["#2D6A4F"],
                )
                fig2.update_layout(
                    plot_bgcolor="#FAF8F5",
                    paper_bgcolor="#FAF8F5",
                )
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("Need at least 2 months of data for a trend chart.")
        else:
            st.info("No date data available for trend analysis.")
    else:
        st.info("Date or emissions columns not found for trend chart.")

except ImportError:
    st.warning("Install `plotly` for interactive charts.", icon="📊")

st.divider()

# ---- Unsupported spend table ----
st.subheader("❓ Unsupported & Needs Review")
if "emissions_status" in df.columns:
    unsupported = df[df["emissions_status"].isin(["unsupported", "needs_review"])]
    if unsupported.empty:
        st.success("All eligible transactions have emissions estimates.", icon="✅")
    else:
        st.caption(
            f"{len(unsupported)} transactions could not be estimated. "
            "See 'estimation_notes' for reasons."
        )
        show_cols = [c for c in ["date", "cleaned_description", "amount", "category", "emissions_status", "estimation_notes"] if c in unsupported.columns]
        st.dataframe(unsupported[show_cols], use_container_width=True)
else:
    st.info("Process a file first to see unsupported transactions.")
