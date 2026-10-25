"""
pipeline/categorization/tier1_classifier.py
Tier 1: TF-IDF + Logistic Regression classifier.
Loads trained model artifacts lazily from models/.
If artifacts are missing or confidence below threshold, falls through.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from pipeline.categorization.categories import CANONICAL_CATEGORIES, CategoryResult

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")
VECTORIZER_PATH = os.path.join(MODEL_DIR, "tfidf_vectorizer.joblib")
CLASSIFIER_PATH = os.path.join(MODEL_DIR, "lr_classifier.joblib")

_VECTORIZER = None
_CLASSIFIER = None
_LOADED = False

DEFAULT_CONFIDENCE_THRESHOLD = 0.80


def _load_model() -> bool:
    """Load vectorizer and classifier lazily. Returns True if both are available."""
    global _VECTORIZER, _CLASSIFIER, _LOADED
    if _LOADED:
        return _VECTORIZER is not None and _CLASSIFIER is not None
    _LOADED = True

    if not (os.path.exists(VECTORIZER_PATH) and os.path.exists(CLASSIFIER_PATH)):
        logger.info("Tier 1 model artifacts not found. Tier 1 disabled.")
        return False

    try:
        import joblib
        _VECTORIZER = joblib.load(VECTORIZER_PATH)
        _CLASSIFIER = joblib.load(CLASSIFIER_PATH)
        logger.info("Tier 1 TF-IDF + LR model loaded from %s", MODEL_DIR)
        return True
    except Exception as exc:
        logger.warning("Failed to load Tier 1 model: %s", str(exc)[:200])
        _VECTORIZER = None
        _CLASSIFIER = None
        return False


def classify(
    merchant_key: str,
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> Optional[CategoryResult]:
    """
    Classify a merchant_key using TF-IDF + Logistic Regression.
    Returns None if model unavailable, confidence below threshold, or unknown category.
    """
    if not _load_model():
        return None

    try:
        import numpy as np
        features = _VECTORIZER.transform([merchant_key])
        predicted_label = _CLASSIFIER.predict(features)[0]
        probabilities = _CLASSIFIER.predict_proba(features)[0]
        confidence = float(np.max(probabilities))

        if confidence < threshold:
            return None

        if predicted_label not in CANONICAL_CATEGORIES:
            logger.warning("Tier 1 predicted unknown category '%s'.", predicted_label)
            return None

        return CategoryResult(
            category=predicted_label,
            subcategory=None,
            merchant_name=None,
            merchant_key=merchant_key,
            tier=1,
            method="tfidf_lr",
            confidence=confidence,
            status="categorized",
            reason=f"classifier_confidence_{confidence:.2f}",
        )

    except Exception as exc:
        logger.error("Tier 1 classify error: %s", str(exc)[:200])
        return None
