"""
pipeline/categorization/tier2_dictionary.py
Tier 2: Exact normalized alias/dictionary matching.
High-confidence (1.0) for unambiguous aliases.
Ambiguous aliases → needs_review.
"""
from __future__ import annotations

import re
from typing import Optional

from pipeline.categorization.categories import CANONICAL_CATEGORIES, CategoryResult

# ---------------------------------------------------------------------------
# Version-controlled alias dictionary
# Keys: normalized alias text (lowercase, stripped)
# Values: (category, subcategory, ambiguous?)
# ---------------------------------------------------------------------------
ALIAS_MAP: dict[str, tuple[str, Optional[str], bool]] = {
    # Electricity
    "electricity bill": ("utilities.electricity", "Electricity bill", False),
    "power bill": ("utilities.electricity", "Electricity bill", False),
    "bescom": ("utilities.electricity", "Electricity bill", False),
    "bses": ("utilities.electricity", "Electricity bill", False),
    "tata power": ("utilities.electricity", "Electricity bill", False),
    "adani electricity": ("utilities.electricity", "Electricity bill", False),
    "msedcl": ("utilities.electricity", "Electricity bill", False),
    "tneb": ("utilities.electricity", "Electricity bill", False),
    "torrent power": ("utilities.electricity", "Electricity bill", False),
    "cesc": ("utilities.electricity", "Electricity bill", False),
    "uppcl": ("utilities.electricity", "Electricity bill", False),
    "wbsedcl": ("utilities.electricity", "Electricity bill", False),
    "electricity board": ("utilities.electricity", "Electricity bill", False),
    "electricity dept": ("utilities.electricity", "Electricity bill", False),

    # LPG
    "lpg refill": ("utilities.lpg", "LPG cylinder refill", False),
    "cooking gas": ("utilities.lpg", "LPG cylinder refill", False),
    "lpg cylinder": ("utilities.lpg", "LPG cylinder refill", False),
    "indane gas": ("utilities.lpg", "LPG cylinder refill", False),
    "hp gas": ("utilities.lpg", "LPG cylinder refill", False),
    "bharat gas": ("utilities.lpg", "LPG cylinder refill", False),
    "lpg": ("utilities.lpg", "LPG cylinder refill", False),

    # Petrol (explicit)
    "petrol pump": ("transport_fuel.petrol", "Petrol", False),
    "petrol bunk": ("transport_fuel.petrol", "Petrol", False),
    "petrol station": ("transport_fuel.petrol", "Petrol", False),
    "petrol": ("transport_fuel.petrol", "Petrol", False),
    "iocl petrol": ("transport_fuel.petrol", "Petrol", False),
    "hp petrol": ("transport_fuel.petrol", "Petrol", False),
    "bpcl petrol": ("transport_fuel.petrol", "Petrol", False),

    # Diesel (explicit)
    "diesel pump": ("transport_fuel.diesel", "Diesel", False),
    "diesel": ("transport_fuel.diesel", "Diesel", False),
    "iocl diesel": ("transport_fuel.diesel", "Diesel", False),
    "bpcl diesel": ("transport_fuel.diesel", "Diesel", False),

    # Fuel stations (type unknown → use combined factor / needs_review)
    "fuel station": ("transport_fuel.unknown", "Unknown vehicle fuel", False),
    "fuel pump": ("transport_fuel.unknown", "Unknown vehicle fuel", False),
    "iocl": ("transport_fuel.unknown", "Unknown vehicle fuel", True),     # could be petrol or diesel
    "bpcl": ("transport_fuel.unknown", "Unknown vehicle fuel", True),
    "hpcl": ("transport_fuel.unknown", "Unknown vehicle fuel", True),
    "reliance fuel": ("transport_fuel.unknown", "Unknown vehicle fuel", True),

    # Grocery
    "grocery": ("food.basic_grocery", "Basic grocery basket", False),
    "kirana": ("food.basic_grocery", "Basic grocery basket", False),
    "provision store": ("food.basic_grocery", "Basic grocery basket", False),
    "supermarket": ("food.basic_grocery", "Basic grocery basket", False),
    "bigbasket": ("food.basic_grocery", "Basic grocery basket", False),
    "grofers": ("food.basic_grocery", "Basic grocery basket", False),
    "blinkit": ("food.basic_grocery", "Basic grocery basket", False),
    "zepto": ("food.basic_grocery", "Basic grocery basket", False),
    "jiomart": ("food.basic_grocery", "Basic grocery basket", False),
    "dmart": ("food.basic_grocery", "Basic grocery basket", False),
    "more supermarket": ("food.basic_grocery", "Basic grocery basket", False),
    "reliance fresh": ("food.basic_grocery", "Basic grocery basket", False),
    "nature s basket": ("food.basic_grocery", "Basic grocery basket", False),
    "spencer s": ("food.basic_grocery", "Basic grocery basket", False),

    # Dairy
    "milk": ("food.milk_dairy", "Dairy", False),
    "dairy": ("food.milk_dairy", "Dairy", False),
    "amul": ("food.milk_dairy", "Dairy", False),
    "mother dairy": ("food.milk_dairy", "Dairy", False),
    "milkbasket": ("food.milk_dairy", "Dairy", False),

    # Restaurants / food delivery (unsupported for emissions)
    "zomato": ("food.restaurant_delivery", "Food delivery", False),
    "swiggy": ("food.restaurant_delivery", "Food delivery", False),
    "restaurant": ("food.restaurant_delivery", "Restaurant", False),
    "cafe": ("food.restaurant_delivery", "Cafe", False),
    "food delivery": ("food.restaurant_delivery", "Food delivery", False),
    "hotel": ("food.restaurant_delivery", "Restaurant", True),  # ambiguous

    # Clothing / apparel
    "clothing": ("shopping.clothing", "Clothing", False),
    "garments": ("shopping.clothing", "Clothing", False),
    "apparel": ("shopping.clothing", "Clothing", False),
    "myntra": ("shopping.clothing", "Clothing", False),
    "ajio": ("shopping.clothing", "Clothing", False),

    # Footwear
    "footwear": ("shopping.footwear", "Footwear", False),
    "shoes": ("shopping.footwear", "Footwear", False),
    "bata": ("shopping.footwear", "Footwear", False),

    # E-commerce (general)
    "amazon": ("shopping.general_ecommerce", "E-commerce", False),
    "flipkart": ("shopping.general_ecommerce", "E-commerce", False),
    "meesho": ("shopping.general_ecommerce", "E-commerce", False),
    "snapdeal": ("shopping.general_ecommerce", "E-commerce", False),

    # Electronics
    "electronics": ("shopping.electronics", "Electronics", False),
    "croma": ("shopping.electronics", "Electronics", False),
    "vijay sales": ("shopping.electronics", "Electronics", False),

    # Transport (public)
    "metro": ("transport.public_transit", "Public transit", False),
    "bus": ("transport.public_transit", "Public transit", True),  # ambiguous (school bus?)
    "irctc": ("transport.public_transit", "Train", False),
    "dmrc": ("transport.public_transit", "Metro", False),

    # Taxi / ride-hail
    "ola": ("transport.taxi_rideshare", "Taxi/ride-share", False),
    "uber": ("transport.taxi_rideshare", "Taxi/ride-share", False),
    "rapido": ("transport.taxi_rideshare", "Taxi/ride-share", False),

    # Air travel
    "indigo": ("transport.air_travel", "Air travel", False),
    "air india": ("transport.air_travel", "Air travel", False),
    "spicejet": ("transport.air_travel", "Air travel", False),
    "vistara": ("transport.air_travel", "Air travel", False),
    "akasa": ("transport.air_travel", "Air travel", False),

    # Entertainment
    "netflix": ("entertainment", "Streaming", False),
    "hotstar": ("entertainment", "Streaming", False),
    "amazon prime": ("entertainment", "Streaming", False),
    "bookmyshow": ("entertainment", "Entertainment", False),
    "pvr": ("entertainment", "Cinema", False),
    "inox": ("entertainment", "Cinema", False),

    # Healthcare
    "pharmacy": ("healthcare", "Pharmacy", False),
    "hospital": ("healthcare", "Hospital", False),
    "apollo": ("healthcare", "Healthcare", True),  # Apollo could be Apollo Pharmacy or Apollo Hospitals
    "medplus": ("healthcare", "Pharmacy", False),
    "1mg": ("healthcare", "Pharmacy", False),
    "pharmeasy": ("healthcare", "Pharmacy", False),

    # Telecom
    "jio": ("telecom_internet", "Telecom", False),
    "airtel": ("telecom_internet", "Telecom", False),
    "vi": ("telecom_internet", "Telecom", True),   # ambiguous — VI is Vodafone Idea but also common abbreviation
    "vodafone": ("telecom_internet", "Telecom", False),
    "idea": ("telecom_internet", "Telecom", True),
    "bsnl": ("telecom_internet", "Telecom", False),
    "broadband": ("telecom_internet", "Broadband", False),

    # Education
    "byjus": ("education", "EdTech", False),
    "unacademy": ("education", "EdTech", False),
    "coursera": ("education", "EdTech", False),
    "udemy": ("education", "EdTech", False),
    "school": ("education", "School", False),
    "college": ("education", "Education", False),

    # Cash / transfers (excluded from emissions)
    "atm withdrawal": ("cash_withdrawal_transfer", "ATM", False),
    "cash withdrawal": ("cash_withdrawal_transfer", "ATM", False),
    "upi transfer": ("cash_withdrawal_transfer", "UPI transfer", False),
    "neft transfer": ("cash_withdrawal_transfer", "Bank transfer", False),
    "imps transfer": ("cash_withdrawal_transfer", "Bank transfer", False),
    "credit card payment": ("cash_withdrawal_transfer", "Card payment", False),
    "card payment": ("cash_withdrawal_transfer", "Card payment", True),

    # Refunds
    "refund": ("refund_credit", "Refund", False),
    "reimbursement": ("refund_credit", "Reimbursement", False),
    "cashback": ("refund_credit", "Cashback", False),
    "reversal": ("refund_credit", "Reversal", False),
}


def _normalize(text: str) -> str:
    """Normalize text for alias matching."""
    text = text.casefold().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def classify(merchant_key: str) -> Optional[CategoryResult]:
    """
    Perform exact normalized alias lookup.
    Returns CategoryResult if matched, else None.
    Ambiguous aliases return needs_review status.
    """
    if not merchant_key:
        return None

    norm = _normalize(merchant_key)

    # Direct match
    if norm in ALIAS_MAP:
        cat, subcat, ambiguous = ALIAS_MAP[norm]
        return CategoryResult(
            category=cat,
            subcategory=subcat,
            merchant_name=None,
            merchant_key=merchant_key,
            tier=2,
            method="dictionary",
            confidence=0.5 if ambiguous else 1.0,
            status="needs_review" if ambiguous else "categorized",
            reason=f"alias_match:{norm}",
        )

    # Substring match (check if any known alias is contained in the merchant key)
    best: Optional[tuple[str, str, Optional[str], bool]] = None
    best_len = 0
    for alias, (cat, subcat, ambiguous) in ALIAS_MAP.items():
        if alias in norm and len(alias) > best_len:
            best = (alias, cat, subcat, ambiguous)
            best_len = len(alias)

    if best:
        alias, cat, subcat, ambiguous = best
        return CategoryResult(
            category=cat,
            subcategory=subcat,
            merchant_name=None,
            merchant_key=merchant_key,
            tier=2,
            method="dictionary_substring",
            confidence=0.4 if ambiguous else 0.9,
            status="needs_review" if ambiguous else "categorized",
            reason=f"alias_substring:{alias}",
        )

    return None
