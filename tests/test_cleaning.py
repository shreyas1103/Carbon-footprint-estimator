import pandas as pd

from pipeline.cleaning import clean_transactions


def test_description_cleaning():

    df = pd.DataFrame({
        "date": ["2026-08-01"],
        "description": ["  SWIGGY  "],
        "amount": ["450"]
    })

    result = clean_transactions(df)

    assert result["description"].iloc[0] == "swiggy"


def test_amount_cleaning():

    df = pd.DataFrame({
        "date": ["2026-08-01"],
        "description": ["Swiggy"],
        "amount": ["₹1,200"]
    })

    result = clean_transactions(df)

    assert result["amount"].iloc[0] == 1200


def test_duplicate_removal():

    df = pd.DataFrame({
        "date": ["2026-08-01", "2026-08-01"],
        "description": ["Swiggy", "Swiggy"],
        "amount": [450, 450]
    })

    result = clean_transactions(df)

    assert len(result) == 1


def test_missing_value_removal():

    df = pd.DataFrame({
        "date": ["2026-08-01", "2026-08-02"],
        "description": ["Swiggy", None],
        "amount": [450, 250]
    })

    result = clean_transactions(df)

    assert len(result) == 1
