"""
dashboard/components/progress_components.py

Visual indicators for transaction categorization quality
and emission factor coverage.
"""

from __future__ import annotations

from typing import Dict, Any
import streamlit as st
import textwrap


def render_categorization_quality(stats: Dict[str, Any]) -> None:
    """
    Render categorization quality metrics and emission coverage
    using responsive visual progress cards.
    """

    # --------------------------------------------------
    # 1. Extract statistics safely
    # --------------------------------------------------

    total = int(stats.get("total", 0) or 0)
    categorized = int(stats.get("categorized", 0) or 0)
    needs_review = int(stats.get("needs_review", 0) or 0)
    unclassified = int(stats.get("unclassified", 0) or 0)

    pct_cat = float(stats.get("pct_categorized", 0.0) or 0.0)

    # Support both existing and alternate statistics keys
    est_count = int(
        stats.get(
            "estimated_emissions_count",
            stats.get("estimated", 0)
        ) or 0
    )

    pct_est = stats.get("pct_with_emissions")

    if pct_est is None:
        pct_est = (
            (est_count / total) * 100
            if total > 0
            else 0.0
        )

    pct_est = float(pct_est or 0.0)

    # Clamp percentages between 0 and 100
    cat_width = max(0.0, min(pct_cat, 100.0))
    emission_width = max(0.0, min(pct_est, 100.0))

    # --------------------------------------------------
    # 2. Create responsive columns
    # --------------------------------------------------

    col1, col2 = st.columns([3, 2], gap="medium")

    # --------------------------------------------------
    # 3. Categorization Success Card
    # --------------------------------------------------

    with col1:

        cat_html = f"""
        <div style="
            background: #FFFFFF;
            border: 1px solid #E7EAE5;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 3px 12px rgba(0,0,0,0.04);
            height: 100%;
        ">

            <div style="
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 12px;
                margin-bottom: 8px;
            ">
                <span style="
                    font-size: 15px;
                    font-weight: 700;
                    color: #1F2933;
                ">
                    Categorization Success
                </span>

                <span style="
                    font-size: 25px;
                    font-weight: 800;
                    color: #246B45;
                ">
                    {pct_cat:.1f}%
                </span>
            </div>

            <div style="
                height: 9px;
                background: #E9EFEA;
                border-radius: 20px;
                overflow: hidden;
                margin: 16px 0 20px 0;
            ">
                <div style="
                    height: 100%;
                    width: {cat_width:.1f}%;
                    background: linear-gradient(90deg, #246B45, #55A879);
                    border-radius: 20px;
                "></div>
            </div>

            <div style="
                display: flex;
                gap: 9px;
                flex-wrap: wrap;
            ">

                <span style="
                    background: #E8F5EC;
                    color: #246B45;
                    padding: 7px 11px;
                    border-radius: 8px;
                    font-size: 12px;
                ">
                    ✓ Categorized: <strong>{categorized:,}</strong>
                </span>

                <span style="
                    background: #FFF4E5;
                    color: #B7791F;
                    padding: 7px 11px;
                    border-radius: 8px;
                    font-size: 12px;
                ">
                    ⚠ Needs Review: <strong>{needs_review:,}</strong>
                </span>

                <span style="
                    background: #F1F3F5;
                    color: #59636E;
                    padding: 7px 11px;
                    border-radius: 8px;
                    font-size: 12px;
                ">
                    ❓ Unclassified: <strong>{unclassified:,}</strong>
                </span>

            </div>

            <div style="
                margin-top: 16px;
                font-size: 12px;
                color: #78847D;
            ">
                Total transactions analyzed: {total:,}
            </div>

        </div>
        """

        st.html(textwrap.dedent(cat_html).strip())

    # --------------------------------------------------
    # 4. Emission Factor Coverage Card
    # --------------------------------------------------

    with col2:

        emission_html = f"""
        <div style="
            background: #FFFFFF;
            border: 1px solid #E7EAE5;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 3px 12px rgba(0,0,0,0.04);
            height: 100%;
        ">

            <div style="
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 12px;
                margin-bottom: 8px;
            ">
                <span style="
                    font-size: 15px;
                    font-weight: 700;
                    color: #1F2933;
                ">
                    Emission Factor Coverage
                </span>

                <span style="
                    font-size: 25px;
                    font-weight: 800;
                    color: #246B45;
                ">
                    {pct_est:.1f}%
                </span>
            </div>

            <div style="
                height: 9px;
                background: #E9EFEA;
                border-radius: 20px;
                overflow: hidden;
                margin: 16px 0 20px 0;
            ">
                <div style="
                    height: 100%;
                    width: {emission_width:.1f}%;
                    background: linear-gradient(90deg, #3B82F6, #60A5FA);
                    border-radius: 20px;
                "></div>
            </div>

            <div style="
                font-size: 13px;
                color: #59636E;
                line-height: 1.7;
            ">
                <strong style="color: #246B45;">
                    {est_count:,}
                </strong>
                of
                <strong>{total:,}</strong>
                transactions have estimated emissions using supported
                emission factors.
            </div>

            <div style="
                margin-top: 16px;
                padding: 10px 12px;
                background: #F3F7FC;
                border-radius: 9px;
                font-size: 11px;
                color: #53677E;
            ">
                India-specific methodology:
                CEA, HCES, BEE and MoEFCC.
            </div>

        </div>
        """

        st.html(textwrap.dedent(emission_html).strip())