"""
pipeline/categorization/tier4_embedding.py
Tier 4: Optional sentence embedding semantic similarity fallback.
Loads the model lazily only when ENABLE_EMBEDDING_FALLBACK=true.
If model unavailable or load fails, returns None (safe fallthrough).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from pipeline.categorization.categories import CANONICAL_CATEGORIES, CategoryResult

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = None
_EMBEDDINGS_LOADED = False
_REFERENCE_EMBEDDINGS: Optional[object] = None
_REFERENCE_LABELS: list[tuple[str, Optional[str]]] = []

ENABLED = os.environ.get("ENABLE_EMBEDDING_FALLBACK", "false").lower() == "true"
SIMILARITY_THRESHOLD = float(os.environ.get("EMBEDDING_SIMILARITY_THRESHOLD", "0.75"))
AMBIGUITY_GAP = float(os.environ.get("EMBEDDING_AMBIGUITY_GAP", "0.05"))
MODEL_NAME = "all-MiniLM-L6-v2"

# Curated reference examples for semantic matching
REFERENCE_EXAMPLES: list[tuple[str, str, Optional[str]]] = [
    ("electricity payment", "utilities.electricity", "Electricity bill"),
    ("power bill payment", "utilities.electricity", "Electricity bill"),
    ("lpg gas cylinder", "utilities.lpg", "LPG/cooking gas"),
    ("cooking gas refill", "utilities.lpg", "LPG/cooking gas"),
    ("petrol fill", "transport_fuel.petrol", "Petrol"),
    ("fuel purchase petrol", "transport_fuel.petrol", "Petrol"),
    ("diesel fill up", "transport_fuel.diesel", "Diesel"),
    ("grocery purchase", "food.basic_grocery", "Basic grocery basket"),
    ("vegetables market", "food.vegetables", "Vegetables"),
    ("fresh fruit shop", "food.fresh_fruit", "Fresh fruit"),
    ("milk purchase", "food.milk_dairy", "Dairy"),
    ("dairy products", "food.milk_dairy", "Dairy"),
    ("rice purchase", "food.rice", "Rice"),
    ("wheat flour", "food.wheat_products", "Wheat products"),
    ("dal purchase", "food.pulses", "Pulses"),
    ("restaurant food", "food.restaurant_delivery", "Restaurant"),
    ("online food order", "food.restaurant_delivery", "Food delivery"),
    ("clothing store", "shopping.clothing", "Clothing"),
    ("online shopping", "shopping.general_ecommerce", "E-commerce"),
    ("bus ticket", "transport.public_transit", "Public transit"),
    ("train journey", "transport.public_transit", "Train"),
    ("cab ride", "transport.taxi_rideshare", "Taxi"),
    ("mobile recharge", "telecom_internet", "Telecom"),
    ("internet bill", "telecom_internet", "Broadband"),
    ("medicine pharmacy", "healthcare", "Pharmacy"),
    ("doctor consultation", "healthcare", "Healthcare"),
    ("atm cash", "cash_withdrawal_transfer", "ATM"),
    ("bank transfer", "cash_withdrawal_transfer", "Transfer"),
    ("refund received", "refund_credit", "Refund"),
]


def _load_embeddings() -> bool:
    """Load model and precompute reference embeddings. Returns True if successful."""
    global _EMBEDDING_MODEL, _REFERENCE_EMBEDDINGS, _REFERENCE_LABELS, _EMBEDDINGS_LOADED
    if _EMBEDDINGS_LOADED:
        return _EMBEDDING_MODEL is not None

    _EMBEDDINGS_LOADED = True
    if not ENABLED:
        return False

    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        _EMBEDDING_MODEL = SentenceTransformer(MODEL_NAME)
        texts = [ex[0] for ex in REFERENCE_EXAMPLES]
        _REFERENCE_EMBEDDINGS = _EMBEDDING_MODEL.encode(texts, normalize_embeddings=True)
        _REFERENCE_LABELS = [(ex[1], ex[2]) for ex in REFERENCE_EXAMPLES]
        logger.info("Tier 4 embedding model loaded: %s", MODEL_NAME)
        return True
    except Exception as exc:
        logger.warning("Tier 4 embedding model load failed: %s", str(exc)[:200])
        _EMBEDDING_MODEL = None
        return False


def classify(merchant_key: str) -> Optional[CategoryResult]:
    """
    Semantic embedding similarity matching.
    Returns CategoryResult if confident match found, None otherwise.
    """
    if not ENABLED:
        return None
    if not _load_embeddings() or _EMBEDDING_MODEL is None:
        return None

    try:
        import numpy as np
        query_emb = _EMBEDDING_MODEL.encode([merchant_key], normalize_embeddings=True)
        similarities = (_REFERENCE_EMBEDDINGS @ query_emb.T).flatten()  # type: ignore[operator]
        sorted_idx = np.argsort(similarities)[::-1]

        best_idx = int(sorted_idx[0])
        best_score = float(similarities[best_idx])
        second_score = float(similarities[sorted_idx[1]]) if len(sorted_idx) > 1 else 0.0
        gap = best_score - second_score

        if best_score < SIMILARITY_THRESHOLD:
            return None

        cat, subcat = _REFERENCE_LABELS[best_idx]

        if gap < AMBIGUITY_GAP:
            return CategoryResult(
                category=cat,
                subcategory=subcat,
                merchant_name=None,
                merchant_key=merchant_key,
                tier=4,
                method="embedding",
                confidence=best_score * 0.6,
                status="needs_review",
                reason=f"embedding_ambiguous:score={best_score:.3f},gap={gap:.3f}",
            )

        return CategoryResult(
            category=cat,
            subcategory=subcat,
            merchant_name=None,
            merchant_key=merchant_key,
            tier=4,
            method="embedding",
            confidence=min(best_score * 0.8, 0.8),
            status="categorized",
            reason=f"embedding_match:score={best_score:.3f}",
        )
    except Exception as exc:
        logger.error("Tier 4 classify error: %s", str(exc)[:200])
        return None
