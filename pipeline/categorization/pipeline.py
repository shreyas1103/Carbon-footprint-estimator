"""
pipeline/categorization/pipeline.py
Orchestrates all categorization tiers in priority order:
  0 → cache
  1 → TF-IDF/LR classifier
  2 → dictionary
  3 → fuzzy
  4 → embeddings (optional)
  5 → LLM (optional)
  → unclassified

Higher-priority confident results are NEVER overwritten.
Each failing tier falls through; one tier failing does not abort the batch.
"""
from __future__ import annotations

import logging
from typing import Optional

from pipeline.categorization import (
    tier0_cache,
    tier1_classifier,
    tier2_dictionary,
    tier3_fuzzy,
    tier4_embedding,
    tier5_llm,
)
from pipeline.categorization.categories import CANONICAL_CATEGORIES, CategoryResult

logger = logging.getLogger(__name__)

# Minimum confidence for a categorized result to be accepted without needs_review
ACCEPT_THRESHOLD = 0.75


def categorize_merchant(
    merchant_key: str,
    cleaned_description: str,
    session=None,
) -> CategoryResult:
    """
    Run the full five-tier categorization pipeline for a single merchant.

    Args:
        merchant_key: normalized merchant key.
        cleaned_description: human-readable cleaned description.
        session: optional SQLAlchemy Session for cache operations.

    Returns:
        CategoryResult with tier, method, confidence, status, reason.
    """
    # ---- Tier 0: Cache ----
    try:
        result = tier0_cache.lookup_cache(merchant_key, session)
        if result and result.is_accepted():
            return result
    except Exception as exc:
        logger.error("Tier 0 error for '%s': %s", merchant_key, str(exc)[:200])

    # ---- Tier 1: TF-IDF + LR ----
    try:
        result = tier1_classifier.classify(merchant_key)
        if result and result.is_accepted(ACCEPT_THRESHOLD):
            _maybe_write_cache(merchant_key, cleaned_description, result, session)
            return result
    except Exception as exc:
        logger.error("Tier 1 error for '%s': %s", merchant_key, str(exc)[:200])

    # ---- Tier 2: Dictionary ----
    try:
        result = tier2_dictionary.classify(merchant_key)
        if result:
            if result.status == "categorized" and result.confidence >= ACCEPT_THRESHOLD:
                _maybe_write_cache(merchant_key, cleaned_description, result, session)
                return result
            elif result.status == "needs_review":
                # Hold as best candidate but keep trying higher tiers first
                # (dictionary needs_review has lower priority than a confident exact match below)
                # Return this as the final result if no better tier finds anything
                pass
            else:
                # Lower confidence categorized — return
                _maybe_write_cache(merchant_key, cleaned_description, result, session)
                return result
        best_candidate = result
    except Exception as exc:
        logger.error("Tier 2 error for '%s': %s", merchant_key, str(exc)[:200])
        best_candidate = None

    # ---- Tier 3: Fuzzy ----
    try:
        result = tier3_fuzzy.classify(merchant_key)
        if result and result.status == "categorized" and result.confidence >= 0.7:
            _maybe_write_cache(merchant_key, cleaned_description, result, session)
            return result
        if result and (best_candidate is None or result.confidence > best_candidate.confidence):
            best_candidate = result
    except Exception as exc:
        logger.error("Tier 3 error for '%s': %s", merchant_key, str(exc)[:200])

    # ---- Tier 4: Embeddings ----
    try:
        result = tier4_embedding.classify(merchant_key)
        if result and result.status == "categorized" and result.confidence >= 0.7:
            _maybe_write_cache(merchant_key, cleaned_description, result, session)
            return result
        if result and (best_candidate is None or result.confidence > best_candidate.confidence):
            best_candidate = result
    except Exception as exc:
        logger.error("Tier 4 error for '%s': %s", merchant_key, str(exc)[:200])

    # ---- Tier 5: LLM ----
    try:
        result = tier5_llm.classify(merchant_key)
        if result and (best_candidate is None or result.confidence > best_candidate.confidence):
            best_candidate = result
    except Exception as exc:
        logger.error("Tier 5 error for '%s': %s", merchant_key, str(exc)[:200])

    # If we have a needs_review or low-confidence candidate, return it
    if best_candidate:
        return best_candidate

    # ---- Unclassified ----
    return CategoryResult(
        category="other_unclassified",
        subcategory=None,
        merchant_name=None,
        merchant_key=merchant_key,
        tier=None,
        method="none",
        confidence=0.0,
        status="unclassified",
        reason="no_matching_tier",
    )


def _maybe_write_cache(
    merchant_key: str,
    cleaned_description: str,
    result: CategoryResult,
    session,
) -> None:
    """Write to cache only if session is available and result is confident."""
    if session is None or not result.is_valid_category():
        return
    try:
        review_status = "auto" if result.confidence >= ACCEPT_THRESHOLD else "needs_review"
        tier0_cache.write_cache(
            merchant_key, cleaned_description, result, session, review_status
        )
    except Exception as exc:
        logger.warning("Cache write skipped: %s", str(exc)[:200])


def categorize_dataframe(df, session=None):
    """
    Apply categorization pipeline to every row in a DataFrame.
    Adds: category, subcategory, category_status, categorization_tier,
          categorization_method, categorization_confidence columns.
    Returns the modified DataFrame.
    """
    import pandas as pd

    df = df.copy()
    results = []
    for _, row in df.iterrows():
        mk = row.get("merchant_key", "") or ""
        cd = row.get("cleaned_description", "") or ""
        try:
            res = categorize_merchant(mk, cd, session)
        except Exception as exc:
            logger.error("Categorization error: %s", str(exc)[:200])
            res = CategoryResult(
                category="other_unclassified",
                subcategory=None,
                merchant_name=None,
                merchant_key=mk,
                tier=None,
                method="error",
                confidence=0.0,
                status="unclassified",
                reason=f"error:{str(exc)[:100]}",
            )
        results.append(res)

    df["category"] = [r.category for r in results]
    df["subcategory"] = [r.subcategory for r in results]
    df["category_status"] = [r.status for r in results]
    df["categorization_tier"] = [r.tier for r in results]
    df["categorization_method"] = [r.method for r in results]
    df["categorization_confidence"] = [r.confidence for r in results]

    return df
