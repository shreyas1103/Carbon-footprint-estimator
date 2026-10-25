"""
pipeline/emissions.py
Pure emissions calculation engine.
No database calls — receives a factor registry dict as input.
Implements Route A (spend-based) and Route B (activity-based) hybrid methodology.

Rules:
- Never double-apply a factor.
- Never use UK/US factors for Indian transactions.
- Never store 0 as a substitute for unknown emissions.
- Only INR amounts get INR factors.
- Refunds/transfers/cash-withdrawals are explicitly excluded.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from pipeline.categorization.categories import EXCLUDED_CATEGORIES, SUPPORTED_SPEND_CATEGORIES

# ---------------------------------------------------------------------------
# Factor registry: loaded from database or seed data.
# Schema: {factor_id: {category, factor_type, value (Decimal), unit, confidence, ...}}
# ---------------------------------------------------------------------------

# In-memory fallback factor registry (matches database seed values exactly)
_FALLBACK_REGISTRY: dict[str, dict] = {
    "IN-HCES-RICE-AND-RICE-PRODUCTS": {
        "category": "food.rice", "factor_type": "spend_based",
        "value": Decimal("0.07048581883787187"), "unit": "kgCO2e/INR",
        "source_name": "HCES India", "confidence": "medium",
    },
    "IN-HCES-WHEAT-AND-WHEAT-PRODUCTS": {
        "category": "food.wheat_products", "factor_type": "spend_based",
        "value": Decimal("0.01210098015315142"), "unit": "kgCO2e/INR",
        "source_name": "HCES India", "confidence": "medium",
    },
    "IN-HCES-COARSE-GRAINS": {
        "category": "food.coarse_grains", "factor_type": "spend_based",
        "value": Decimal("0.005561874060700431"), "unit": "kgCO2e/INR",
        "source_name": "HCES India", "confidence": "medium",
    },
    "IN-HCES-PULSES-AND-PULSE-PRODUCTS": {
        "category": "food.pulses", "factor_type": "spend_based",
        "value": Decimal("0.004027566759451551"), "unit": "kgCO2e/INR",
        "source_name": "HCES India", "confidence": "medium",
    },
    "IN-HCES-SUGAR-AND-SWEETENERS": {
        "category": "food.sugar_sweeteners", "factor_type": "spend_based",
        "value": Decimal("0.003699943926194361"), "unit": "kgCO2e/INR",
        "source_name": "HCES India", "confidence": "medium",
    },
    "IN-HCES-MILK-AND-DAIRY": {
        "category": "food.milk_dairy", "factor_type": "spend_based",
        "value": Decimal("0.1255438890163547"), "unit": "kgCO2e/INR",
        "source_name": "HCES India", "confidence": "medium",
    },
    "IN-HCES-MEAT-FISH-(EXCLUDING-EGGS)": {
        "category": "food.meat_fish", "factor_type": "spend_based",
        "value": Decimal("0.06844688332133109"), "unit": "kgCO2e/INR",
        "source_name": "HCES India", "confidence": "medium",
    },
    "IN-HCES-EDIBLE-OILS": {
        "category": "food.edible_oils", "factor_type": "spend_based",
        "value": Decimal("0.01840805461327834"), "unit": "kgCO2e/INR",
        "source_name": "HCES India", "confidence": "medium",
    },
    "IN-HCES-VEGETABLES-(KG-BASED-ITEMS)": {
        "category": "food.vegetables", "factor_type": "spend_based",
        "value": Decimal("0.00124394517499368"), "unit": "kgCO2e/INR",
        "source_name": "HCES India", "confidence": "medium",
    },
    "IN-HCES-FRESH-FRUIT-(KG-BASED-ITEMS)": {
        "category": "food.fresh_fruit", "factor_type": "spend_based",
        "value": Decimal("0.0006504095558087095"), "unit": "kgCO2e/INR",
        "source_name": "HCES India", "confidence": "medium",
    },
    "IN-HCES-BASIC-GROCERY": {
        "category": "food.basic_grocery", "factor_type": "spend_based",
        "value": Decimal("0.04246780031372872"), "unit": "kgCO2e/INR",
        "source_name": "HCES India", "confidence": "medium",
    },
    "IN-CEA-ELECTRICITY-SPEND": {
        "category": "utilities.electricity", "factor_type": "spend_based",
        "value": Decimal("0.1325303878714435"), "unit": "kgCO2e/INR",
        "source_name": "CEA V21.0 (derived)", "confidence": "high",
    },
    "IN-MOEFCC-LPG-SPEND": {
        "category": "utilities.lpg", "factor_type": "spend_based",
        "value": Decimal("0.04715845926839721"), "unit": "kgCO2e/INR",
        "source_name": "MoEFCC LCL (derived)", "confidence": "high",
    },
    "IN-BEE-PETROL-SPEND": {
        "category": "transport_fuel.petrol", "factor_type": "spend_based",
        "value": Decimal("0.02209753236010448"), "unit": "kgCO2e/INR",
        "source_name": "BEE India (derived)", "confidence": "high",
    },
    "IN-BEE-DIESEL-SPEND": {
        "category": "transport_fuel.diesel", "factor_type": "spend_based",
        "value": Decimal("0.02853545300348392"), "unit": "kgCO2e/INR",
        "source_name": "BEE India (derived)", "confidence": "high",
    },
    "IN-HCES-VEHICLE-FUEL-COMBINED-SPEND": {
        "category": "transport_fuel.unknown", "factor_type": "spend_based",
        "value": Decimal("0.02470813417651744"), "unit": "kgCO2e/INR",
        "source_name": "HCES India (blended)", "confidence": "high",
    },
    # Physical (Route B) factors
    "IN-ELEC-CEA-V21-2024-25": {
        "category": "utilities.electricity", "factor_type": "activity_based",
        "value": Decimal("0.7117"), "unit": "kgCO2/kWh",
        "source_name": "CEA V21.0", "confidence": "high",
    },
    "IN-LPG-MOEF-LCL": {
        "category": "utilities.lpg", "factor_type": "activity_based",
        "value": Decimal("3.13"), "unit": "kgCO2/kg",
        "source_name": "MoEFCC LCL", "confidence": "high",
    },
    "IN-PETROL-ROAD-DPIIT": {
        "category": "transport_fuel.petrol", "factor_type": "activity_based",
        "value": Decimal("2.27"), "unit": "kgCO2/L",
        "source_name": "DPIIT/WRI India", "confidence": "medium",
    },
    "IN-DIESEL-ROAD-DPIIT": {
        "category": "transport_fuel.diesel", "factor_type": "activity_based",
        "value": Decimal("2.64"), "unit": "kgCO2/L",
        "source_name": "DPIIT/WRI India", "confidence": "medium",
    },
}

# Category → preferred spend-based factor ID
_CATEGORY_SPEND_FACTOR: dict[str, str] = {
    "food.rice": "IN-HCES-RICE-AND-RICE-PRODUCTS",
    "food.wheat_products": "IN-HCES-WHEAT-AND-WHEAT-PRODUCTS",
    "food.coarse_grains": "IN-HCES-COARSE-GRAINS",
    "food.pulses": "IN-HCES-PULSES-AND-PULSE-PRODUCTS",
    "food.sugar_sweeteners": "IN-HCES-SUGAR-AND-SWEETENERS",
    "food.milk_dairy": "IN-HCES-MILK-AND-DAIRY",
    "food.meat_fish": "IN-HCES-MEAT-FISH-(EXCLUDING-EGGS)",
    "food.edible_oils": "IN-HCES-EDIBLE-OILS",
    "food.vegetables": "IN-HCES-VEGETABLES-(KG-BASED-ITEMS)",
    "food.fresh_fruit": "IN-HCES-FRESH-FRUIT-(KG-BASED-ITEMS)",
    "food.basic_grocery": "IN-HCES-BASIC-GROCERY",
    "utilities.electricity": "IN-CEA-ELECTRICITY-SPEND",
    "utilities.lpg": "IN-MOEFCC-LPG-SPEND",
    "transport_fuel.petrol": "IN-BEE-PETROL-SPEND",
    "transport_fuel.diesel": "IN-BEE-DIESEL-SPEND",
    "transport_fuel.unknown": "IN-HCES-VEHICLE-FUEL-COMBINED-SPEND",
}


@dataclass
class EmissionsResult:
    """Output of the emissions engine for one transaction."""
    factor_id: Optional[str]
    factor_method: Optional[str]        # spend_based | activity_based
    activity_quantity: Optional[float]
    activity_unit: Optional[str]
    estimated_co2e_kg: Optional[float]  # None means unsupported/unknown — NEVER 0
    emissions_status: str               # estimated|unsupported|excluded_refund|excluded_non_consumption|needs_review|error
    emissions_confidence: Optional[str] # high|medium|low
    factor_source: Optional[str]
    factor_year: Optional[int]
    estimation_notes: Optional[str]


def estimate(
    amount: float,
    currency: str,
    category: Optional[str],
    category_status: str = "categorized",
    activity_quantity: Optional[float] = None,
    activity_unit: Optional[str] = None,
    factor_registry: Optional[dict] = None,
) -> EmissionsResult:
    """
    Estimate CO₂e for a single transaction.

    Priority:
      1. Excluded categories (cash, refunds) → excluded status, NULL emissions.
      2. Non-INR currency → unsupported (NON_INR_CURRENCY), NULL emissions.
      3. Negative amounts (refunds) → excluded_refund, NULL emissions.
      4. Route B: user-supplied activity quantity + physical factor.
      5. Route A: spend-based factor for the category.
      6. Unsupported: NULL emissions, unsupported status.

    Returns EmissionsResult. Never returns 0 emissions as a placeholder.
    """
    registry = factor_registry or _FALLBACK_REGISTRY

    # ---- 1. Excluded categories ----
    if category in EXCLUDED_CATEGORIES:
        exclusion_reason = "NON_CONSUMPTION"
        if category == "refund_credit":
            exclusion_reason = "REFUND_CREDIT"
        return EmissionsResult(
            factor_id=None, factor_method=None,
            activity_quantity=None, activity_unit=None,
            estimated_co2e_kg=None,
            emissions_status="excluded_non_consumption",
            emissions_confidence=None,
            factor_source=None, factor_year=None,
            estimation_notes=f"Excluded: {exclusion_reason}",
        )

    # ---- 2. Currency check ----
    if currency and currency.upper() != "INR":
        return EmissionsResult(
            factor_id=None, factor_method=None,
            activity_quantity=None, activity_unit=None,
            estimated_co2e_kg=None,
            emissions_status="unsupported",
            emissions_confidence=None,
            factor_source=None, factor_year=None,
            estimation_notes=f"NON_INR_CURRENCY: {currency}. Cannot apply INR factors.",
        )

    # ---- 3. Negative amounts (refunds not already categorized) ----
    if isinstance(amount, (int, float)) and amount < 0:
        return EmissionsResult(
            factor_id=None, factor_method=None,
            activity_quantity=None, activity_unit=None,
            estimated_co2e_kg=None,
            emissions_status="excluded_refund",
            emissions_confidence=None,
            factor_source=None, factor_year=None,
            estimation_notes="Refund/credit excluded from emissions total.",
        )

    # ---- Validate amount ----
    try:
        amount_float = float(amount)
        if not math.isfinite(amount_float) or amount_float <= 0:
            return EmissionsResult(
                factor_id=None, factor_method=None,
                activity_quantity=None, activity_unit=None,
                estimated_co2e_kg=None,
                emissions_status="error",
                emissions_confidence=None,
                factor_source=None, factor_year=None,
                estimation_notes="Invalid amount for emissions calculation.",
            )
    except (TypeError, ValueError):
        return EmissionsResult(
            factor_id=None, factor_method=None,
            activity_quantity=None, activity_unit=None,
            estimated_co2e_kg=None,
            emissions_status="error",
            emissions_confidence=None,
            factor_source=None, factor_year=None,
            estimation_notes="Cannot parse amount.",
        )

    # ---- 4. Route B: activity-based with user-supplied quantity ----
    if activity_quantity is not None and activity_unit and category:
        route_b = _compute_route_b(
            amount=amount_float,
            category=category,
            quantity=activity_quantity,
            unit=activity_unit,
            registry=registry,
        )
        if route_b:
            return route_b

    # ---- 5. Route A: spend-based ----
    if category:
        route_a = _compute_route_a(amount=amount_float, category=category, registry=registry)
        if route_a:
            return route_a

    # ---- 6. Unsupported ----
    reason = "NO_INDIA_FACTOR"
    if not category or category == "other_unclassified":
        reason = "UNCLASSIFIED"
    elif category_status in ("needs_review", "unclassified"):
        reason = "AMBIGUOUS_CATEGORY"

    return EmissionsResult(
        factor_id=None, factor_method=None,
        activity_quantity=None, activity_unit=None,
        estimated_co2e_kg=None,
        emissions_status="unsupported",
        emissions_confidence=None,
        factor_source=None, factor_year=None,
        estimation_notes=reason,
    )


def _compute_route_a(amount: float, category: str, registry: dict) -> Optional[EmissionsResult]:
    """Route A: spend × spend factor (kgCO2e/INR)."""
    factor_id = _CATEGORY_SPEND_FACTOR.get(category)
    if not factor_id:
        return None
    factor = registry.get(factor_id)
    if not factor or factor.get("factor_type") != "spend_based":
        return None

    value = Decimal(str(factor["value"]))
    spend = Decimal(str(amount))
    # Route A: co2e = spend_inr × factor_kgco2e_per_inr
    co2e = spend * value  # full precision in calculation

    return EmissionsResult(
        factor_id=factor_id,
        factor_method="spend_based",
        activity_quantity=None,
        activity_unit=None,
        estimated_co2e_kg=float(co2e),
        emissions_status="estimated",
        emissions_confidence=factor.get("confidence", "medium"),
        factor_source=factor.get("source_name"),
        factor_year=factor.get("base_year"),
        estimation_notes=f"Route A: spend × {factor_id}",
    )


def _compute_route_b(
    amount: float,
    category: str,
    quantity: float,
    unit: str,
    registry: dict,
) -> Optional[EmissionsResult]:
    """Route B: activity_quantity × physical factor."""
    # Find a matching activity-based factor for this category
    for factor_id, factor in registry.items():
        if (
            factor.get("factor_type") == "activity_based"
            and factor.get("category") == category
            and factor.get("unit", "").lower().endswith(unit.lower().split("/")[-1])
        ):
            phys_value = Decimal(str(factor["value"]))
            qty = Decimal(str(quantity))
            co2e = qty * phys_value

            return EmissionsResult(
                factor_id=factor_id,
                factor_method="activity_based",
                activity_quantity=float(qty),
                activity_unit=unit,
                estimated_co2e_kg=float(co2e),
                emissions_status="estimated",
                emissions_confidence=factor.get("confidence", "medium"),
                factor_source=factor.get("source_name"),
                factor_year=factor.get("base_year"),
                estimation_notes=f"Route B: {quantity} {unit} × {factor_id}",
            )

    return None


def compute_coverage_metrics(df) -> dict:
    """
    Compute coverage metrics for a processed DataFrame.
    Returns dict with keys: total_spend, supported_spend, supported_pct,
    total_co2e_kg, estimated_count, unsupported_count, excluded_count.
    """
    import pandas as pd
    import numpy as np

    df = df.copy()

    # Eligible expense transactions (positive INR, not excluded)
    eligible_mask = (
        (df["amount"].apply(lambda x: isinstance(x, (int, float)) and x > 0))
        & (df.get("currency", "INR").fillna("INR").str.upper() == "INR")
        & (~df.get("emissions_status", "").isin(["excluded_non_consumption", "excluded_refund"]))
    )
    eligible_df = df[eligible_mask]
    total_spend = float(eligible_df["amount"].sum()) if not eligible_df.empty else 0.0

    # Estimated
    estimated_mask = eligible_mask & (df.get("emissions_status", "") == "estimated")
    estimated_df = df[estimated_mask]
    supported_spend = float(estimated_df["amount"].sum()) if not estimated_df.empty else 0.0
    total_co2e = (
        float(estimated_df["estimated_co2e_kg"].sum())
        if not estimated_df.empty and "estimated_co2e_kg" in estimated_df.columns
        else 0.0
    )
    if pd.isna(total_co2e):
        total_co2e = 0.0

    supported_pct = (supported_spend / total_spend * 100) if total_spend > 0 else None

    # Counts
    estimated_count = int(estimated_mask.sum())
    excluded_count = int(
        (~eligible_mask & df.get("emissions_status", "").isin(
            ["excluded_non_consumption", "excluded_refund"]
        )).sum()
    ) if "emissions_status" in df.columns else 0
    unsupported_count = int(
        (eligible_mask & (df.get("emissions_status", "") == "unsupported")).sum()
    ) if "emissions_status" in df.columns else 0

    return {
        "total_expense_spend_inr": total_spend,
        "supported_spend_inr": supported_spend,
        "supported_spend_pct": supported_pct,
        "estimated_co2e_kg": total_co2e,
        "estimated_count": estimated_count,
        "unsupported_count": unsupported_count,
        "excluded_count": excluded_count,
        "total_transactions": len(df),
    }


def apply_emissions_to_dataframe(df, factor_registry: Optional[dict] = None):
    """
    Apply emissions calculation to every row of a processed DataFrame.
    Adds emissions result columns.
    Returns modified DataFrame.
    """
    import pandas as pd

    registry = factor_registry or _FALLBACK_REGISTRY
    results = []

    for _, row in df.iterrows():
        try:
            res = estimate(
                amount=row.get("amount", 0),
                currency=str(row.get("currency", "INR") or "INR"),
                category=row.get("category"),
                category_status=str(row.get("category_status", "unclassified") or "unclassified"),
                activity_quantity=row.get("activity_quantity"),
                activity_unit=row.get("activity_unit"),
                factor_registry=registry,
            )
        except Exception as exc:
            res = EmissionsResult(
                factor_id=None, factor_method=None,
                activity_quantity=None, activity_unit=None,
                estimated_co2e_kg=None,
                emissions_status="error",
                emissions_confidence=None,
                factor_source=None, factor_year=None,
                estimation_notes=f"error:{str(exc)[:100]}",
            )
        results.append(res)

    df = df.copy()
    df["factor_id"] = [r.factor_id for r in results]
    df["factor_method"] = [r.factor_method for r in results]
    df["activity_quantity"] = [r.activity_quantity for r in results]
    df["activity_unit"] = [r.activity_unit for r in results]
    df["estimated_co2e_kg"] = [r.estimated_co2e_kg for r in results]
    df["emissions_status"] = [r.emissions_status for r in results]
    df["emissions_confidence"] = [r.emissions_confidence for r in results]
    df["factor_source"] = [r.factor_source for r in results]
    df["factor_year"] = [r.factor_year for r in results]
    df["estimation_notes"] = [r.estimation_notes for r in results]

    return df
