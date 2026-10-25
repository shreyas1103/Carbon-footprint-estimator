"""
pipeline/categorization/tier3_fuzzy.py
Tier 3: RapidFuzz fuzzy matching against dictionary aliases.
Default threshold: 90 (0-100 scale).
Requires 5-point ambiguity gap between best and second-best match.
"""
from __future__ import annotations

import os
from typing import Optional

from pipeline.categorization.categories import CANONICAL_CATEGORIES, CategoryResult
from pipeline.categorization.tier2_dictionary import ALIAS_MAP, _normalize

DEFAULT_THRESHOLD = int(os.environ.get("FUZZY_MATCH_THRESHOLD", "90"))
DEFAULT_AMBIGUITY_GAP = int(os.environ.get("FUZZY_AMBIGUITY_GAP", "5"))


def classify(
    merchant_key: str,
    threshold: int = DEFAULT_THRESHOLD,
    ambiguity_gap: int = DEFAULT_AMBIGUITY_GAP,
) -> Optional[CategoryResult]:
    """
    Fuzzy match merchant_key against all known dictionary aliases.
    Returns CategoryResult if a confident, unambiguous match is found.
    Returns needs_review if match is within ambiguity gap.
    Returns None if no match above threshold.
    """
    if not merchant_key:
        return None

    try:
        from rapidfuzz import process, fuzz
    except ImportError:
        return None

    norm_key = _normalize(merchant_key)
    alias_keys = list(ALIAS_MAP.keys())

    # Get best matches scored by token_set_ratio (handles word-order variations)
    results = process.extract(
        norm_key,
        alias_keys,
        scorer=fuzz.token_set_ratio,
        limit=3,
    )

    if not results:
        return None

    best_alias, best_score, _ = results[0]
    second_score = results[1][1] if len(results) > 1 else 0

    if best_score < threshold:
        return None

    gap = best_score - second_score
    cat, subcat, ambiguous = ALIAS_MAP[best_alias]

    if gap < ambiguity_gap or ambiguous:
        # Ambiguous — fall through rather than assigning incorrectly
        return CategoryResult(
            category=cat,
            subcategory=subcat,
            merchant_name=None,
            merchant_key=merchant_key,
            tier=3,
            method="fuzzy",
            confidence=0.4,
            status="needs_review",
            reason=f"fuzzy_ambiguous:best={best_alias}({best_score:.0f}),gap={gap:.0f}",
        )

    # Confident fuzzy match
    confidence = min(best_score / 100.0 * 0.85, 0.85)  # max 0.85 for fuzzy
    return CategoryResult(
        category=cat,
        subcategory=subcat,
        merchant_name=None,
        merchant_key=merchant_key,
        tier=3,
        method="fuzzy",
        confidence=confidence,
        status="categorized",
        reason=f"fuzzy_match:{best_alias}(score={best_score:.0f})",
    )
