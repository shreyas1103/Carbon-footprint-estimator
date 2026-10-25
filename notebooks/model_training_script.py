"""
notebooks/model_training_script.py
Standalone Python script version of the Tier 1 TF-IDF + Logistic Regression training.
Run from the project root: python notebooks/model_training_script.py

Requires labeled training data in notebooks/training_data.csv with columns:
  merchant_key, category

Saves:
  models/tfidf_vectorizer.joblib
  models/lr_classifier.joblib
"""
from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def train():
    import pandas as pd
    import joblib
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split, StratifiedKFold, cross_validate
    from sklearn.metrics import classification_report, confusion_matrix
    from sklearn.pipeline import Pipeline
    from pipeline.categorization.categories import CANONICAL_CATEGORIES

    data_path = os.path.join(os.path.dirname(__file__), "training_data.csv")
    if not os.path.exists(data_path):
        logger.error(
            "Training data not found at %s. "
            "Create a CSV with columns: merchant_key, category", data_path
        )
        return

    df = pd.read_csv(data_path)
    required = {"merchant_key", "category"}
    if not required.issubset(df.columns):
        logger.error("Training CSV must have columns: merchant_key, category")
        return

    # Validate categories
    invalid = set(df["category"].unique()) - CANONICAL_CATEGORIES
    if invalid:
        logger.warning("Removing rows with non-canonical categories: %s", invalid)
        df = df[df["category"].isin(CANONICAL_CATEGORIES)]

    df = df.dropna(subset=["merchant_key", "category"])
    logger.info("Training on %d examples across %d categories", len(df), df["category"].nunique())

    X = df["merchant_key"].astype(str).tolist()
    y = df["category"].tolist()

    # Check for rare classes
    class_counts = df["category"].value_counts()
    rare_classes = class_counts[class_counts < 3].index.tolist()
    if rare_classes:
        logger.warning("Classes with fewer than 3 examples (may affect stratification): %s", rare_classes)

    # Train/test split with stratification if possible
    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
    except ValueError:
        logger.warning("Stratified split failed (likely rare classes). Using random split.")
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

    # TF-IDF + LR pipeline
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4),
        max_features=50_000,
        sublinear_tf=True,
    )
    clf = LogisticRegression(
        max_iter=1000,
        C=5.0,
        class_weight="balanced",
        random_state=42,
    )

    X_train_vec = vectorizer.fit_transform(X_train)
    clf.fit(X_train_vec, y_train)

    # Evaluate
    X_test_vec = vectorizer.transform(X_test)
    y_pred = clf.predict(X_test_vec)

    print("\n=== Classification Report ===")
    print(classification_report(y_test, y_pred, zero_division=0))

    print("\n=== Confusion Matrix ===")
    labels = sorted(set(y_test))
    cm = confusion_matrix(y_test, y_pred, labels=labels)
    print(pd.DataFrame(cm, index=labels, columns=labels))

    # Save artifacts
    models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
    os.makedirs(models_dir, exist_ok=True)

    vec_path = os.path.join(models_dir, "tfidf_vectorizer.joblib")
    clf_path = os.path.join(models_dir, "lr_classifier.joblib")

    joblib.dump(vectorizer, vec_path)
    joblib.dump(clf, clf_path)

    logger.info("Saved vectorizer → %s", vec_path)
    logger.info("Saved classifier → %s", clf_path)
    logger.info("Training complete.")


if __name__ == "__main__":
    train()
