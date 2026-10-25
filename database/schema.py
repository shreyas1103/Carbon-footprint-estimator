"""
database/schema.py
Creates all tables safely (create_all, no drops).
Also seeds the active India factor registry on first run.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from database.base import Base
from database.connection import get_engine, get_session
from database.models import CarbonFactor

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Active India spend-based carbon factors (from project workbook)
# Do NOT modify these values — they are traceable to the workbook source.
# ---------------------------------------------------------------------------
INDIA_FACTORS = [
    {
        "factor_id": "IN-HCES-RICE-AND-RICE-PRODUCTS",
        "category": "food.rice",
        "subcategory": "Rice and rice products",
        "factor_type": "spend_based",
        "value": Decimal("0.07048581883787187"),
        "unit": "kgCO2e/INR",
        "country": "India",
        "source_name": "HCES India",
        "confidence": "medium",
        "active": True,
        "methodology_notes": (
            "Only if classifier/mapping specifically supports rice; "
            "not a universal grocery factor."
        ),
    },
    {
        "factor_id": "IN-HCES-WHEAT-AND-WHEAT-PRODUCTS",
        "category": "food.wheat_products",
        "subcategory": "Wheat and wheat products",
        "factor_type": "spend_based",
        "value": Decimal("0.01210098015315142"),
        "unit": "kgCO2e/INR",
        "country": "India",
        "source_name": "HCES India",
        "confidence": "medium",
        "active": True,
        "methodology_notes": "Specific category only.",
    },
    {
        "factor_id": "IN-HCES-COARSE-GRAINS",
        "category": "food.coarse_grains",
        "subcategory": "Coarse grains",
        "factor_type": "spend_based",
        "value": Decimal("0.005561874060700431"),
        "unit": "kgCO2e/INR",
        "country": "India",
        "source_name": "HCES India",
        "confidence": "medium",
        "active": True,
        "methodology_notes": "Specific category only.",
    },
    {
        "factor_id": "IN-HCES-PULSES-AND-PULSE-PRODUCTS",
        "category": "food.pulses",
        "subcategory": "Pulses",
        "factor_type": "spend_based",
        "value": Decimal("0.004027566759451551"),
        "unit": "kgCO2e/INR",
        "country": "India",
        "source_name": "HCES India",
        "confidence": "medium",
        "active": True,
        "methodology_notes": "Specific category only.",
    },
    {
        "factor_id": "IN-HCES-SUGAR-AND-SWEETENERS",
        "category": "food.sugar_sweeteners",
        "subcategory": "Sugar and sweeteners",
        "factor_type": "spend_based",
        "value": Decimal("0.003699943926194361"),
        "unit": "kgCO2e/INR",
        "country": "India",
        "source_name": "HCES India",
        "confidence": "medium",
        "active": True,
        "methodology_notes": "Specific category only.",
    },
    {
        "factor_id": "IN-HCES-MILK-AND-DAIRY",
        "category": "food.milk_dairy",
        "subcategory": "Milk and dairy",
        "factor_type": "spend_based",
        "value": Decimal("0.1255438890163547"),
        "unit": "kgCO2e/INR",
        "country": "India",
        "source_name": "HCES India",
        "confidence": "medium",
        "active": True,
        "methodology_notes": "Dairy-specific transactions only.",
    },
    {
        "factor_id": "IN-HCES-MEAT-FISH-(EXCLUDING-EGGS)",
        "category": "food.meat_fish",
        "subcategory": "Meat and fish",
        "factor_type": "spend_based",
        "value": Decimal("0.06844688332133109"),
        "unit": "kgCO2e/INR",
        "country": "India",
        "source_name": "HCES India",
        "confidence": "medium",
        "active": True,
        "methodology_notes": "Do not use for eggs unless source mapping explicitly permits it.",
    },
    {
        "factor_id": "IN-HCES-EDIBLE-OILS",
        "category": "food.edible_oils",
        "subcategory": "Edible oils",
        "factor_type": "spend_based",
        "value": Decimal("0.01840805461327834"),
        "unit": "kgCO2e/INR",
        "country": "India",
        "source_name": "HCES India",
        "confidence": "medium",
        "active": True,
        "methodology_notes": "Specific category only.",
    },
    {
        "factor_id": "IN-HCES-VEGETABLES-(KG-BASED-ITEMS)",
        "category": "food.vegetables",
        "subcategory": "Vegetables",
        "factor_type": "spend_based",
        "value": Decimal("0.00124394517499368"),
        "unit": "kgCO2e/INR",
        "country": "India",
        "source_name": "HCES India",
        "confidence": "medium",
        "active": True,
        "methodology_notes": "Category average; source basis is limited.",
    },
    {
        "factor_id": "IN-HCES-FRESH-FRUIT-(KG-BASED-ITEMS)",
        "category": "food.fresh_fruit",
        "subcategory": "Fresh fruit",
        "factor_type": "spend_based",
        "value": Decimal("0.0006504095558087095"),
        "unit": "kgCO2e/INR",
        "country": "India",
        "source_name": "HCES India",
        "confidence": "medium",
        "active": True,
        "methodology_notes": "Category average; source basis is limited.",
    },
    {
        "factor_id": "IN-HCES-BASIC-GROCERY",
        "category": "food.basic_grocery",
        "subcategory": "Basic grocery basket",
        "factor_type": "spend_based",
        "value": Decimal("0.04246780031372872"),
        "unit": "kgCO2e/INR",
        "country": "India",
        "source_name": "HCES India",
        "confidence": "medium",
        "active": True,
        "methodology_notes": (
            "Only for grocery merchants where a mixed grocery basket is plausible; "
            "not restaurants/food delivery."
        ),
    },
    {
        "factor_id": "IN-CEA-ELECTRICITY-SPEND",
        "category": "utilities.electricity",
        "subcategory": "Electricity bill",
        "factor_type": "spend_based",
        "value": Decimal("0.1325303878714435"),
        "unit": "kgCO2e/INR",
        "country": "India",
        "source_name": "CEA V21.0 (derived spend factor)",
        "confidence": "high",
        "active": True,
        "methodology_notes": "Spend-based factor at runtime; do not apply kWh factor again.",
    },
    {
        "factor_id": "IN-MOEFCC-LPG-SPEND",
        "category": "utilities.lpg",
        "subcategory": "LPG/cooking gas",
        "factor_type": "spend_based",
        "value": Decimal("0.04715845926839721"),
        "unit": "kgCO2e/INR",
        "country": "India",
        "source_name": "MoEFCC Low Carbon Lifestyles (derived spend factor)",
        "confidence": "high",
        "active": True,
        "methodology_notes": "Spend-based factor at runtime; do not apply LPG physical factor again.",
    },
    {
        "factor_id": "IN-BEE-PETROL-SPEND",
        "category": "transport_fuel.petrol",
        "subcategory": "Petrol",
        "factor_type": "spend_based",
        "value": Decimal("0.02209753236010448"),
        "unit": "kgCO2e/INR",
        "country": "India",
        "source_name": "BEE India (derived spend factor)",
        "confidence": "high",
        "active": True,
        "methodology_notes": "Only when petrol is known.",
    },
    {
        "factor_id": "IN-BEE-DIESEL-SPEND",
        "category": "transport_fuel.diesel",
        "subcategory": "Diesel",
        "factor_type": "spend_based",
        "value": Decimal("0.02853545300348392"),
        "unit": "kgCO2e/INR",
        "country": "India",
        "source_name": "BEE India (derived spend factor)",
        "confidence": "high",
        "active": True,
        "methodology_notes": "Only when diesel is known.",
    },
    {
        "factor_id": "IN-HCES-VEHICLE-FUEL-COMBINED-SPEND",
        "category": "transport_fuel.unknown",
        "subcategory": "Unknown vehicle fuel",
        "factor_type": "spend_based",
        "value": Decimal("0.02470813417651744"),
        "unit": "kgCO2e/INR",
        "country": "India",
        "source_name": "HCES India (blended estimate)",
        "confidence": "high",
        "active": True,
        "methodology_notes": (
            "Use only when fuel type is genuinely unknown and a combined estimate is acceptable; "
            "label blended estimate."
        ),
    },
    # Physical (Route B) factors — separate IDs, not spend factors
    {
        "factor_id": "IN-ELEC-CEA-V21-2024-25",
        "category": "utilities.electricity",
        "subcategory": "Electricity (activity-based)",
        "factor_type": "activity_based",
        "value": Decimal("0.7117"),
        "unit": "kgCO2/kWh",
        "country": "India",
        "base_year": 2024,
        "source_name": "CEA V21.0",
        "source_version": "V21.0",
        "confidence": "high",
        "active": True,
        "methodology_notes": "Use only with actual/inferred kWh. FY 2024-25.",
    },
    {
        "factor_id": "IN-LPG-MOEF-LCL",
        "category": "utilities.lpg",
        "subcategory": "LPG (activity-based)",
        "factor_type": "activity_based",
        "value": Decimal("3.13"),
        "unit": "kgCO2/kg",
        "country": "India",
        "source_name": "MoEFCC Low Carbon Lifestyles",
        "confidence": "high",
        "active": True,
        "methodology_notes": "Use only with actual/inferred kg LPG.",
    },
    {
        "factor_id": "IN-PETROL-ROAD-DPIIT",
        "category": "transport_fuel.petrol",
        "subcategory": "Petrol (activity-based)",
        "factor_type": "activity_based",
        "value": Decimal("2.27"),
        "unit": "kgCO2/L",
        "country": "India",
        "source_name": "DPIIT/WRI India road-fuel reference",
        "confidence": "medium",
        "active": True,
        "methodology_notes": "Keep source traceability; verify exact citation.",
    },
    {
        "factor_id": "IN-DIESEL-ROAD-DPIIT",
        "category": "transport_fuel.diesel",
        "subcategory": "Diesel (activity-based)",
        "factor_type": "activity_based",
        "value": Decimal("2.64"),
        "unit": "kgCO2/L",
        "country": "India",
        "source_name": "DPIIT/WRI India road-fuel reference",
        "confidence": "medium",
        "active": True,
        "methodology_notes": "Keep source traceability; verify exact citation.",
    },
]


def create_tables() -> bool:
    """
    Create all tables if they do not exist. Never drops existing data.
    Returns True if successful (or tables already exist), False if DB unavailable.
    """
    engine = get_engine()
    if engine is None:
        logger.warning("Database not configured. Skipping table creation.")
        return False
    try:
        Base.metadata.create_all(engine, checkfirst=True)
        logger.info("Database tables created/verified.")
        return True
    except Exception as exc:
        logger.error("Failed to create tables: %s", str(exc)[:200])
        return False


def seed_factors(session: Session) -> None:
    """
    Idempotently insert the active India factor rows.
    Uses merge (upsert by primary key) so reruns are safe.
    """
    for row in INDIA_FACTORS:
        existing = session.get(CarbonFactor, row["factor_id"])
        if existing is None:
            session.add(CarbonFactor(**row))
    session.commit()


def initialize_db() -> bool:
    """
    Full initialization: create tables + seed factors.
    Safe to call multiple times.
    """
    if not create_tables():
        return False
    session = get_session()
    if session is None:
        return False
    try:
        seed_factors(session)
        return True
    except Exception as exc:
        logger.error("Factor seed failed: %s", str(exc)[:200])
        session.rollback()
        return False
    finally:
        session.close()
