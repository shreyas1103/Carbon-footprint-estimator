# """
# dashboard/app.py
# EcoTrack — Personal Carbon Intelligence
# Main application entry point & platform overview.
# """

# from __future__ import annotations
# import sys
# from pathlib import Path

# # Absolute path to CfootAg4
# PROJECT_ROOT = Path(__file__).resolve().parent.parent

# # Prioritize the main project directory
# if str(PROJECT_ROOT) in sys.path:
#     sys.path.remove(str(PROJECT_ROOT))

# sys.path.insert(0, str(PROJECT_ROOT))


# import os
# import sys

# # Ensure project root is in path
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# import streamlit as st
# from components.sidebar import render_sidebar
# from dashboard_utils import load_dashboard_data, compute_kpis, format_co2e, friendly_category


# st.set_page_config(
#     page_title="EcoTrack — Personal Carbon Intelligence",
#     page_icon="🌿",
#     layout="wide",
#     initial_sidebar_state="expanded",
# )

# render_sidebar(current_page="Overview")

# # ── Load Current Data (if any) ──
# raw_session_df = st.session_state.get("processed_df")
# current_df = load_dashboard_data(raw_session_df)


# # ── Hero Section ──
# st.markdown("""
# <div style="background: linear-gradient(135deg, #FFFFFF 0%, #F4F8F5 100%); border: 1px solid #E7EAE5; border-radius: 20px; padding: 40px 44px; margin-bottom: 28px; box-shadow: 0 4px 20px rgba(36, 107, 69, 0.05);">
#     <div style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 9999px; background: #E7F3EB; color: #174C35; font-size: 12.5px; font-weight: 700; margin-bottom: 16px;">
#         <span>🌿</span>
#         <span>India-Specific Carbon Accounting Engine</span>
#     </div>
#     <div style="font-size: 38px; font-weight: 800; color: #1F2933; letter-spacing: -0.03em; line-height: 1.15; margin-bottom: 12px;">
#         Turn Bank Statements into Climate Action
#     </div>
#     <div style="font-size: 16px; color: #78847D; max-width: 720px; line-height: 1.6; margin-bottom: 28px;">
#         EcoTrack bridges everyday personal financial transactions with official Indian environmental emission factors 
#         (CEA V21.0, NSSO/HCES, BEE, MoEFCC) to deliver transparent, audit-ready carbon intelligence.
#     </div>
# </div>
# """, unsafe_allow_html=True)


# # ── Action Bar / Snapshot ──
# if current_df is not None and not current_df.empty:
#     kpis = compute_kpis(current_df)
#     tot = kpis.get("total_co2e_kg", 0.0) or 0.0
#     tot_str = f"{tot / 1000.0:.2f} t CO₂e" if tot >= 1000 else f"{tot:,.1f} kg CO₂e"
#     top_c = friendly_category(kpis.get("top_category"))
#     tot_tx = kpis.get("total_transactions", 0) or 0
#     est_tx = kpis.get("estimated_transactions", 0) or kpis.get("estimated_count", 0) or 0

#     st.markdown(f"""
#     <div class="eco-card" style="margin-bottom: 28px;">
#         <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
#             <div>
#                 <div style="font-size: 13px; font-weight: 700; color: #246B45; text-transform: uppercase; letter-spacing: 0.05em;">Active Portfolio Detected</div>
#                 <div style="font-size: 20px; font-weight: 800; color: #1F2933; margin-top: 2px;">
#                     {tot_tx:,} Transactions Analyzed • {tot_str}
#                 </div>
#             </div>
#             <div style="display: flex; gap: 12px;">
#                 <span class="pill pill-green">Top Source: {top_c}</span>
#                 <span class="pill pill-gray">{est_tx:,} Factor Matches</span>
#             </div>
#         </div>
#     </div>
#     """, unsafe_allow_html=True)

#     c1, c2 = st.columns(2)
#     with c1:
#         if st.button("📊 Open Carbon Dashboard", type="primary", use_container_width=True):
#             st.switch_page("pages/2_Dashboard.py")
#     with c2:
#         if st.button("📁 Upload Additional Statement", use_container_width=True):
#             st.switch_page("pages/1_Upload.py")
# else:
#     c1, c2 = st.columns(2)
#     with c1:
#         if st.button("📁 Upload Your Bank Statement", type="primary", use_container_width=True):
#             st.switch_page("pages/1_Upload.py")
#     with c2:
#         if st.button("📊 Open Dashboard Preview", use_container_width=True):
#             st.switch_page("pages/2_Dashboard.py")


# st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)


# # ── How the Engine Works ──
# st.markdown("""
# <div style="margin-bottom: 16px;">
#     <div style="font-size: 13px; font-weight: 700; color: #246B45; text-transform: uppercase; letter-spacing: 0.05em;">Engine Architecture</div>
#     <div style="font-size: 22px; font-weight: 800; color: #1F2933; letter-spacing: -0.02em;">How EcoTrack Quantifies Your Footprint</div>
# </div>
# """, unsafe_allow_html=True)

# col_w1, col_w2, col_w3, col_w4 = st.columns(4)

# steps = [
#     ("01", "Upload & Sanitize", "Parse bank PDF or CSV statements. Sensitive account numbers and PII are strictly rejected at the gateway.", "🔒"),
#     ("02", "Multi-Tier Categorization", "Classify merchants using exact alias matching, TF-IDF + Logistic Regression, fuzzy search, and LLM fallback.", "🏷️"),
#     ("03", "Factor Calibration", "Map spend to official Indian factors: CEA Grid V21.0, HCES spend factors, BEE fuel equivalents, and MoEFCC guidelines.", "⚡"),
#     ("04", "Carbon Intelligence", "Explore monthly trajectories, category distribution, high-emission drivers, and personalized reduction insights.", "📈"),
# ]

# for col, (num, title, desc, icon) in zip([col_w1, col_w2, col_w3, col_w4], steps):
#     with col:
#         st.markdown(f"""
#         <div class="eco-card" style="height: 100%; display: flex; flex-direction: column; justify-content: space-between;">
#             <div>
#                 <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
#                     <span style="font-size: 12px; font-weight: 800; color: #246B45; background: #E7F3EB; padding: 2px 8px; border-radius: 6px;">{num}</span>
#                     <span style="font-size: 20px;">{icon}</span>
#                 </div>
#                 <div style="font-size: 15px; font-weight: 700; color: #1F2933; margin-bottom: 6px;">{title}</div>
#                 <div style="font-size: 12.5px; color: #78847D; line-height: 1.5;">{desc}</div>
#             </div>
#         </div>
#         """, unsafe_allow_html=True)


# # ── Methodology & Privacy Guarantees ──
# st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

# col_g1, col_g2 = st.columns(2)

# with col_g1:
#     st.markdown("""
#     <div class="eco-card" style="height: 100%;">
#         <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
#             <div style="width: 32px; height: 32px; border-radius: 8px; background: #E7F3EB; color: #246B45; display: flex; align-items: center; justify-content: center; font-size: 16px;">
#                 🏛️
#             </div>
#             <div style="font-size: 16px; font-weight: 700; color: #1F2933;">Official Indian Emission Sources</div>
#         </div>
#         <p style="font-size: 13px; color: #78847D; line-height: 1.6; margin: 0;">
#             Unlike global calculators relying on UK DEFRA or US EPA averages, EcoTrack utilizes India's Central Electricity 
#             Authority (CEA Baseline Database Version 21.0), Household Consumer Expenditure Survey (HCES), Bureau of 
#             Energy Efficiency (BEE), and MoEFCC transport standards.
#         </p>
#     </div>
#     """, unsafe_allow_html=True)

# with col_g2:
#     st.markdown("""
#     <div class="eco-card" style="height: 100%;">
#         <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
#             <div style="width: 32px; height: 32px; border-radius: 8px; background: #FDF3E7; color: #E9A45B; display: flex; align-items: center; justify-content: center; font-size: 16px;">
#                 🛡️
#             </div>
#             <div style="font-size: 16px; font-weight: 700; color: #1F2933;">Confidentiality & Privacy By Design</div>
#         </div>
#         <p style="font-size: 13px; color: #78847D; line-height: 1.6; margin: 0;">
#             All financial ingestion enforces strict schema validation (<code>extra='forbid'</code>). Account numbers, card 
#             digits, CVVs, and credentials never pass through the pipeline. Only cleaned merchant descriptors and amounts 
#             are computed for emissions.
#         </p>
#     </div>
#     """, unsafe_allow_html=True)


# # ── Footer ──
# st.markdown("""
# <div style="text-align: center; font-size: 12px; color: #78847D; margin-top: 48px; padding-top: 18px; border-top: 1px solid #E7EAE5;">
#     EcoTrack · Personal Carbon Intelligence Platform · Startup Version 2.1
# </div>
# """, unsafe_allow_html=True)


import streamlit as st

st.set_page_config(
    page_title="EcoTrack",
    page_icon="🌿",
    layout="wide"
)

st.title("🌿 EcoTrack")
st.success("EcoTrack is running successfully on Azure!")
st.write("Streamlit application started.")