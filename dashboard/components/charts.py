"""
dashboard/components/charts.py
Plotly charts designed with startup-grade aesthetics:
- Monthly trend area chart with smooth spline and subtle green gradient
- Category emissions horizontal bar chart with custom tooltips
- Clean donut chart with center annotation and grouped "Other" slices
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# Palette constants
PRIMARY_GREEN = "#246B45"
DARK_GREEN = "#174C35"
SOFT_MINT = "#E7F3EB"
MUTED_TEXT = "#78847D"
DARK_TEXT = "#1F2933"
GRID_COLOR = "#F0F2EE"
BORDER_COLOR = "#E7EAE5"

CHART_PALETTE = [
    "#246B45", "#2D7A50", "#3E9265", "#52B788", "#74C69D",
    "#95D5B2", "#B7E4C7", "#E9A45B", "#DDA15E", "#A3B18A",
    "#8FA38F", "#C4D4C8"
]


def render_monthly_trend_chart(monthly_df: pd.DataFrame) -> None:
    """Render interactive line/area chart showing CO2e emissions over time."""
    if monthly_df.empty:
        st.info("No monthly emissions data available for the selected period.", icon="ℹ️")
        return

    col_x = "month_label" if "month_label" in monthly_df.columns else "month_str"

    # If single month, render a clean vertical bar chart instead of a single dot
    if len(monthly_df) == 1:
        row = monthly_df.iloc[0]
        fig = go.Figure(go.Bar(
            x=[str(row[col_x])],
            y=[row["co2e_kg"]],
            marker_color=PRIMARY_GREEN,
            marker_line_width=0,
            width=0.35,
            hovertemplate="<b>%{x}</b><br>Emissions: %{y:.2f} kg CO₂e<extra></extra>",
        ))
        fig.update_layout(
            height=320,
            margin=dict(l=20, r=20, t=20, b=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(
                title="Emissions (kg CO₂e)",
                title_font=dict(size=12, color=MUTED_TEXT),
                gridcolor=GRID_COLOR,
                zerolinecolor=BORDER_COLOR,
                tickfont=dict(size=11, color=MUTED_TEXT),
            ),
            xaxis=dict(
                tickfont=dict(size=12, color=DARK_TEXT),
                gridcolor="rgba(0,0,0,0)",
            ),
            font=dict(family="Plus Jakarta Sans, Inter, sans-serif"),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        return

    # Multi-month trend: Smooth spline area chart
    fig = go.Figure()

    # Subtle area fill
    fig.add_trace(go.Scatter(
        x=monthly_df[col_x],
        y=monthly_df["co2e_kg"],
        mode="lines+markers",
        name="Emissions",
        line=dict(color=PRIMARY_GREEN, width=3, shape="spline", smoothing=1.1),
        marker=dict(
            size=7,
            color=PRIMARY_GREEN,
            line=dict(color="#FFFFFF", width=2),
        ),
        fill="tozeroy",
        fillcolor="rgba(36, 107, 69, 0.08)",
        hovertemplate="<b>%{x}</b><br>Footprint: <b>%{y:,.1f} kg CO₂e</b><extra></extra>",
    ))

    fig.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        hoverlabel=dict(
            bgcolor=DARK_TEXT,
            font_size=12,
            font_family="Plus Jakarta Sans, Inter, sans-serif",
            font_color="#FFFFFF",
        ),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            tickfont=dict(size=12, color=MUTED_TEXT),
            linecolor=BORDER_COLOR,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=GRID_COLOR,
            zeroline=True,
            zerolinecolor=BORDER_COLOR,
            tickfont=dict(size=11, color=MUTED_TEXT),
            ticksuffix=" kg",
        ),
        font=dict(family="Plus Jakarta Sans, Inter, sans-serif"),
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_category_bar_chart(cat_df: pd.DataFrame) -> None:
    """Render horizontal bar chart for category emission breakdown."""
    if cat_df.empty:
        st.info("No category emission data available.", icon="ℹ️")
        return

    # Limit to top 10 categories for visual clarity
    df_plot = cat_df.head(10).iloc[::-1]  # reverse so highest is at top
    col_y = "category_friendly" if "category_friendly" in df_plot.columns else "category"

    fig = go.Figure(go.Bar(
        x=df_plot["co2e_kg"],
        y=df_plot[col_y],
        orientation="h",
        marker=dict(
            color=df_plot["co2e_kg"],
            colorscale=[
                [0.0, "#A3D9B8"],
                [0.5, "#40916C"],
                [1.0, "#174C35"],
            ],
            line_width=0,
        ),
        text=[f"{v:,.1f} kg" for v in df_plot["co2e_kg"]],
        textposition="auto",
        textfont=dict(family="Plus Jakarta Sans, Inter", size=11, color="#FFFFFF"),
        hovertemplate="<b>%{y}</b><br>Emissions: %{x:,.2f} kg CO₂e<extra></extra>",
    ))

    fig.update_layout(
        height=340,
        margin=dict(l=10, r=20, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        hoverlabel=dict(
            bgcolor=DARK_TEXT,
            font_size=12,
            font_family="Plus Jakarta Sans, Inter, sans-serif",
            font_color="#FFFFFF",
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor=GRID_COLOR,
            zeroline=False,
            tickfont=dict(size=11, color=MUTED_TEXT),
            title="Estimated CO₂e (kg)",
            title_font=dict(size=12, color=MUTED_TEXT),
        ),
        yaxis=dict(
            showgrid=False,
            tickfont=dict(size=12, color=DARK_TEXT),
        ),
        font=dict(family="Plus Jakarta Sans, Inter, sans-serif"),
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_donut_chart(donut_df: pd.DataFrame, total_co2e_kg: float) -> None:
    """Render clean interactive donut chart with center annotation."""
    if donut_df.empty or total_co2e_kg <= 0:
        st.info("No emission distribution data to display.", icon="ℹ️")
        return

    # Format center label
    if total_co2e_kg >= 1000:
        center_val = f"{total_co2e_kg / 1000.0:.2f}"
        center_unit = "t CO₂e"
    else:
        center_val = f"{total_co2e_kg:,.0f}"
        center_unit = "kg CO₂e"

    col_labels = "category_friendly" if "category_friendly" in donut_df.columns else "category"

    fig = go.Figure(go.Pie(
        labels=donut_df[col_labels],
        values=donut_df["co2e_kg"],
        hole=0.68,
        marker=dict(
            colors=CHART_PALETTE[:len(donut_df)],
            line=dict(color="#FFFFFF", width=2),
        ),
        textinfo="percent",
        textfont=dict(family="Plus Jakarta Sans, Inter", size=11),
        hovertemplate="<b>%{label}</b><br>%{value:,.1f} kg CO₂e (%{percent})<extra></extra>",
        sort=False,
    ))

    # Center label annotation
    fig.update_layout(
        height=340,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.02,
            font=dict(size=11, color=MUTED_TEXT),
        ),
        hoverlabel=dict(
            bgcolor=DARK_TEXT,
            font_size=12,
            font_color="#FFFFFF",
        ),
        annotations=[
            dict(
                text=f"<b style='font-size:20px; color:#1F2933;'>{center_val}</b><br><span style='font-size:12px; color:#78847D;'>{center_unit}</span>",
                x=0.5,
                y=0.5,
                font=dict(family="Plus Jakarta Sans, Inter", size=13),
                showarrow=False,
            )
        ],
        font=dict(family="Plus Jakarta Sans, Inter, sans-serif"),
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

