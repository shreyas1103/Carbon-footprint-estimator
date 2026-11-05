import joblib
import os
import sys

# Project root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODEL_DIR = os.path.join(BASE_DIR, "models")

VECTORIZER_PATH = os.path.join(
    MODEL_DIR, "tfidf_vectorizer.joblib"
)

CLASSIFIER_PATH = os.path.join(
    MODEL_DIR, "lr_classifier.joblib"
)

# Load trained models
vectorizer = joblib.load(VECTORIZER_PATH)
classifier = joblib.load(CLASSIFIER_PATH)

# Test descriptions (not necessarily present in training data)
test_transactions = [
    "SWIGGY ORDER 7821",
    "BIGBASKET PURCHASE",
    "HP PETROL PUMP",
    "IRCTC TICKET",
    "NETFLIX SUBSCRIPTION",
    "APOLLO PHARMACY",
    "JIO FIBER BILL",
    "UBER RIDE PAYMENT",
    "AMAZON ELECTRONICS STORE",
    "PVR CINEMAS BOOKING",
    "INDANE GAS BOOKING",
    "UNKNOWN MERCHANT 83921",
    "RANDOM PAYMENT XYZ 12345",
]

# Predict categories
X = vectorizer.transform(test_transactions)

predictions = classifier.predict(X)
probabilities = classifier.predict_proba(X)

print("\n========== TIER 1 MODEL TESTING ==========\n")

for i, description in enumerate(test_transactions):

    predicted_category = predictions[i]
    confidence = max(probabilities[i])

    print(f"Transaction : {description}")
    print(f"Category    : {predicted_category}")
    print(f"Confidence  : {confidence:.4f}")
    print("-" * 55)

print("\nTesting completed!")