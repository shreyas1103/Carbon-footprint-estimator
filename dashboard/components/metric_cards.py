"""
dashboard/components/metric_cards.py
Custom-designed KPI cards matching Linear/Stripe climate-tech SaaS aesthetics.
"""
from __future__ import annotations

from typing import Any, Dict
import streamlit as st
from dashboard_utils import format_co2e, friendly_category
import textwrap

def render_kpi_cards(kpis: Dict[str, Any]) -> None:
    """
    Render 4 elevated KPI cards with SVG icons, large readable numbers,
    clean units, and supporting metadata.
    """
    total_co2e = kpis.get("total_co2e_kg", 0.0) or 0.0
    avg_monthly = kpis.get("average_monthly_co2e") or kpis.get("avg_monthly_co2e_kg") or 0.0
    top_cat = kpis.get("top_category")
    top_cat_pct = kpis.get("top_category_pct", 0.0) or 0.0
    total_tx = kpis.get("total_transactions", 0) or 0
    est_tx = kpis.get("estimated_transactions") or kpis.get("estimated_count") or 0

    # 1. Total Footprint display
    if total_co2e >= 1000.0:
        val_total = f"{total_co2e / 1000.0:.2f}"
        unit_total = "t CO₂e"
    elif total_co2e > 0.0:
        val_total = f"{total_co2e:,.1f}"
        unit_total = "kg CO₂e"
    else:
        val_total = "0.0"
        unit_total = "kg CO₂e"

    # 2. Monthly Average display
    if avg_monthly >= 1000.0:
        val_avg = f"{avg_monthly / 1000.0:.2f}"
        unit_avg = "t / mo"
    elif avg_monthly > 0.0:
        val_avg = f"{avg_monthly:,.1f}"
        unit_avg = "kg / mo"
    else:
        val_avg = "—"
        unit_avg = ""

    # 3. Top Category display
    if top_cat:
        val_cat = friendly_category(top_cat)
        sub_cat = f"{top_cat_pct:.1f}% of total emissions"
    else:
        val_cat = "None"
        sub_cat = "No estimated transactions"

    # 4. Transactions display
    val_tx = f"{total_tx:,}"
    pct_est = (est_tx / total_tx * 100.0) if total_tx > 0 else 0.0
    sub_tx = f"{est_tx:,} estimated ({pct_est:.0f}%)"

    card_html = f"""
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px;">
        <!-- Card 1: Total Footprint -->
        <div class="kpi-card">
            <div class="kpi-top">
                <span class="kpi-title">Total Footprint</span>
                <div class="kpi-icon-wrapper">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/>
                        <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>
                    </svg>
                </div>
            </div>
            <div class="kpi-value-row">
                <span class="kpi-value">{val_total}</span>
                <span class="kpi-unit">{unit_total}</span>
            </div>
            <div class="kpi-subtext">Estimated environmental impact of your spending</div>
        </div>

        <!-- Card 2: Monthly Average -->
        <div class="kpi-card">
            <div class="kpi-top">
                <span class="kpi-title">Monthly Average</span>
                <div class="kpi-icon-wrapper" style="background: #FDF3E7; color: #E9A45B;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
                    </svg>
                </div>
            </div>
            <div class="kpi-value-row">
                <span class="kpi-value">{val_avg}</span>
                <span class="kpi-unit">{unit_avg}</span>
            </div>
            <div class="kpi-subtext">Calculated across active spending months</div>
        </div>

        <!-- Card 3: Top Category -->
        <div class="kpi-card">
            <div class="kpi-top">
                <span class="kpi-title">Top Contributor</span>
                <div class="kpi-icon-wrapper" style="background: #F0F4FF; color: #3B82F6;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/>
                        <polyline points="16 7 22 7 22 13"/>
                    </svg>
                </div>
            </div>
            <div class="kpi-value-row">
                <span class="kpi-value" style="font-size: 22px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%;" title="{val_cat}">
                    {val_cat}
                </span>
            </div>
            <div class="kpi-subtext">{sub_cat}</div>
        </div>

        <!-- Card 4: Transactions Analyzed -->
        <div class="kpi-card">
            <div class="kpi-top">
                <span class="kpi-title">Transactions</span>
                <div class="kpi-icon-wrapper" style="background: #F4F5F7; color: #4B5563;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/>
                        <path d="M16 8h-6"/>
                        <path d="M16 12h-6"/>
                        <path d="M16 16h-6"/>
                    </svg>
                </div>
            </div>
            <div class="kpi-value-row">
                <span class="kpi-value">{val_tx}</span>
                <span class="kpi-unit">records</span>
            </div>
            <div class="kpi-subtext">{sub_tx}</div>
        </div>
    </div>
    """

    st.html(textwrap.dedent(card_html).strip())
