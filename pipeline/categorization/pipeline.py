"""
pipeline/categorization/pipeline.py
Orchestrates all categorization tiers in priority order:
  0 → cache
  2 → dictionary (exact/substring match — reliable rules first)
  1 → TF-IDF/LR classifier
  3 → fuzzy
  4 → embeddings (optional)
  5 → LLM (optional)
  → unclassified

Rationale for ordering Tier 2 before Tier 1:
  Dictionary rules are curated and deterministic.  An ML classifier
  (Logistic Regression) always returns *some* class — even for inputs
  far outside its training distribution — often with misleadingly high
  confidence.  Running dictionary lookup first ensures that known
  merchants (e.g. "INDANE GAS") receive the correct category before the
  ML model has a chance to misclassify them.

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
    Run the full multi-tier categorization pipeline for a single merchant.

    Execution order: 0 (cache) → 2 (dictionary) → 1 (ML) → 3 (fuzzy)
                     → 4 (embeddings) → 5 (LLM) → unclassified.

    Args:
        merchant_key: normalized merchant key.
        cleaned_description: human-readable cleaned description.
        session: optional SQLAlchemy Session for cache operations.

    Returns:
        CategoryResult with tier, method, confidence, status, reason.
    """
    logger.debug("Categorizing merchant_key='%s'", merchant_key[:80])

    # ---- Tier 0: Cache ----
    try:
        result = tier0_cache.lookup_cache(merchant_key, session)
        if result and result.is_accepted():
            logger.info(
                "Tier 0 cache hit for '%s' → %s (confidence=%.2f)",
                merchant_key[:50], result.category, result.confidence,
            )
            return result
        if result:
            logger.debug("Tier 0 cache entry exists but not accepted (status=%s)", result.status)
    except Exception as exc:
        logger.error("Tier 0 error for '%s': %s", merchant_key[:50], str(exc)[:200])

    # ---- Tier 2: Dictionary (moved BEFORE Tier 1) ----
    best_candidate: Optional[CategoryResult] = None
    try:
        result = tier2_dictionary.classify(merchant_key)
        if result:
            if result.status == "categorized" and result.confidence >= ACCEPT_THRESHOLD:
                logger.info(
                    "Tier 2 dictionary match for '%s' → %s (confidence=%.2f, reason=%s)",
                    merchant_key[:50], result.category, result.confidence, result.reason,
                )
                _maybe_write_cache(merchant_key, cleaned_description, result, session)
                return result
            elif result.status == "categorized":
                # Lower confidence dictionary match — still return it
                # (dictionary matches are curated, so even lower confidence is trustworthy)
                logger.info(
                    "Tier 2 dictionary match (lower confidence) for '%s' → %s (confidence=%.2f)",
                    merchant_key[:50], result.category, result.confidence,
                )
                _maybe_write_cache(merchant_key, cleaned_description, result, session)
                return result
            elif result.status == "needs_review":
                # Hold as best candidate — keep trying subsequent tiers
                logger.debug(
                    "Tier 2 needs_review for '%s' → %s (holding as candidate)",
                    merchant_key[:50], result.category,
                )
                best_candidate = result
    except Exception as exc:
        logger.error("Tier 2 error for '%s': %s", merchant_key[:50], str(exc)[:200])

    # ---- Tier 1: TF-IDF + LR ----
    try:
        result = tier1_classifier.classify(merchant_key)
        if result and result.is_accepted(ACCEPT_THRESHOLD):
            # If Tier 2 already flagged this as ambiguous (needs_review),
            # ML must NOT override it.  Dictionary ambiguity is semantic
            # (e.g. "bus" = school bus vs public transit, "hotel" = restaurant
            # vs accommodation) and character n-gram agreement does not
            # resolve the underlying ambiguity.  Only a human reviewer or
            # additional context can resolve dictionary-flagged ambiguity.
            if best_candidate and best_candidate.status == "needs_review":
                logger.debug(
                    "Tier 1 ML has result for '%s' → %s (confidence=%.2f) but "
                    "Tier 2 flagged needs_review. Preserving dictionary ambiguity.",
                    merchant_key[:50], result.category, result.confidence,
                )
                # Don't override — keep the dictionary's needs_review
            else:
                # No Tier 2 ambiguity — accept ML result normally
                logger.info(
                    "Tier 1 ML classifier for '%s' → %s (confidence=%.2f)",
                    merchant_key[:50], result.category, result.confidence,
                )
                _maybe_write_cache(merchant_key, cleaned_description, result, session)
                return result
        elif result:
            logger.debug(
                "Tier 1 returned '%s' (confidence=%.2f) but below threshold or not accepted",
                result.category, result.confidence,
            )
    except Exception as exc:
        logger.error("Tier 1 error for '%s': %s", merchant_key[:50], str(exc)[:200])

    # ---- Tier 3: Fuzzy ----
    try:
        result = tier3_fuzzy.classify(merchant_key)
        if result and result.status == "categorized" and result.confidence >= 0.7:
            logger.info(
                "Tier 3 fuzzy match for '%s' → %s (confidence=%.2f)",
                merchant_key[:50], result.category, result.confidence,
            )
            _maybe_write_cache(merchant_key, cleaned_description, result, session)
            return result
        if result and (best_candidate is None or result.confidence > best_candidate.confidence):
            best_candidate = result
    except Exception as exc:
        logger.error("Tier 3 error for '%s': %s", merchant_key[:50], str(exc)[:200])

    # ---- Tier 4: Embeddings ----
    try:
        result = tier4_embedding.classify(merchant_key)
        if result and result.status == "categorized" and result.confidence >= 0.7:
            logger.info(
                "Tier 4 embedding match for '%s' → %s (confidence=%.2f)",
                merchant_key[:50], result.category, result.confidence,
            )
            _maybe_write_cache(merchant_key, cleaned_description, result, session)
            return result
        if result and (best_candidate is None or result.confidence > best_candidate.confidence):
            best_candidate = result
    except Exception as exc:
        logger.error("Tier 4 error for '%s': %s", merchant_key[:50], str(exc)[:200])

    # ---- Tier 5: LLM ----
    try:
        result = tier5_llm.classify(merchant_key)
        if result and (best_candidate is None or result.confidence > best_candidate.confidence):
            best_candidate = result
    except Exception as exc:
        logger.error("Tier 5 error for '%s': %s", merchant_key[:50], str(exc)[:200])

    # If we have a needs_review or low-confidence candidate, return it
    if best_candidate:
        logger.info(
            "Returning best candidate for '%s' → %s (status=%s, tier=%s, confidence=%.2f)",
            merchant_key[:50], best_candidate.category, best_candidate.status,
            best_candidate.tier, best_candidate.confidence,
        )
        return best_candidate

    # ---- Unclassified ----
    logger.info("No tier matched for '%s' → other_unclassified", merchant_key[:50])
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
