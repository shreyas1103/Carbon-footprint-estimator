"""
pipeline/categorization/tier0_cache.py
Tier 0: Merchant cache lookup via database.
Cache hits skip all subsequent tiers — but only if the cached result
is still consistent with the current dictionary rules.

Auto-classified entries are validated against Tier 2 dictionary before
being trusted.  User-approved entries are always trusted.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from pipeline.categorization.categories import CANONICAL_CATEGORIES, CategoryResult

logger = logging.getLogger(__name__)


def lookup_cache(merchant_key: str, session) -> Optional[CategoryResult]:
    """
    Look up a merchant_key in the merchant_cache table.
    Returns a CategoryResult if a valid entry is found, else None.

    Validation rules:
    - 'approved' entries (human-reviewed) are always trusted.
    - 'auto' entries are cross-checked against the dictionary:
      if the dictionary now returns a *different* confident category,
      the stale cache entry is invalidated and None is returned so the
      pipeline re-classifies using the current tier order.
    - Invalid categories are skipped.

    Args:
        merchant_key: normalized merchant key (already cleaned/casefolded).
        session: SQLAlchemy Session (may be None if DB is unavailable).
    """
    if session is None or not merchant_key:
        return None

    try:
        from database.models import MerchantCache
        entry = (
            session.query(MerchantCache)
            .filter(
                MerchantCache.merchant_key == merchant_key,
                MerchantCache.review_status.in_(["approved", "auto"]),
            )
            .first()
        )
        if entry is None:
            return None

        # Validate category
        if entry.category not in CANONICAL_CATEGORIES:
            logger.warning(
                "Cache entry for '%s' has invalid category '%s'; skipping.",
                merchant_key,
                entry.category,
            )
            return None

        # --- Stale-cache guard for auto-classified entries ---
        # If the dictionary now disagrees with the cached category,
        # the cache is stale (likely from the old pipeline order where
        # Tier 1 ML ran before dictionary).  Invalidate it.
        if entry.review_status == "auto":
            from pipeline.categorization import tier2_dictionary
            dict_result = tier2_dictionary.classify(merchant_key)
            if (
                dict_result is not None
                and dict_result.status == "categorized"
                and dict_result.category != entry.category
            ):
                logger.warning(
                    "Stale cache for '%s': cached=%s (tier=%s) but dictionary says %s. "
                    "Invalidating auto entry so pipeline re-classifies.",
                    merchant_key, entry.category, entry.tier,
                    dict_result.category,
                )
                # Demote the stale entry so it won't be returned next time
                try:
                    entry.review_status = "stale"
                    session.flush()
                except Exception:
                    session.rollback()
                return None

        # Update last_used — use a savepoint so a failure here doesn't poison
        # the parent session (e.g. if the table schema changed).
        try:
            entry.last_used = datetime.utcnow()
            session.flush()  # flush without committing — caller commits
        except Exception:
            session.rollback()  # rollback only this sub-operation

        return CategoryResult(
            category=entry.category,
            subcategory=entry.subcategory,
            merchant_name=entry.clean_merchant,
            merchant_key=merchant_key,
            tier=0,
            method="cache",
            confidence=float(entry.confidence),
            status="categorized",
            reason="merchant_cache_hit",
        )

    except Exception as exc:
        logger.warning("Cache lookup error for '%s': %s", merchant_key, str(exc)[:100])
        # Rollback so the session stays usable for subsequent queries
        try:
            session.rollback()
        except Exception:
            pass
        return None


def write_cache(
    merchant_key: str,
    clean_merchant: str,
    result: CategoryResult,
    session,
    review_status: str = "auto",
) -> bool:
    """
    Write or update a merchant cache entry.
    Low-confidence or needs_review results should be written with
    review_status='needs_review'.

    Never promotes an unchecked LLM result to 'approved' automatically.
    """

    if session is None or not merchant_key:
        return False

    if result.category not in CANONICAL_CATEGORIES:
        return False

    try:
        from database.models import MerchantCache

        now = datetime.now(timezone.utc)

        existing = (
            session.query(MerchantCache)
            .filter(MerchantCache.merchant_key == merchant_key)
            .first()
        )

        if existing:
            # Never downgrade a human-approved entry
            if existing.review_status == "approved" and review_status == "auto":
                logger.debug(
                    "Cache write skipped for '%s': existing entry is human-approved.",
                    merchant_key,
                )
                return False

            existing.raw_merchant = clean_merchant
            existing.category = result.category
            existing.subcategory = result.subcategory
            existing.confidence = result.confidence
            existing.source = result.method
            existing.tier = result.tier
            existing.review_status = review_status
            existing.last_used = now
            existing.updated_at = now

        else:
            new_entry = MerchantCache(
                raw_merchant=clean_merchant,
                merchant_key=merchant_key,
                clean_merchant=clean_merchant,
                category=result.category,
                subcategory=result.subcategory,
                confidence=result.confidence,
                source=result.method,
                tier=result.tier,
                review_status=review_status,

                # Explicit timestamps
                created_at=now,
                last_used=now,
                updated_at=now,
            )

            session.add(new_entry)

        session.commit()
        return True

    except Exception as exc:
        session.rollback()

        logger.error(
            "Cache write error for '%s': %s",
            merchant_key,
            str(exc)[:200],
        )

        return False