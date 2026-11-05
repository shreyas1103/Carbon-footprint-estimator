"""
dashboard/pages/5_Settings.py
EcoTrack — Settings, Account Profile & Carbon Accounting Methodology
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


# ── Page Configuration ──
st.set_page_config(
    page_title="Settings & Methodology — EcoTrack",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_sidebar(current_page="Settings")


# ── Header ──
st.markdown("""
<div style="margin-bottom: 24px;">
    <div style="font-size: 13px; font-weight: 700; color: #246B45; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">
        Configuration & Governance
    </div>
    <div style="font-size: 30px; font-weight: 800; color: #1F2933; letter-spacing: -0.02em; margin-bottom: 6px;">
        Settings & Methodology
    </div>
    <div style="font-size: 14.5px; color: #78847D; max-width: 700px; line-height: 1.5;">
        Manage user preferences, inspect official Indian emission factor registries, and review our privacy standards.
    </div>
</div>
""", unsafe_allow_html=True)


tab1, tab2, tab3 = st.tabs(["👤 Account Profile", "📚 Factor Methodology", "🔒 Privacy & Data Protection"])

with tab1:
    st.markdown("""
    <div class="eco-card">
        <h3 class="eco-card-title">User Account Information</h3>
        <p class="eco-card-subtitle">Personal carbon accounting profile settings</p>
        
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-top: 20px;">
            <div>
                <div style="font-size: 12px; font-weight: 700; color: #78847D; text-transform: uppercase;">Name</div>
                <div style="font-size: 16px; font-weight: 700; color: #1F2933; margin-top: 4px;">Shreyas</div>
            </div>
            <div>
                <div style="font-size: 12px; font-weight: 700; color: #78847D; text-transform: uppercase;">Account Tier</div>
                <div style="font-size: 16px; font-weight: 700; color: #246B45; margin-top: 4px;">Personal Pro · Active</div>
            </div>
            <div>
                <div style="font-size: 12px; font-weight: 700; color: #78847D; text-transform: uppercase;">Primary Currency</div>
                <div style="font-size: 16px; font-weight: 700; color: #1F2933; margin-top: 4px;">INR (₹) — Indian Rupee</div>
            </div>
            <div>
                <div style="font-size: 12px; font-weight: 700; color: #78847D; text-transform: uppercase;">Baseline Standard</div>
                <div style="font-size: 16px; font-weight: 700; color: #1F2933; margin-top: 4px;">India CEA Baseline V21.0</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with tab2:
    st.markdown("""
    <div class="eco-card">
        <h3 class="eco-card-title">Hybrid Estimation Framework</h3>
        <p class="eco-card-subtitle">India-specific spend and physical activity factors</p>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 16px;">
            <div style="background: #FAFCF9; border: 1px solid #E7EAE5; border-radius: 12px; padding: 18px;">
                <div style="font-size: 15px; font-weight: 700; color: #174C35; margin-bottom: 8px;">Route A — Spend-Based</div>
                <div style="font-family: monospace; font-size: 13px; background: #FFFFFF; padding: 8px 12px; border-radius: 6px; border: 1px solid #E7EAE5; margin-bottom: 10px;">
                    CO₂e (kg) = Spend (INR) × Factor (kgCO₂e/INR)
                </div>
                <div style="font-size: 12.5px; color: #78847D; line-height: 1.5;">
                    Derived from official Household Consumer Expenditure Survey (HCES) economic data combined with national sector emissions.
                </div>
            </div>

            <div style="background: #FAFCF9; border: 1px solid #E7EAE5; border-radius: 12px; padding: 18px;">
                <div style="font-size: 15px; font-weight: 700; color: #174C35; margin-bottom: 8px;">Route B — Activity-Based</div>
                <div style="font-family: monospace; font-size: 13px; background: #FFFFFF; padding: 8px 12px; border-radius: 6px; border: 1px solid #E7EAE5; margin-bottom: 10px;">
                    Quantity = Spend / Unit Price<br>
                    CO₂e (kg) = Quantity × Physical Factor
                </div>
                <div style="font-size: 12.5px; color: #78847D; line-height: 1.5;">
                    Applied when direct physical quantities can be inferred (e.g. electricity units in kWh, motor petrol in litres).
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("Official Factor Sources")
    factors_data = [
        {"Category": "Electricity (Grid)", "Factor": "0.713 kg CO₂/kWh", "Standard": "CEA Baseline Database V21.0 (2024)", "Route": "Route B"},
        {"Category": "Motor Petrol", "Factor": "2.31 kg CO₂e/litre", "Standard": "MoEFCC / IPCC National GHG Inventory", "Route": "Route B"},
        {"Category": "LPG Cylinder Refill", "Factor": "1.66 kg CO₂e/kg LPG", "Standard": "Indian Oil / MoP&NG Standards", "Route": "Route B"},
        {"Category": "Restaurant Delivery", "Factor": "0.0018 kg CO₂e/INR", "Standard": "HCES Consumption Survey + LCA", "Route": "Route A"},
        {"Category": "Basic Groceries", "Factor": "0.0012 kg CO₂e/INR", "Standard": "ICAR Agricultural GHG Matrix", "Route": "Route A"},
        {"Category": "Rideshare / Taxi", "Factor": "0.14 kg CO₂e/km", "Standard": "BEE Automotive Standards (2023)", "Route": "Route A/B"},
    ]
    st.dataframe(pd.DataFrame(factors_data), use_container_width=True, hide_index=True)

with tab3:
    st.markdown("""
    <div class="eco-card">
        <h3 class="eco-card-title">Zero PII Retention Architecture</h3>
        <p class="eco-card-subtitle">Enterprise privacy safeguards built into the ingestion gateway</p>
        
        <ul style="font-size: 13.5px; color: #78847D; line-height: 1.8; margin-top: 14px;">
            <li><strong>Strict Reject-on-Detect:</strong> If a statement includes account numbers, PANs, card CVVs, IFSC codes, or passwords, the ingestion pipeline immediately halts and discards the file.</li>
            <li><strong>Schema Isolation:</strong> The system enforces <code>extra='forbid'</code>, guaranteeing that undeclared columns never enter memory or the database.</li>
            <li><strong>Descriptor Sanitization:</strong> Raw transaction descriptors are scrubbed of personal names, UPI handles, and reference hashes prior to storage.</li>
            <li><strong>Self-Contained Processing:</strong> All machine learning classification (TF-IDF + Logistic Regression) executes locally without transmitting raw statements to third-party endpoints.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

