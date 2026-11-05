import pandas as pd
import re
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "training_data_original.csv"
OUTPUT_FILE = BASE_DIR / "training_data.csv"
REVIEW_FILE = BASE_DIR / "training_data_review.csv"

df = pd.read_csv(INPUT_FILE)

# Normalize descriptions
df["transaction_description"] = (
    df["transaction_description"]
    .fillna("")
    .astype(str)
    .str.lower()
    .str.strip()
)

df["category"] = df["category"].str.strip()

def classify_transaction(description, original_category):

    text = description.lower()

    # Apparel
    if original_category == "Apparel":
        return "shopping.clothing"

    # Electronics
    if original_category == "Electronics":
        return "shopping.electronics"

    # Entertainment
    if original_category == "Entertainment":
        return "entertainment"

    # Healthcare
    if original_category == "Healthcare":
        return "healthcare"

    # Grocery
    if original_category == "Grocery":
        return "food.basic_grocery"

    # Food
    if original_category == "Food":
        return "food.restaurant_delivery"

    # Fuel
    if original_category == "Fuel":
        if re.search(r"\bdiesel\b", text):
            return "transport_fuel.diesel"
        if re.search(r"\bpetrol\b|\biocl\b|\bindian oil\b|\bbpcl\b|\bhpcl\b|\bnayara\b|\bshell\b", text):
            return "transport_fuel.petrol"

        return "transport_fuel.unknown"

    # Transport
    if original_category == "Transport":

        if re.search(r"uber|ola|rapido|cab|taxi|blusmart|auto ride", text):
            return "transport.taxi_rideshare"

        if re.search(r"metro|bus|railway|irctc|train|abhibus", text):
            return "transport.public_transit"

        return None

    # Utilities
    if original_category == "Utilities":

        if re.search(r"msedcl|bescom|tata power|electricity|power bill", text):
            return "utilities.electricity"

        if re.search(r"airtel|internet|broadband|jio fiber|dth recharge", text):
            return "telecom_internet"

        return None

    # Travel
    if original_category == "Travel":

        if re.search(r"flight|airline|air india|indigo|spicejet|vistara", text):
            return "transport.air_travel"

        return None

    return None


df["merchant_key"] = df["transaction_description"].str.upper()

df["canonical_category"] = df.apply(
    lambda row: classify_transaction(
        row["transaction_description"],
        row["category"]
    ),
    axis=1
)

# Separate confidently mapped rows and rows requiring review
valid_df = df[df["canonical_category"].notna()].copy()
review_df = df[df["canonical_category"].isna()].copy()

# Remove exact duplicate examples
valid_df = valid_df.drop_duplicates(
    subset=["merchant_key", "canonical_category"]
)

# Final training dataset
training_df = valid_df[
    ["merchant_key", "canonical_category"]
].rename(columns={"canonical_category": "category"})

training_df.to_csv(OUTPUT_FILE, index=False)

review_df.to_csv(REVIEW_FILE, index=False)

print("\n========== DATASET PREPARATION ==========")

print("Original records:", len(df))
print("Mapped records:", len(training_df))
print("Records requiring review:", len(review_df))

print("\nCanonical category distribution:")
print(training_df["category"].value_counts())

print("\nTraining dataset saved:", OUTPUT_FILE)
print("Review dataset saved:", REVIEW_FILE)

print("=========================================")