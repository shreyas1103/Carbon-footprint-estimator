"""
dashboard/utils/dashboard_utils.py
All data loading, aggregation, and KPI calculation helpers for the
Milestone 3.2 dashboard.  No Streamlit UI code lives here — this module
is intentionally testable with plain pytest.

Column name contract (matches models.Transaction + Upload page output):
  date / transaction_date → datetime
  cleaned_description     → str
  amount                  → float
  category                → str | None
  category_status         → "categorized" | "needs_review" | "unclassified"
  emissions_status        → "estimated" | "unsupported" | "excluded_*"
  estimated_co2e_kg       → float | None
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SMALL_CATEGORY_THRESHOLD = 0.03   # categories < 3% total are grouped into "Other"
MAX_DB_ROWS = 2000                 # safety ceiling for DB queries
ESTIMATED_STATUS = "estimated"


# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------

def load_dashboard_data(session_df: Optional[pd.DataFrame] = None) -> Optional[pd.DataFrame]:
    """
    Return the best available DataFrame for the dashboard.
    Priority: session state → database (latest batch).
    Returns None if no data is available.
    """
    if session_df is not None and not session_df.empty:
        return _normalise_columns(session_df.copy())

    return _load_from_db()


def _load_from_db() -> Optional[pd.DataFrame]:
    """Query latest transactions from database, returning None on any failure."""
    try:
        from database.connection import get_session
        from database.models import Transaction
        session = get_session()
        if session is None:
            return None
        rows = (
            session.query(Transaction)
            .order_by(Transaction.transaction_date.desc())
            .limit(MAX_DB_ROWS)
            .all()
        )
        session.close()
        if not rows:
            return None

        records = []
        for r in rows:
            records.append({
                "date": r.transaction_date,
                "cleaned_description": r.cleaned_description or "",
                "amount": float(r.amount) if r.amount is not None else 0.0,
                "currency": r.currency or "INR",
                "category": r.category,
                "subcategory": r.subcategory,
                "category_status": r.category_status,
                "emissions_status": r.emissions_status,
                "estimated_co2e_kg": (
                    float(r.estimated_co2e_kg) if r.estimated_co2e_kg is not None else None
                ),
                "emissions_confidence": r.emissions_confidence,
                "factor_id": r.factor_id,
                "factor_source": r.factor_source,
                "estimation_notes": r.estimation_notes,
                "batch_id": r.batch_id,
            })
        return _normalise_columns(pd.DataFrame(records))
    except Exception as exc:
        logger.warning("DB load failed: %s", str(exc)[:200])
        return None


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure critical columns exist and have correct types.
    Handles both 'date' and 'transaction_date' column names.
    """
    # Unify date column
    if "transaction_date" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"transaction_date": "date"})

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Ensure numeric
    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)

    # estimated_co2e_kg → float, keep NaN for None
    if "estimated_co2e_kg" in df.columns:
        df["estimated_co2e_kg"] = pd.to_numeric(df["estimated_co2e_kg"], errors="coerce")

    # Fill string columns
    for col in ("category_status", "emissions_status", "category"):
        if col not in df.columns:
            df[col] = None

    return df


# ---------------------------------------------------------------------------
# Period Filter
# ---------------------------------------------------------------------------

def filter_by_period(
    df: pd.DataFrame,
    start_date: Optional[Any] = None,
    end_date: Optional[Any] = None,
    start: Optional[Any] = None,
    end: Optional[Any] = None,
) -> pd.DataFrame:
    """
    Filter DataFrame rows to the [start_date, end_date] date window.
    Supports both keyword and positional arguments:
      filter_by_period(df, start_date, end_date)
      filter_by_period(df, start_date=..., end_date=...)
      filter_by_period(df, start=..., end=...)  # backward compatibility
    Silently handles missing/NaT dates and string/date/datetime types.
    """
    s = start_date if start_date is not None else start
    e = end_date if end_date is not None else end

    if "date" not in df.columns or df.empty:
        return df

    dates = pd.to_datetime(df["date"], errors="coerce")
    valid_dates = dates.notna()

    mask = pd.Series([True] * len(df), index=df.index)
    if s is not None and not (isinstance(s, float) and pd.isna(s)):
        try:
            ts_start = pd.Timestamp(s)
            mask &= (valid_dates & (dates >= ts_start))
        except Exception:
            pass
    if e is not None and not (isinstance(e, float) and pd.isna(e)):
        try:
            ts_end = pd.Timestamp(e)
            mask &= (valid_dates & (dates <= ts_end))
        except Exception:
            pass
    return df[mask]


def get_date_range(df: pd.DataFrame):
    """Return (min_date, max_date) or (None, None) if unavailable."""
    if "date" not in df.columns or df["date"].isna().all():
        return None, None
    valid = df["date"].dropna()
    return valid.min().to_pydatetime(), valid.max().to_pydatetime()


# ---------------------------------------------------------------------------
# Estimated emissions subset (the only subset used for CO2e charts)
# ---------------------------------------------------------------------------

def get_estimated(df: pd.DataFrame) -> pd.DataFrame:
    """Return rows where emissions_status == 'estimated' AND estimated_co2e_kg > 0."""
    if "emissions_status" not in df.columns or "estimated_co2e_kg" not in df.columns:
        return pd.DataFrame(columns=df.columns)
    mask = (
        (df["emissions_status"] == ESTIMATED_STATUS)
        & df["estimated_co2e_kg"].notna()
        & (df["estimated_co2e_kg"] > 0)
    )
    return df[mask].copy()


# ---------------------------------------------------------------------------
# KPI Calculations
# ---------------------------------------------------------------------------

def compute_kpis(df: pd.DataFrame) -> dict:
    """
    Compute standardized KPI metrics dictionary across all dashboard pages.

    Standardized return keys:
      total_co2e_kg: float
      average_monthly_co2e: float | None
      top_category: str | None
      top_category_co2e_kg: float | None
      top_category_pct: float
      total_transactions: int
      estimated_transactions: int
      categorized_transactions: int
      unclassified_transactions: int
      categorization_rate: float

    Backward compatibility aliases:
      avg_monthly_co2e_kg -> average_monthly_co2e
      categorized_count -> categorized_transactions
      estimated_count -> estimated_transactions
    """
    total_transactions = len(df)

    # Categorization counts
    if "category_status" in df.columns:
        categorized_transactions = int((df["category_status"] == "categorized").sum())
        unclassified_transactions = int((df["category_status"] == "unclassified").sum())
    elif "category" in df.columns:
        valid_cat = df["category"].dropna().astype(str).str.strip()
        categorized_transactions = int((valid_cat != "").sum())
        unclassified_transactions = total_transactions - categorized_transactions
    else:
        categorized_transactions = 0
        unclassified_transactions = total_transactions

    categorization_rate = (
        round((categorized_transactions / total_transactions) * 100.0, 2)
        if total_transactions > 0
        else 0.0
    )

    # Estimated transactions (only valid, non-null CO2e with emissions_status == "estimated")
    estimated_df = get_estimated(df)
    estimated_transactions = len(estimated_df)

    # Total CO2e (summing only estimated subset, NaN excluded)
    total_co2e = (
        round(float(estimated_df["estimated_co2e_kg"].dropna().sum()), 4)
        if not estimated_df.empty
        else 0.0
    )

    # Average monthly CO2e — divide by number of distinct months WITH data
    avg_monthly = None
    if not estimated_df.empty and "date" in estimated_df.columns:
        monthly = _monthly_totals(estimated_df)
        if not monthly.empty:
            avg_monthly = round(float(monthly["co2e_kg"].mean()), 4)

    # Top category & percentage contribution
    top_category, top_cat_co2e = None, None
    top_cat_pct = 0.0
    if not estimated_df.empty and "category" in estimated_df.columns:
        cat_totals = (
            estimated_df.groupby("category")["estimated_co2e_kg"]
            .sum()
            .sort_values(ascending=False)
        )
        if not cat_totals.empty:
            top_category = str(cat_totals.index[0])
            top_cat_co2e = round(float(cat_totals.iloc[0]), 4)
            if total_co2e > 0.0:
                top_cat_pct = round((top_cat_co2e / total_co2e) * 100.0, 2)

    return {
        # Standardized keys
        "total_co2e_kg": total_co2e,
        "average_monthly_co2e": avg_monthly,
        "top_category": top_category,
        "top_category_co2e_kg": top_cat_co2e,
        "top_category_pct": top_cat_pct,
        "total_transactions": total_transactions,
        "estimated_transactions": estimated_transactions,
        "categorized_transactions": categorized_transactions,
        "unclassified_transactions": unclassified_transactions,
        "categorization_rate": categorization_rate,
        # Backward compatibility aliases
        "avg_monthly_co2e_kg": avg_monthly,
        "categorized_count": categorized_transactions,
        "estimated_count": estimated_transactions,
    }


# ---------------------------------------------------------------------------
# Monthly Aggregation
# ---------------------------------------------------------------------------

def _monthly_totals(estimated_df: pd.DataFrame) -> pd.DataFrame:
    """Internal: aggregate estimated CO2e by calendar month."""
    if estimated_df.empty or "date" not in estimated_df.columns:
        return pd.DataFrame(columns=["month_str", "co2e_kg"])
    tmp = estimated_df.copy()
    tmp = tmp.dropna(subset=["date"])
    if tmp.empty:
        return pd.DataFrame(columns=["month_str", "co2e_kg"])
    if not pd.api.types.is_datetime64_any_dtype(tmp["date"]):
        tmp["date"] = pd.to_datetime(tmp["date"], errors="coerce")
        tmp = tmp.dropna(subset=["date"])
        if tmp.empty:
            return pd.DataFrame(columns=["month_str", "co2e_kg"])
    tmp["month_period"] = tmp["date"].dt.to_period("M")
    monthly = (
        tmp.groupby("month_period")["estimated_co2e_kg"]
        .sum()
        .reset_index()
        .rename(columns={"month_period": "month_str", "estimated_co2e_kg": "co2e_kg"})
    )
    monthly["month_str"] = monthly["month_str"].astype(str)
    monthly = monthly.sort_values("month_str")
    try:
        monthly["month_label"] = pd.to_datetime(monthly["month_str"] + "-01").dt.strftime("%b %Y")
    except Exception:
        monthly["month_label"] = monthly["month_str"]
    return monthly


def get_monthly_trend(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return monthly CO2e aggregation for the line chart.
    Columns: month_str (e.g. "2024-01"), month_label (e.g. "Jan 2024"), co2e_kg.
    Only contains months with estimated emissions.
    """
    return _monthly_totals(get_estimated(df))


# ---------------------------------------------------------------------------
# Category Aggregation
# ---------------------------------------------------------------------------

def get_category_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return per-category estimated CO2e (horizontal bar chart data).
    Columns: category, category_friendly, co2e_kg — sorted descending.
    """
    estimated = get_estimated(df)
    if estimated.empty or "category" not in estimated.columns:
        return pd.DataFrame(columns=["category", "category_friendly", "co2e_kg"])
    cat = (
        estimated.groupby("category")["estimated_co2e_kg"]
        .sum()
        .reset_index()
        .rename(columns={"estimated_co2e_kg": "co2e_kg"})
        .sort_values("co2e_kg", ascending=False)
    )
    cat = cat[cat["co2e_kg"] > 0].copy()
    cat["category_friendly"] = cat["category"].apply(lambda c: _friendly_category(str(c)))
    return cat


def get_donut_data(cat_df: pd.DataFrame, threshold: float = SMALL_CATEGORY_THRESHOLD) -> pd.DataFrame:
    """
    Prepare donut chart data.  Categories below `threshold` fraction of total
    are grouped into 'Other' for visual clarity.  The underlying data is NOT
    altered.  Returns DataFrame with columns: category, category_friendly, co2e_kg, pct.
    """
    if cat_df.empty:
        return pd.DataFrame(columns=["category", "category_friendly", "co2e_kg", "pct"])
    total = cat_df["co2e_kg"].sum()
    if total <= 0:
        return pd.DataFrame(columns=["category", "category_friendly", "co2e_kg", "pct"])
    df2 = cat_df.copy()
    df2["pct"] = df2["co2e_kg"] / total
    main = df2[df2["pct"] >= threshold].copy()
    small = df2[df2["pct"] < threshold]
    if not small.empty:
        other_row = pd.DataFrame([{
            "category": "Other",
            "category_friendly": "Other",
            "co2e_kg": small["co2e_kg"].sum(),
            "pct": small["pct"].sum(),
        }])
        main = pd.concat([main, other_row], ignore_index=True)
    if "category_friendly" not in main.columns:
        main["category_friendly"] = main["category"].apply(
            lambda c: "Other" if str(c) == "Other" else _friendly_category(str(c))
        )
    main = main.sort_values("co2e_kg", ascending=False)
    return main


# ---------------------------------------------------------------------------
# Categorization Quality
# ---------------------------------------------------------------------------

def get_categorization_stats(df: pd.DataFrame) -> dict:
    """
    Return categorization quality summary.
    Keys: total, categorized, needs_review, unclassified, pct_categorized.
    """
    total = len(df)
    if total == 0:
        return {
            "total": 0, "categorized": 0,
            "needs_review": 0, "unclassified": 0,
            "estimated": 0, "pct_categorized": 0.0,
        }
    cs = df.get("category_status", pd.Series(dtype=str))
    categorized = int((cs == "categorized").sum())
    needs_review = int((cs == "needs_review").sum())
    unclassified = int((cs == "unclassified").sum())
    estimated = int(
        (df.get("emissions_status", pd.Series(dtype=str)) == "estimated").sum()
    )
    pct = (categorized / total * 100) if total > 0 else 0.0
    return {
        "total": total,
        "categorized": categorized,
        "needs_review": needs_review,
        "unclassified": unclassified,
        "estimated": estimated,
        "pct_categorized": pct,
    }


# ---------------------------------------------------------------------------
# Sustainability Highlights
# ---------------------------------------------------------------------------

def get_sustainability_highlights(df: pd.DataFrame, cat_df: Optional[pd.DataFrame] = None) -> list[dict]:
    """
    Generate 2–3 data-driven text observations.
    Each item is {"icon": str, "title": str, "text": str}.
    Returns empty list if data is insufficient.
    If cat_df is omitted, it is computed automatically from df.
    """
    highlights = []
    estimated = get_estimated(df)
    if estimated.empty:
        return []

    if cat_df is None:
        cat_df = get_category_breakdown(df)

    total_co2e = float(estimated["estimated_co2e_kg"].sum())

    # Highlight 1: Top category
    if not cat_df.empty:
        top = cat_df.iloc[0]
        pct = top["co2e_kg"] / total_co2e * 100 if total_co2e > 0 else 0
        label = _friendly_category(str(top["category"]))
        highlights.append({
            "icon": "🏆",
            "title": "Primary Driver",
            "text": f"Your highest-emission category is **{label}**, contributing **{pct:.1f}%** of your estimated footprint.",
        })

    # Highlight 2: Month-over-month change (requires ≥ 2 months)
    monthly = _monthly_totals(estimated)
    if len(monthly) >= 2:
        current = float(monthly["co2e_kg"].iloc[-1])
        previous = float(monthly["co2e_kg"].iloc[-2])
        if previous > 0:
            change_pct = (current - previous) / previous * 100
            if change_pct > 5:
                highlights.append({
                    "icon": "📈",
                    "title": "Monthly Trajectory",
                    "text": f"Your emissions **increased by {change_pct:.1f}%** compared to the previous month.",
                })
            elif change_pct < -5:
                highlights.append({
                    "icon": "📉",
                    "title": "Monthly Trajectory",
                    "text": f"Your emissions **decreased by {abs(change_pct):.1f}%** compared to the previous month — great progress!",
                })
            else:
                highlights.append({
                    "icon": "➡️",
                    "title": "Monthly Trajectory",
                    "text": "Your emissions were roughly **stable** compared to the previous month.",
                })
    elif len(monthly) == 1:
        highlights.append({
            "icon": "📅",
            "title": "Single Month Profile",
            "text": "Month-over-month comparison needs more transaction history. Upload next month's statement to see trends.",
        })

    # Highlight 3: Share of top-2 categories
    if len(cat_df) >= 2 and total_co2e > 0:
        top2_pct = cat_df.head(2)["co2e_kg"].sum() / total_co2e * 100
        highlights.append({
            "icon": "🔍",
            "title": "Emission Concentration",
            "text": f"Your top 2 emission categories account for **{top2_pct:.1f}%** of your total estimated footprint.",
        })

    return highlights[:3]  # cap at 3


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_co2e(value_kg: float) -> str:
    """Format CO2e value with appropriate unit (kg or tonnes)."""
    if value_kg is None:
        return "—"
    if value_kg >= 1000:
        return f"{value_kg / 1000:.2f} t CO₂e"
    return f"{value_kg:.2f} kg CO₂e"


def _friendly_category(category: Optional[str]) -> str:
    """Convert 'food.basic_grocery' → 'Food — Basic Grocery'."""
    if not category:
        return "Uncategorized"
    parts = str(category).split(".")
    return " — ".join(p.replace("_", " ").title() for p in parts)


friendly_category = _friendly_category


# Category color palette (forest greens + muted oranges)
CATEGORY_COLORS = [
    "#2D6A4F", "#40916C", "#52B788", "#74C69D", "#95D5B2",
    "#B7E4C7", "#D8F3DC", "#E9C46A", "#F4A261", "#E76F51",
    "#A8DADC", "#457B9D", "#1D3557", "#6A994E", "#A7C957",
]
