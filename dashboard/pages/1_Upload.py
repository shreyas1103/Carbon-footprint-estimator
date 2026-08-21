import sys
import os

# Add the main project folder to Python path
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../..")
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


import streamlit as st
import pandas as pd

from utils.validation import validate_csv
from pipeline.cleaning import clean_transactions

st.title("📂 Upload Transactions")

st.write(
    "Upload your bank transaction CSV file."
)

uploaded_file = st.file_uploader(
    "Choose a CSV file",
    type=["csv"]
)


if uploaded_file is not None:

    try:

        # Read CSV
        df = pd.read_csv(uploaded_file)

        # Validate CSV
        errors = validate_csv(df)

        if errors:

            st.error("❌ CSV validation failed.")

            for error in errors:
                st.warning(error)

        else:
           st.success("✅ CSV is valid!")

           # Clean the transaction data
           cleaned_df = clean_transactions(df)

           st.success("🧹 Transaction data cleaned successfully!")

           st.subheader("Cleaned Transaction Preview")

           st.dataframe(
             cleaned_df.head(10),
             use_container_width=True
           )

           st.info(
           f"Total cleaned transactions: {len(cleaned_df)}"
           )

    except Exception as e:

        st.error(
            f"Unable to read the CSV file: {e}"
        )