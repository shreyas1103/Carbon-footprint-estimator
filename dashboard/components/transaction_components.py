"""
dashboard/components/transaction_components.py
Visual transaction cards and dedicated explorer table for EcoTrack.
"""
from __future__ import annotations

import math
from typing import Optional
import pandas as pd
import streamlit as st
from dashboard_utils import friendly_category, format_co2e


def _get_category_icon(category: Optional[str]) -> str:
    """Return an appropriate emoji/symbol for the category."""
    if not category or pd.isna(category):
        return "❓"
    cat = str(category).lower()
    if "fuel" in cat or "petrol" in cat or "diesel" in cat:
        return "⛽"
    if "electricity" in cat or "utility" in cat or "power" in cat:
        return "⚡"
    if "lpg" in cat or "gas" in cat:
        return "🔥"
    if "air" in cat or "flight" in cat:
        return "✈️"
    if "taxi" in cat or "ride" in cat or "cab" in cat:
        return "🚕"
    if "transit" in cat or "train" in cat or "metro" in cat or "bus" in cat:
        return "🚆"
    if "grocery" in cat or "supermarket" in cat:
        return "🛒"
    if "food" in cat or "restaurant" in cat or "dining" in cat:
        return "🍽️"
    if "delivery" in cat:
        return "🛵"
    if "shopping" in cat or "apparel" in cat:
        return "🛍️"
    if "electronic" in cat:
        return "💻"
    if "health" in cat or "pharmacy" in cat or "medical" in cat:
        return "💊"
    if "entertainment" in cat or "movie" in cat:
        return "🎬"
    return "💳"


def render_recent_transactions(df: pd.DataFrame, limit: int = 5) -> None:
    """
    Render 5 most recent transactions as sleek list-style cards.
    """
    if df.empty:
        st.info("No recent transactions found.", icon="ℹ️")
        return

    # Sort descending by date
    sort_col = "date" if "date" in df.columns else "transaction_date"
    if sort_col in df.columns:
        df_sorted = df.sort_values(by=sort_col, ascending=False, na_position="last")
    else:
        df_sorted = df

    recent = df_sorted.head(limit)

    for _, row in recent.iterrows():
        merchant = str(row.get("cleaned_description", "Unknown Merchant"))
        if len(merchant) > 36:
            merchant = merchant[:33] + "..."

        raw_date = row.get("date")
        if pd.notna(raw_date):
            try:
                date_str = pd.to_datetime(raw_date).strftime("%d %b %Y")
            except Exception:
                date_str = str(raw_date)[:10]
        else:
            date_str = "—"

        raw_cat = row.get("category")
        category_label = friendly_category(raw_cat)
        icon = _get_category_icon(raw_cat)

        amount = row.get("amount", 0.0)
        amount_str = f"₹{amount:,.2f}" if pd.notna(amount) else "—"

        co2e = row.get("estimated_co2e_kg")
        status = str(row.get("emissions_status", "")).lower()

        if pd.notna(co2e) and co2e is not None and float(co2e) > 0:
            co2e_badge = f'<span style="color:#246B45; font-weight:700; font-size:13px;">+{float(co2e):.1f} kg CO₂e</span>'
        elif status == "unsupported":
            co2e_badge = '<span class="pill pill-gray" style="font-size:11px;">Not Estimated</span>'
        elif status == "needs_review":
            co2e_badge = '<span class="pill pill-orange" style="font-size:11px;">Review</span>'
        else:
            co2e_badge = '<span style="color:#78847D; font-size:12px;">—</span>'

        st.markdown(f"""
        <div class="tx-row">
            <div class="tx-left">
                <div class="tx-icon-box">{icon}</div>
                <div>
                    <div class="tx-merchant">{merchant}</div>
                    <div class="tx-meta">
                        <span>{date_str}</span>
                        <span>•</span>
                        <span class="pill pill-green" style="font-size: 11px; padding: 2px 8px;">{category_label}</span>
                    </div>
                </div>
            </div>
            <div class="tx-right">
                <div class="tx-amount">{amount_str}</div>
                <div style="margin-top: 3px;">{co2e_badge}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)


def render_transactions_explorer(df: pd.DataFrame) -> None:
    """
    Dedicated, rich transaction explorer with search, filtering, and pagination.
    """
    if df.empty:
        st.info("No transaction data available to explore.", icon="📁")
        return

    # Filter controls in 4 columns
    c1, c2, c3, c4 = st.columns([3, 2, 2, 2])

    with c1:
        search_query = st.text_input("🔍 Search Merchant", placeholder="Swiggy, Uber, Petrol...", key="tx_search")

    with c2:
        # Category list
        unique_cats = sorted([c for c in df["category"].dropna().unique() if str(c).strip()])
        cat_filter = st.multiselect("Category", options=unique_cats, key="tx_cat_filter")

    with c3:
        status_opts = ["All", "Estimated", "Needs Review", "Unsupported"]
        status_filter = st.selectbox("Status", options=status_opts, key="tx_status_filter")

    with c4:
        sort_by = st.selectbox("Sort By", options=[
            "Date: Newest", "Date: Oldest", "Amount: High to Low", "CO₂e: High to Low"
        ], key="tx_sort_by")

    # Apply filters
    filtered_df = df.copy()

    if search_query:
        q = search_query.strip().lower()
        filtered_df = filtered_df[
            filtered_df["cleaned_description"].astype(str).str.lower().str.contains(q, na=False)
        ]

    if cat_filter:
        filtered_df = filtered_df[filtered_df["category"].isin(cat_filter)]

    if status_filter == "Estimated":
        filtered_df = filtered_df[filtered_df["emissions_status"] == "estimated"]
    elif status_filter == "Needs Review":
        filtered_df = filtered_df[
            (filtered_df.get("category_status") == "needs_review") |
            (filtered_df.get("emissions_status") == "needs_review")
        ]
    elif status_filter == "Unsupported":
        filtered_df = filtered_df[filtered_df["emissions_status"] == "unsupported"]

    # Apply sorting
    if sort_by == "Date: Newest":
        filtered_df = filtered_df.sort_values(by="date", ascending=False, na_position="last")
    elif sort_by == "Date: Oldest":
        filtered_df = filtered_df.sort_values(by="date", ascending=True, na_position="last")
    elif sort_by == "Amount: High to Low":
        filtered_df = filtered_df.sort_values(by="amount", ascending=False, na_position="last")
    elif sort_by == "CO₂e: High to Low":
        filtered_df = filtered_df.sort_values(by="estimated_co2e_kg", ascending=False, na_position="last")

    # Metrics summary for current filter
    total_found = len(filtered_df)
    total_spend = filtered_df["amount"].sum() if "amount" in filtered_df.columns else 0.0
    total_emissions = filtered_df["estimated_co2e_kg"].dropna().sum() if "estimated_co2e_kg" in filtered_df.columns else 0.0

    st.markdown(f"""
    <div style="display: flex; gap: 16px; margin: 12px 0 16px 0; font-size: 13px; color: #78847D;">
        <span>Showing <strong>{total_found:,}</strong> transactions</span>
        <span>•</span>
        <span>Total Spend: <strong>₹{total_spend:,.2f}</strong></span>
        <span>•</span>
        <span>Total Estimated CO₂e: <strong>{total_emissions:,.1f} kg</strong></span>
    </div>
    """, unsafe_allow_html=True)

    if filtered_df.empty:
        st.warning("No transactions match the selected filters.", icon="⚠️")
        return

    # Pagination
    PAGE_SIZE = 15
    total_pages = max(1, math.ceil(total_found / PAGE_SIZE))
    
    col_p1, col_p2 = st.columns([1, 4])
    with col_p1:
        current_page = st.number_input(f"Page (1 to {total_pages})", min_value=1, max_value=total_pages, value=1, step=1)
    
    start_idx = (current_page - 1) * PAGE_SIZE
    page_df = filtered_df.iloc[start_idx:start_idx + PAGE_SIZE]

    # Render Clean Table View
    display_rows = []
    for _, row in page_df.iterrows():
        raw_date = row.get("date")
        date_val = pd.to_datetime(raw_date).strftime("%Y-%m-%d") if pd.notna(raw_date) else "—"
        merchant_val = str(row.get("cleaned_description", "—"))
        amount_val = f"₹{row.get('amount', 0.0):,.2f}"
        cat_val = friendly_category(row.get("category"))
        cat_status_val = str(row.get("category_status", "—"))
        co2e_val = row.get("estimated_co2e_kg")
        co2e_str = f"{float(co2e_val):,.2f} kg" if pd.notna(co2e_val) and co2e_val is not None else "—"
        status_val = str(row.get("emissions_status", "—"))

        display_rows.append({
            "Date": date_val,
            "Merchant": merchant_val,
            "Amount (INR)": amount_val,
            "Category": cat_val,
            "Categorization": cat_status_val,
            "CO₂e": co2e_str,
            "Status": status_val,
        })

    st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)

