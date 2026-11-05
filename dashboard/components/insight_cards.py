"""
dashboard/components/insight_cards.py
Rule-based sustainability highlight cards with sleek badges and clear takeaways.
"""
from __future__ import annotations

from typing import List, Dict, Any
import streamlit as st


def render_sustainability_insights(highlights: List[Dict[str, Any]]) -> None:
    """
    Render 3 crisp data-driven sustainability insight cards in a 3-column grid.
    """
    if not highlights:
        st.info("Upload transactions to generate automated sustainability highlights.", icon="💡")
        return

    cols = st.columns(len(highlights))
    for col, item in zip(cols, highlights):
        title = item.get("title", "Observation")
        text = item.get("text", "")
        icon = item.get("icon", "🌿")

        with col:
            st.markdown(f"""
            <div class="insight-card" style="height: 100%; display: flex; flex-direction: column; justify-content: flex-start;">
                <div class="insight-header">
                    <span style="font-size: 20px;">{icon}</span>
                    <span class="insight-title">{title}</span>
                </div>
                <p class="insight-desc" style="margin-top: 4px;">{text}</p>
            </div>
            """, unsafe_allow_html=True)

