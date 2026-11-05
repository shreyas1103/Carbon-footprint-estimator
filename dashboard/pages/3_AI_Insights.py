"""
dashboard/pages/3_AI_Insights.py
EcoTrack — AI-Powered Sustainability Insights
Prepares the interface for Milestone 3.3 (Personalized Gemini Recommendations).
Synthesizes user's actual category breakdown into targeted reduction pathways,
impact ratings, and actionable sustainability levers.
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
from dashboard_utils import (
    load_dashboard_data,
    compute_kpis,
    get_category_breakdown,
    friendly_category,
    format_co2e,
)


# ── Page Configuration ──
st.set_page_config(
    page_title="AI Insights — EcoTrack",
    page_icon="💡",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_sidebar(current_page="AI Insights")


# ── Header ──
st.markdown("""
<div style="margin-bottom: 24px;">
    <div style="font-size: 13px; font-weight: 700; color: #246B45; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">
        Intelligent Carbon Analytics
    </div>
    <div style="font-size: 30px; font-weight: 800; color: #1F2933; letter-spacing: -0.02em; margin-bottom: 6px;">
        AI-Powered Sustainability Insights
    </div>
    <div style="font-size: 14.5px; color: #78847D; max-width: 720px; line-height: 1.5;">
        Discover what drives your carbon footprint and where meaningful changes can make a difference. 
        Targeted reduction opportunities quantified using India-specific emission baselines.
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
            💡
        </div>
        <div style="font-size: 19px; font-weight: 700; color: #1F2933; margin-bottom: 8px;">
            No Spending Data to Analyze
        </div>
        <div style="font-size: 13.5px; color: #78847D; max-width: 440px; margin: 0 auto 20px auto;">
            Please upload a bank statement first so the engine can extract spending patterns and evaluate reduction pathways.
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("📁 Go to Statement Upload", type="primary"):
        st.switch_page("pages/1_Upload.py")
    st.stop()


# ── Calculate Real Analytics ──
kpis = compute_kpis(df)
cat_breakdown = get_category_breakdown(df)

total_co2e = kpis.get("total_co2e_kg", 0.0) or 0.0
top_cat_name = friendly_category(kpis.get("top_category"))
top_cat_pct = kpis.get("top_category_pct", 0.0) or 0.0
top_cat_co2e = kpis.get("top_category_co2e_kg", 0.0) or 0.0


# ── Milestone 3.3 Architecture Callout Banner ──
st.markdown("""
<div style="background: #F4FBF7; border: 1px solid #B7E4C7; border-radius: 12px; padding: 14px 18px; margin-bottom: 24px; display: flex; align-items: center; gap: 12px;">
    <span style="font-size: 22px;">🤖</span>
    <div style="font-size: 13px; color: #1F2933; line-height: 1.4;">
        <strong>Milestone 3.3 Ready:</strong> The recommendations below are calibrated directly to your real transaction emissions data.
        In Milestone 3.3, live Gemini generative narrative reasoning will connect dynamically via <code>pipeline/insights.py</code>.
    </div>
</div>
""", unsafe_allow_html=True)


# ── Footprint Summary Banner ──
col_b1, col_b2, col_b3 = st.columns([2, 1, 1])

with col_b1:
    st.markdown(f"""
    <div class="eco-card" style="margin-bottom: 24px; padding: 22px 26px;">
        <div style="font-size: 12.5px; font-weight: 700; color: #78847D; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px;">
            Total Monitored Footprint
        </div>
        <div style="font-size: 32px; font-weight: 800; color: #1F2933; letter-spacing: -0.02em;">
            {total_co2e:,.1f} <span style="font-size: 16px; font-weight: 600; color: #78847D;">kg CO₂e</span>
        </div>
        <div style="font-size: 13px; color: #78847D; margin-top: 6px;">
            Across <strong>{kpis['total_transactions']:,}</strong> transactions in your statement period.
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_b2:
    st.markdown(f"""
    <div class="eco-card" style="margin-bottom: 24px; padding: 22px 26px;">
        <div style="font-size: 12.5px; font-weight: 700; color: #78847D; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px;">
            Primary Driver
        </div>
        <div style="font-size: 22px; font-weight: 800; color: #246B45; letter-spacing: -0.01em;">
            {top_cat_name}
        </div>
        <div style="font-size: 13px; color: #78847D; margin-top: 6px;">
            Accounts for <strong>{top_cat_pct:.1f}%</strong> of total footprint.
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_b3:
    # Estimate a realistic 25% reduction across top category
    potential_reduction = (top_cat_co2e or 0.0) * 0.25
    st.markdown(f"""
    <div class="eco-card" style="margin-bottom: 24px; padding: 22px 26px; border-color: #B7E4C7; background: #FAFDFB;">
        <div style="font-size: 12.5px; font-weight: 700; color: #246B45; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px;">
            Target Potential
        </div>
        <div style="font-size: 26px; font-weight: 800; color: #246B45; letter-spacing: -0.01em;">
            -{potential_reduction:,.1f} <span style="font-size: 14px; font-weight: 600;">kg</span>
        </div>
        <div style="font-size: 13px; color: #78847D; margin-top: 6px;">
            Realistic 25% lever on primary category.
        </div>
    </div>
    """, unsafe_allow_html=True)


# ── AI Recommendation Cards ──
st.markdown("""
<div style="margin: 12px 0 16px 0;">
    <div style="font-size: 18px; font-weight: 800; color: #1F2933;">Targeted Action Pathways</div>
</div>
""", unsafe_allow_html=True)

# Generate recommendations tailored to user's top categories
recommendations = []

for _, row in cat_breakdown.head(3).iterrows():
    raw_cat = str(row["category"])
    cat_co2 = row["co2e_kg"]
    cat_title = row["category_friendly"]
    cat_pct = (cat_co2 / total_co2e * 100.0) if total_co2e > 0 else 0.0

    if "fuel" in raw_cat or "petrol" in raw_cat:
        recommendations.append({
            "title": f"Optimize Private Mobility ({cat_title})",
            "impact": "HIGH IMPACT",
            "impact_color": "#246B45",
            "impact_bg": "#E7F3EB",
            "reduction": f"Up to {cat_co2 * 0.30:,.1f} kg CO₂e / month",
            "summary": "Vehicle fuel contributes heavily to your monthly footprint due to direct combustion factors (2.31 kg CO₂e/litre for petrol).",
            "actions": [
                "Shift 2 commute days per week to electric transit or metro rail.",
                "Adopt smooth acceleration and tire pressure maintenance to improve fuel economy by 8-12%.",
                "Consolidate multiple personal errands into single-trip loops."
            ],
            "details": "Under MoEFCC and BEE standards, urban private vehicle travel is one of the most carbon-intensive domestic activities in India."
        })
    elif "electricity" in raw_cat:
        recommendations.append({
            "title": f"Household Grid Decarbonization ({cat_title})",
            "impact": "HIGH IMPACT",
            "impact_color": "#246B45",
            "impact_bg": "#E7F3EB",
            "reduction": f"Up to {cat_co2 * 0.25:,.1f} kg CO₂e / month",
            "summary": "India's grid emission factor (CEA Baseline V21.0: 0.713 kg CO₂/kWh) means heavy appliance usage produces substantial emissions.",
            "actions": [
                "Adjust AC thermostat to 24°C-25°C instead of 18°C-20°C (saves ~6% electricity per degree).",
                "Ensure refrigeration and cooling equipment have BEE 5-star ratings.",
                "Transition remaining lighting and auxiliary loads to high-efficiency LEDs."
            ],
            "details": "The Central Electricity Authority calculates an operating margin emission factor reflecting India's coal-heavy generation mix."
        })
    elif "delivery" in raw_cat or "restaurant" in raw_cat:
        recommendations.append({
            "title": f"Shift from Restaurant Delivery to Meal Planning ({cat_title})",
            "impact": "MEDIUM IMPACT",
            "impact_color": "#E9A45B",
            "impact_bg": "#FDF3E7",
            "reduction": f"Up to {cat_co2 * 0.35:,.1f} kg CO₂e / month",
            "summary": f"Restaurant food delivery involves packaging, single-use containers, and point-to-point courier transit across {cat_co2:,.1f} kg CO₂e.",
            "actions": [
                "Replace 2 weekend delivery orders with homemade whole-food meals.",
                "Opt out of single-use cutlery and plastic sachets at checkout.",
                "Support localized zero-emissions bicycle delivery vendors when available."
            ],
            "details": "Life-cycle emissions for restaurant delivery are significantly higher than home-cooked grains and vegetables due to supply chain overhead."
        })
    else:
        recommendations.append({
            "title": f"Carbon-Conscious Purchasing in {cat_title}",
            "impact": "LOW HANGING FRUIT",
            "impact_color": "#3B82F6",
            "impact_bg": "#EFF6FF",
            "reduction": f"Up to {cat_co2 * 0.20:,.1f} kg CO₂e / month",
            "summary": f"Your spending in {cat_title} accounts for {cat_pct:.1f}% of total estimated emissions.",
            "actions": [
                "Consolidate multiple small online retail orders to reduce courier logistics mileage.",
                "Prioritize certified repairable and durable goods over frequent replacements.",
                "Evaluate energy efficiency labels before purchasing electronics or appliances."
            ],
            "details": "Spend-based emission factors from NSSO/HCES reflect the average embedded carbon intensity per INR spent in this industry."
        })

# Render recommendation cards
if not recommendations:
    st.info("No actionable emission reduction pathways found for the currently classified transactions. Upload more transactions to generate insights.", icon="ℹ️")
else:
    for rec in recommendations:
        st.markdown(f"""
        <div class="eco-card" style="margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 10px;">
                <div style="font-size: 16.5px; font-weight: 700; color: #1F2933;">{rec['title']}</div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 12px; font-weight: 700; color: {rec['impact_color']}; background: {rec['impact_bg']}; padding: 3px 10px; border-radius: 6px;">
                        {rec['impact']}
                    </span>
                    <span style="font-size: 12px; font-weight: 700; color: #246B45;">
                        {rec['reduction']}
                    </span>
                </div>
            </div>
            <p style="font-size: 13.5px; color: #78847D; line-height: 1.5; margin-bottom: 12px;">
                {rec['summary']}
            </p>
        """, unsafe_allow_html=True)

        with st.expander("📋 Recommended Action Checklist & Methodology Note", expanded=False):
            for act in rec["actions"]:
                st.markdown(f"- **{act}**")
            st.caption(f"Methodology Note: {rec['details']}")

        st.markdown("</div>", unsafe_allow_html=True)


# ── Direct Navigation to Dashboard ──
st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
if st.button("📊 Return to Carbon Dashboard", type="primary"):
    st.switch_page("pages/2_Dashboard.py")

