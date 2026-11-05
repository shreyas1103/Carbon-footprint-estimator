"""
dashboard/components/sidebar.py
Sidebar brand header, navigation styling, and user profile card.
"""
from __future__ import annotations

import os
import streamlit as st


def inject_custom_styles() -> None:
    """Read and inject the unified main.css stylesheet."""
    css_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "styles", "main.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)


def render_sidebar(current_page: str = "Dashboard") -> None:
    """Render the brand header and bottom profile inside the Streamlit sidebar."""
    inject_custom_styles()

    with st.sidebar:
        # ── Brand Header ──
        st.markdown("""
        <div style="padding: 10px 4px 18px 4px; border-bottom: 1px solid #E7EAE5; margin-bottom: 14px;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <div style="width: 36px; height: 36px; border-radius: 10px; background: #E7F3EB; display: flex; align-items: center; justify-content: center; color: #246B45;">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/>
                        <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>
                    </svg>
                </div>
                <div>
                    <div style="font-size: 19px; font-weight: 800; color: #1F2933; letter-spacing: -0.03em; line-height: 1.1;">
                        EcoTrack
                    </div>
                    <div style="font-size: 11px; font-weight: 600; color: #78847D; letter-spacing: 0.02em; text-transform: uppercase; margin-top: 2px;">
                        Carbon Intelligence
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Database Status Pill ──
        db_connected = False
        try:
            from database.connection import db_health_check
            db_status = db_health_check()
            db_connected = bool(db_status.get("ok"))
        except Exception:
            db_connected = False

        status_color = "#246B45" if db_connected else "#E9A45B"
        status_bg = "#E7F3EB" if db_connected else "#FDF3E7"
        status_text = "Live Database" if db_connected else "In-Session Mode"

        st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 12px; background: {status_bg}; border-radius: 8px; margin-bottom: 16px; border: 1px solid rgba(0,0,0,0.04);">
            <div style="display: flex; align-items: center; gap: 6px;">
                <span style="width: 7px; height: 7px; border-radius: 50%; background: {status_color}; display: inline-block;"></span>
                <span style="font-size: 11.5px; font-weight: 600; color: {status_color};">{status_text}</span>
            </div>
            <span style="font-size: 10.5px; font-weight: 600; color: {status_color}; opacity: 0.85;">v2.1</span>
        </div>
        """, unsafe_allow_html=True)

                # ── Custom Navigation ──
        st.markdown("""
        <div style="
            font-size: 11px;
            font-weight: 700;
            color: #9AA5A0;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin: 20px 4px 8px 4px;
        ">
            Menu
        </div>
        """, unsafe_allow_html=True)

        pages = [
            ("app.py", "Overview", "🏠"),
            ("pages/1_Upload.py", "Upload", "📁"),
            ("pages/2_Dashboard.py", "Dashboard", "📊"),
            ("pages/3_AI_Insights.py", "AI Insights", "💡"),
            ("pages/4_Transactions.py", "Transactions", "📋"),
            ("pages/5_Settings.py", "Settings", "⚙️"),
        ]

        #for page_path, label, icon in pages:
        #    st.page_link(
         #       page_path,
        #        label=f"{icon}  {label}",
         #       use_container_width=True
         #   )

        st.markdown(
            "<div style='height: 1px; background: #E7EAE5; margin: 20px 0;'></div>",
            unsafe_allow_html=True
        )

         # ── Custom Navigation ──

        st.markdown("""
        <div style="
            margin: 20px 4px 10px 4px;
            font-size: 11px;
            font-weight: 700;
            color: #78847D;
            letter-spacing: 1px;
        ">
            NAVIGATION
        </div>
        """, unsafe_allow_html=True)

        st.page_link("app.py", label="🏠  Overview", use_container_width=True)
        st.page_link("pages/1_Upload.py", label="📁  Upload", use_container_width=True)
        st.page_link("pages/2_Dashboard.py", label="📊  Dashboard", use_container_width=True)
        st.page_link("pages/3_AI_Insights.py", label="💡  AI Insights", use_container_width=True)
        st.page_link("pages/4_Transactions.py", label="📋  Transactions", use_container_width=True)
       # st.page_link("pages/5_Settings.py", label="⚙️  Settings", use_container_width=True)

        st.markdown("""
        <div style="
            height: 1px;
            background: #E7EAE5;
            margin: 18px 0;
        "></div>
        """, unsafe_allow_html=True)
        
        # Bottom User Profile Card (placed in sidebar)
        st.markdown("""
        <div style="margin-top: 36px; padding: 14px; background: #FFFFFF; border-radius: 12px; border: 1px solid #E7EAE5; box-shadow: 0 1px 4px rgba(0,0,0,0.03);">
            <div style="display: flex; align-items: center; gap: 10px;">
                <div style="width: 34px; height: 34px; border-radius: 50%; background: #246B45; color: #FFFFFF; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px;">
                    S
                </div>
                <div style="flex: 1; min-width: 0;">
                    <div style="font-size: 13px; font-weight: 700; color: #1F2933; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        Shreyas
                    </div>
                    <div style="font-size: 11px; color: #78847D;">
                        Personal Account
                    </div>
                </div>
                <span style="padding: 2px 7px; border-radius: 6px; background: #E7F3EB; color: #246B45; font-size: 10.5px; font-weight: 700;">
                    PRO
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)

