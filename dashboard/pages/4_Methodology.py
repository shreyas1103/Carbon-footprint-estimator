"""
dashboard/pages/4_Methodology.py
Methodology and factor registry documentation page.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st

st.set_page_config(
    page_title="Methodology — Carbon Footprint Estimator",
    page_icon="📚",
    layout="wide",
)

st.title("📚 Methodology & Factor Sources")
st.caption("How carbon emissions are estimated — India-specific hybrid approach")

st.subheader("Estimation Approach")

col1, col2 = st.columns(2)
with col1:
    st.markdown("""
### Route A — Spend-Based

**Formula:**
```
CO₂e (kg) = Spend (INR) × Factor (kgCO₂e/INR)
```

Used when a validated India-specific spend factor exists for the merchant category.
The factor is derived from physical emission data and Household Consumer Expenditure
Survey (HCES) spend data, then pre-computed as a spend factor.

**At runtime:** spend × spend factor only. No further physical factor multiplication.
    """)

with col2:
    st.markdown("""
### Route B — Activity-Based

**Formula:**
```
Quantity = Spend (INR) / Price per unit
CO₂e (kg) = Quantity × Physical Factor (kgCO₂/unit)
```

Used when an actual physical quantity is available or can be defensibly inferred
(e.g., kWh from an electricity bill, litres from a fuel receipt).

**Note:** If quantity is inferred from spend, it is labelled "estimated from spend"
and confidence is lowered. Do not infer quantity when no reliable unit price is known.
    """)

st.info(
    "⚠️ **No double-counting rule:** A spend factor (kgCO₂e/INR) is applied once to spend. "
    "A physical factor (kgCO₂/unit) is applied once to quantity. Never apply both to the same transaction.",
    icon="⚠️",
)

st.divider()
st.subheader("Active India Factor Registry")

# Show factor table
from pipeline.emissions import _FALLBACK_REGISTRY
import pandas as pd

factor_rows = []
for fid, f in _FALLBACK_REGISTRY.items():
    factor_rows.append({
        "Factor ID": fid,
        "Category": f.get("category"),
        "Type": f.get("factor_type"),
        "Value": float(f.get("value", 0)),
        "Unit": f.get("unit"),
        "Source": f.get("source_name"),
        "Confidence": f.get("confidence"),
    })

factor_df = pd.DataFrame(factor_rows)
st.dataframe(factor_df, use_container_width=True, height=500)

st.caption(
    "All factors are India-specific. Foreign factors (UK DEFRA, US EPA) are NOT used. "
    "Factors with 'spend_based' type are Route A; 'activity_based' are Route B only."
)

st.divider()
st.subheader("Unsupported Categories")
st.markdown("""
The following categories have **no current active India-specific factor** and will always
show `emissions_status = unsupported`:

- `food.restaurant_delivery` — No defensible India-specific factor
- `shopping.*` — clothing, footwear, electronics, general e-commerce
- `transport.public_transit`, `transport.taxi_rideshare`, `transport.air_travel`
- `entertainment`, `healthcare`, `telecom_internet`, `personal_care`
- `education`, `housing_rent`, `insurance_finance`
- `cash_withdrawal_transfer`, `refund_credit` — Excluded from consumption emissions

**Policy:** `estimated_co2e_kg = NULL` for unsupported categories. Never `0`.
The app reports spend coverage so the partial nature of the estimate is always visible.
""")

st.divider()
st.subheader("Coverage Disclaimer")
st.warning(
    "The CO₂e totals shown in this application cover only transactions where a "
    "validated India-specific emission factor exists. "
    "**This is NOT a complete carbon footprint.** "
    "Spend in unsupported categories is excluded from the total but shown separately.",
    icon="⚠️",
)
