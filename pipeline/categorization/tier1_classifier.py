"""
pipeline/categorization/tier1_classifier.py
Tier 1: TF-IDF + Logistic Regression classifier.
Loads trained model artifacts lazily from models/.
If artifacts are missing or confidence below threshold, falls through.

Important: Logistic Regression always returns one of its trained classes,
even for inputs that are completely unrelated to any training example.
A high probability does NOT guarantee correctness.  This tier should only
be reached after the curated dictionary (Tier 2) has failed to match.

Out-of-distribution detection:
  Uses TF-IDF vocabulary coverage — the fraction of the input's character
  n-grams that appear in the training vocabulary.  If coverage falls below
  a minimum threshold, the prediction is considered unreliable regardless
  of the model's confidence score.
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

# Minimum fraction of input n-grams that must appear in the TF-IDF vocabulary
# for a prediction to be considered in-distribution.
# Below this threshold, the input is considered out-of-distribution and
# the prediction is rejected regardless of confidence.
MIN_VOCABULARY_COVERAGE = 0.10


def _load_model() -> bool:
    """Load vectorizer and classifier lazily. Returns True if both are available."""
    global _VECTORIZER, _CLASSIFIER, _LOADED
    if _LOADED:
        return _VECTORIZER is not None and _CLASSIFIER is not None
    _LOADED = True

    if not (os.path.exists(VECTORIZER_PATH) and os.path.exists(CLASSIFIER_PATH)):
        logger.info("Tier 1 model artifacts not found at %s. Tier 1 disabled.", MODEL_DIR)
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


def _vocabulary_coverage(merchant_key: str) -> float:
    """
    Compute the fraction of character n-grams in merchant_key that exist
    in the TF-IDF vocabulary.

    Returns a float in [0.0, 1.0].
    - 1.0 means every n-gram in the input was seen during training.
    - 0.0 means none of the input's n-grams were in the vocabulary.

    This uses the vectorizer's built-in analyzer, which handles the same
    tokenization, lowercasing, and n-gram generation as during training.
    """
    if _VECTORIZER is None:
        return 0.0

    try:
        # The analyzer function generates the same n-grams used during fit
        analyzer = _VECTORIZER.build_analyzer()
        input_ngrams = analyzer(merchant_key)

        if not input_ngrams:
            return 0.0

        vocabulary = _VECTORIZER.vocabulary_
        known_count = sum(1 for ng in input_ngrams if ng in vocabulary)
        return known_count / len(input_ngrams)
    except Exception as exc:
        logger.debug("Vocabulary coverage check failed: %s", str(exc)[:100])
        return 1.0  # On error, don't reject — let confidence threshold decide


def classify(
    merchant_key: str,
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> Optional[CategoryResult]:
    """
    Classify a merchant_key using TF-IDF + Logistic Regression.

    Returns None if:
    - Model unavailable
    - Input is empty/invalid
    - Confidence below threshold
    - Predicted category not in CANONICAL_CATEGORIES
    - Input is out-of-distribution (low vocabulary coverage)
    """
    # Guard against empty / invalid input
    if not merchant_key or not merchant_key.strip():
        logger.debug("Tier 1 skipped: empty merchant_key")
        return None

    if not _load_model():
        return None

    try:
        import numpy as np
        features = _VECTORIZER.transform([merchant_key])
        predicted_label = _CLASSIFIER.predict(features)[0]
        probabilities = _CLASSIFIER.predict_proba(features)[0]
        confidence = float(np.max(probabilities))

        # --- Out-of-distribution check ---
        coverage = _vocabulary_coverage(merchant_key)
        logger.debug(
            "Tier 1 prediction for '%s': label='%s', confidence=%.4f, "
            "vocab_coverage=%.2f, threshold=%.2f",
            merchant_key[:50], predicted_label, confidence, coverage, threshold,
        )

        if coverage < MIN_VOCABULARY_COVERAGE:
            logger.info(
                "Tier 1 OOD rejection for '%s': vocab_coverage=%.2f < %.2f. "
                "Model predicted '%s' at %.2f%% but input is out-of-distribution.",
                merchant_key[:50], coverage, MIN_VOCABULARY_COVERAGE,
                predicted_label, confidence * 100,
            )
            return None

        if confidence < threshold:
            logger.debug(
                "Tier 1 rejected '%s': confidence %.4f < threshold %.2f",
                merchant_key[:50], confidence, threshold,
            )
            return None

        if predicted_label not in CANONICAL_CATEGORIES:
            logger.warning(
                "Tier 1 predicted non-canonical category '%s' for '%s'. Rejecting.",
                predicted_label, merchant_key[:50],
            )
            return None

        logger.debug(
            "Tier 1 accepted '%s' → %s (confidence=%.4f, vocab_coverage=%.2f)",
            merchant_key[:50], predicted_label, confidence, coverage,
        )
        return CategoryResult(
            category=predicted_label,
            subcategory=None,
            merchant_name=None,
            merchant_key=merchant_key,
            tier=1,
            method="tfidf_lr",
            confidence=confidence,
            status="categorized",
            reason=f"classifier_confidence_{confidence:.2f}_coverage_{coverage:.2f}",
        )

    except Exception as exc:
        logger.error("Tier 1 classify error for '%s': %s", merchant_key[:50], str(exc)[:200])
        return None
