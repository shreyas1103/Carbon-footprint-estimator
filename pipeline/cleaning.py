import pandas as pd


def clean_transactions(df):
    """
    Clean transaction data before further processing.
    """

    # Make a copy so that the original DataFrame is not changed
    df = df.copy()

    # --------------------------------
    # 1. Clean column names
    # --------------------------------
    df.columns = df.columns.str.strip().str.lower()

    # --------------------------------
    # 2. Clean description
    # --------------------------------
    df["description"] = (
        df["description"]
        .astype("string")
        .str.strip()
        .str.lower()
    )

    # --------------------------------
    # 3. Clean amount
    # --------------------------------
    df["amount"] = (
        df["amount"]
        .astype("string")
        .str.replace("₹", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
    )

    df["amount"] = pd.to_numeric(
        df["amount"],
        errors="coerce"
    )

    # --------------------------------
    # 4. Clean date
    # --------------------------------
    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    # --------------------------------
    # 5. Remove rows with missing
    #    important information
    # --------------------------------
    df = df.dropna(
        subset=["date", "description", "amount"]
    )

    # --------------------------------
    # 6. Remove duplicate transactions
    # --------------------------------
    df = df.drop_duplicates()

    # Reset index after cleaning
    df = df.reset_index(drop=True)

    return df
