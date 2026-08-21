
import pandas as pd


REQUIRED_COLUMNS = ["date", "description", "amount"]


def validate_csv(df):

    errors = []

    # Check empty file
    if df.empty:
        errors.append("The CSV file is empty.")
        return errors

    # Check required columns
    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        errors.append(
            "Missing required columns: "
            + ", ".join(missing_columns)
        )

        return errors

    # Check date
    dates = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    if dates.isna().any():
        errors.append(
            "The 'date' column contains invalid dates."
        )

    # Check amount
    
    amounts = (
       df["amount"]
       .astype("string")
       .str.replace("₹", "", regex=False)
       .str.replace(",", "", regex=False)
       .str.strip()
     )

    amounts = pd.to_numeric(
        amounts,
        errors="coerce"
     )

    if amounts.isna().any():
     errors.append(
        "The 'amount' column must contain numeric values."
    )
    # Check description
    if df["description"].isna().any():
        errors.append(
            "The 'description' column contains empty values."
        )

    return errors