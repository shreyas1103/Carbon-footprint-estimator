"""
pipeline/categorization/categories.py
Canonical category enum and shared result dataclass.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Canonical category enum values
# ---------------------------------------------------------------------------
CANONICAL_CATEGORIES = {
    "utilities.electricity",
    "utilities.lpg",
    "transport_fuel.petrol",
    "transport_fuel.diesel",
    "transport_fuel.unknown",
    "food.rice",
    "food.wheat_products",
    "food.coarse_grains",
    "food.pulses",
    "food.sugar_sweeteners",
    "food.milk_dairy",
    "food.meat_fish",
    "food.edible_oils",
    "food.vegetables",
    "food.fresh_fruit",
    "food.basic_grocery",
    "food.restaurant_delivery",
    "shopping.clothing",
    "shopping.footwear",
    "shopping.general_ecommerce",
    "shopping.electronics",
    "transport.public_transit",
    "transport.taxi_rideshare",
    "transport.air_travel",
    "transport.vehicle_purchase",
    "entertainment",
    "healthcare",
    "telecom_internet",
    "personal_care",
    "education",
    "housing_rent",
    "insurance_finance",
    "cash_withdrawal_transfer",
    "refund_credit",
    "other_unclassified",
}

# Categories that should be excluded from consumption emissions
EXCLUDED_CATEGORIES = {"cash_withdrawal_transfer", "refund_credit"}

# Categories with a supported India factor (spend-based Route A)
SUPPORTED_SPEND_CATEGORIES = {
    "food.rice",
    "food.wheat_products",
    "food.coarse_grains",
    "food.pulses",
    "food.sugar_sweeteners",
    "food.milk_dairy",
    "food.meat_fish",
    "food.edible_oils",
    "food.vegetables",
    "food.fresh_fruit",
    "food.basic_grocery",
    "utilities.electricity",
    "utilities.lpg",
    "transport_fuel.petrol",
    "transport_fuel.diesel",
    "transport_fuel.unknown",
}


@dataclass
class CategoryResult:
    """Output from any categorization tier."""
    category: Optional[str]
    subcategory: Optional[str]
    merchant_name: Optional[str]
    merchant_key: Optional[str]
    tier: Optional[int]
    method: Optional[str]
    confidence: float            # 0.0–1.0
    status: str                  # categorized | needs_review | unclassified
    reason: Optional[str] = None

    def is_valid_category(self) -> bool:
        return self.category in CANONICAL_CATEGORIES

    def is_accepted(self, min_confidence: float = 0.0) -> bool:
        return (
            self.status == "categorized"
            and self.is_valid_category()
            and self.confidence >= min_confidence
        )
