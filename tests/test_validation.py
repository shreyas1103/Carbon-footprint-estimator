"""
tests/test_validation.py
Tests for utils/validation.py — CSV header normalization,
sensitive column rejection, row-level validation.
"""
import io
import pandas as pd
import pytest
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.validation import validate_dataframe, normalize_header, TransactionRow


# ---------------------------------------------------------------------------
# Header normalization
# ---------------------------------------------------------------------------

def test_normalize_header_strips_whitespace():
    assert normalize_header("  Date  ") == "date"


def test_normalize_header_collapses_spaces():
    assert normalize_header("transaction date") == "transaction_date"


def test_normalize_header_lowercases():
    assert normalize_header("Amount") == "amount"


# ---------------------------------------------------------------------------
# Valid CSV
# ---------------------------------------------------------------------------

def test_valid_csv_passes():
    df = pd.DataFrame({
        "date": ["2024-01-05"],
        "description": ["Electricity Bill"],
        "amount": ["1200.00"],
    })
    result = validate_dataframe(df)
    assert result.can_proceed
    assert result.valid_count == 1
    assert result.invalid_count == 0


def test_valid_csv_with_optional_columns():
    df = pd.DataFrame({
        "date": ["2024-01-05"],
        "description": ["Electricity Bill"],
        "amount": ["1200.00"],
        "currency": ["INR"],
        "payment_method": ["UPI"],
    })
    result = validate_dataframe(df)
    assert result.can_proceed


# ---------------------------------------------------------------------------
# Missing required column
# ---------------------------------------------------------------------------

def test_missing_amount_column():
    df = pd.DataFrame({
        "date": ["2024-01-05"],
        "description": ["Electricity Bill"],
    })
    result = validate_dataframe(df)
    assert not result.can_proceed
    assert any("amount" in e.lower() for e in result.errors)


def test_missing_description_column():
    df = pd.DataFrame({
        "date": ["2024-01-05"],
        "amount": ["1200.00"],
    })
    result = validate_dataframe(df)
    assert not result.can_proceed


def test_missing_date_column():
    df = pd.DataFrame({
        "description": ["Electricity Bill"],
        "amount": ["1200.00"],
    })
    result = validate_dataframe(df)
    assert not result.can_proceed


# ---------------------------------------------------------------------------
# Header whitespace/case normalization
# ---------------------------------------------------------------------------

def test_header_case_insensitive():
    df = pd.DataFrame({
        "Date": ["2024-01-05"],
        "Description": ["Electricity Bill"],
        "Amount": ["1200.00"],
    })
    result = validate_dataframe(df)
    assert result.can_proceed, result.errors


def test_header_whitespace_normalized():
    df = pd.DataFrame({
        " date ": ["2024-01-05"],
        " description ": ["Electricity Bill"],
        " amount ": ["1200.00"],
    })
    result = validate_dataframe(df)
    assert result.can_proceed, result.errors


# ---------------------------------------------------------------------------
# Sensitive column rejection
# ---------------------------------------------------------------------------

def test_sensitive_account_number_rejected():
    df = pd.DataFrame({
        "date": ["2024-01-05"],
        "description": ["Electricity Bill"],
        "amount": ["1200.00"],
        "account_number": ["XXXX1234"],
    })
    result = validate_dataframe(df)
    assert not result.can_proceed
    assert any("sensitive" in e.lower() or "account" in e.lower() for e in result.errors)


def test_sensitive_card_number_rejected():
    df = pd.DataFrame({
        "date": ["2024-01-05"],
        "description": ["Electricity Bill"],
        "amount": ["1200.00"],
        "card_number": ["XXXX1234"],
    })
    result = validate_dataframe(df)
    assert not result.can_proceed


def test_sensitive_ifsc_rejected():
    df = pd.DataFrame({
        "date": ["2024-01-05"],
        "description": ["Electricity Bill"],
        "amount": ["1200.00"],
        "ifsc": ["HDFC0001234"],
    })
    result = validate_dataframe(df)
    assert not result.can_proceed


def test_sensitive_upi_id_rejected():
    df = pd.DataFrame({
        "date": ["2024-01-05"],
        "description": ["Electricity Bill"],
        "amount": ["1200.00"],
        "upi_id": ["user@okaxis"],
    })
    result = validate_dataframe(df)
    assert not result.can_proceed


def test_sensitive_values_not_echoed_in_errors():
    """Sensitive cell VALUES must never appear in error messages."""
    df = pd.DataFrame({
        "date": ["2024-01-05"],
        "description": ["Electricity Bill"],
        "amount": ["1200.00"],
        "account_number": ["SECRET123456789"],
    })
    result = validate_dataframe(df)
    for err in result.errors + result.warnings:
        assert "SECRET123456789" not in err


# ---------------------------------------------------------------------------
# Empty file / only headers
# ---------------------------------------------------------------------------

def test_empty_dataframe():
    df = pd.DataFrame()
    result = validate_dataframe(df)
    assert not result.can_proceed


def test_headers_only():
    df = pd.DataFrame(columns=["date", "description", "amount"])
    result = validate_dataframe(df)
    assert not result.can_proceed


# ---------------------------------------------------------------------------
# Row-level validation
# ---------------------------------------------------------------------------

def test_invalid_date_row():
    df = pd.DataFrame({
        "date": ["not-a-date"],
        "description": ["Electricity"],
        "amount": ["1200.00"],
    })
    result = validate_dataframe(df)
    assert result.invalid_count >= 1


def test_blank_description_row():
    df = pd.DataFrame({
        "date": ["2024-01-05"],
        "description": ["   "],
        "amount": ["1200.00"],
    })
    result = validate_dataframe(df)
    assert result.invalid_count >= 1


def test_nonnumeric_amount_row():
    df = pd.DataFrame({
        "date": ["2024-01-05"],
        "description": ["Electricity"],
        "amount": ["not-a-number"],
    })
    result = validate_dataframe(df)
    assert result.invalid_count >= 1


def test_nan_amount_row():
    df = pd.DataFrame({
        "date": ["2024-01-05"],
        "description": ["Electricity"],
        "amount": [float("nan")],
    })
    result = validate_dataframe(df)
    assert result.invalid_count >= 1


def test_negative_amount_is_valid_row():
    """Negative amounts (refunds) are valid rows; they get excluded_refund status in emissions."""
    df = pd.DataFrame({
        "date": ["2024-01-05"],
        "description": ["Refund from Amazon"],
        "amount": ["-500.00"],
    })
    result = validate_dataframe(df)
    # Negative amounts should pass validation (not be invalid rows)
    assert result.valid_count >= 1


def test_duplicate_headers():
    # Create a DataFrame with genuinely duplicate column names using numpy/io trick
    import io
    csv_content = b"date,description,amount,date\n2024-01-05,Electricity,1200.00,2024-01-05\n"
    df_dup = pd.read_csv(io.BytesIO(csv_content), dtype=str)
    # pandas auto-renames duplicates to "date.1" so we manually set them
    df_dup.columns = ["date", "description", "amount", "date"]  # type: ignore[assignment]
    result = validate_dataframe(df_dup)
    assert not result.can_proceed


# ---------------------------------------------------------------------------
# Non-INR currency warning
# ---------------------------------------------------------------------------

def test_non_inr_currency_triggers_warning():
    df = pd.DataFrame({
        "date": ["2024-01-05"],
        "description": ["Amazon Purchase"],
        "amount": ["50.00"],
        "currency": ["USD"],
    })
    result = validate_dataframe(df)
    assert any("usd" in w.lower() or "currency" in w.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# Pydantic strict model (Addendum B)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(TransactionRow is None, reason="pydantic not installed")
def test_pydantic_rejects_extra_fields():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        TransactionRow(
            date="2024-01-05",
            description="Electricity",
            amount=1200.0,
            account_number="12345",  # type: ignore
        )


@pytest.mark.skipif(TransactionRow is None, reason="pydantic not installed")
def test_pydantic_accepts_valid_row():
    from datetime import date
    row = TransactionRow(
        date=date(2024, 1, 5),
        description="Electricity Bill",
        amount=1200.0,
        currency="INR",
    )
    assert row.description == "Electricity Bill"


@pytest.mark.skipif(TransactionRow is None, reason="pydantic not installed")
def test_pydantic_rejects_blank_description():
    from pydantic import ValidationError
    from datetime import date
    with pytest.raises(ValidationError):
        TransactionRow(date=date(2024, 1, 5), description="   ", amount=1200.0)
