"""
tests/test_pdf_reader.py
Tests for utils/file_readers/pdf_reader.py — word-based extraction.
Uses a synthetic PDF generated via reportlab (must be installed).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd

from utils.file_readers.pdf_reader import (
    read_pdf,
    clean_money, is_money, parse_date,
    normalize_text, clean_description,
    find_headers, group_words_into_lines,
    create_column_ranges,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sample_pdf_bytes():
    """Generate a realistic text-based bank statement PDF."""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        import io
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        c.setFont("Courier", 9)

        # Header row
        c.drawString(40, 710, "Date")
        c.drawString(150, 710, "Description")
        c.drawString(380, 710, "Withdrawal")
        c.drawString(455, 710, "Deposit")
        c.drawString(530, 710, "Balance")

        rows = [
            ("05 Jan 24", "BESCOM ELECTRICITY BILL",  "1200.00", "",        "8800.00"),
            ("08 Jan 24", "HP GAS LPG REFILL",         "980.00",  "",        "7820.00"),
            ("10 Jan 24", "IOCL PETROL PUMP",           "2500.00", "",        "5320.00"),
            ("12 Jan 24", "BIGBASKET GROCERY",          "850.00",  "",        "4470.00"),
            ("18 Jan 24", "AMAZON REFUND CREDIT",       "",        "800.00",  "5270.00"),
            ("20 Jan 24", "MOTHER DAIRY MILK",          "320.00",  "",        "4950.00"),
        ]
        y = 690
        for row in rows:
            for x, val in zip([40, 150, 380, 455, 530], row):
                c.drawString(x, y, val)
            y -= 16

        c.save()
        buf.seek(0)
        return buf.read()
    except ImportError:
        pytest.skip("reportlab not installed — skipping PDF tests")


@pytest.fixture(scope="module")
def extraction_result(sample_pdf_bytes):
    return read_pdf(sample_pdf_bytes)


# ---------------------------------------------------------------------------
# ExtractionResult contract
# ---------------------------------------------------------------------------

def test_pdf_no_errors(extraction_result):
    assert extraction_result.errors == [], extraction_result.errors


def test_pdf_rows_extracted(extraction_result):
    assert extraction_result.rows_extracted >= 5


def test_pdf_dataframe_not_empty(extraction_result):
    assert not extraction_result.dataframe.empty


def test_pdf_required_columns(extraction_result):
    df = extraction_result.dataframe
    assert "date" in df.columns
    assert "description" in df.columns
    assert "amount" in df.columns


def test_pdf_source_parser(extraction_result):
    assert "pdf" in extraction_result.source_parser.lower()


# ---------------------------------------------------------------------------
# Content correctness
# ---------------------------------------------------------------------------

def test_pdf_dates_are_valid(extraction_result):
    df = extraction_result.dataframe
    dates = pd.to_datetime(df["date"], errors="coerce")
    assert dates.notna().all(), "Some dates could not be parsed"


def test_pdf_amounts_are_positive(extraction_result):
    df = extraction_result.dataframe
    assert (df["amount"] > 0).all(), "All amounts must be positive"


def test_pdf_descriptions_not_blank(extraction_result):
    df = extraction_result.dataframe
    assert (df["description"].str.strip() != "").all()


def test_pdf_electricity_found(extraction_result):
    df = extraction_result.dataframe
    found = df["description"].str.contains("ELECTRICITY|BESCOM", case=False, na=False)
    assert found.any(), "Electricity bill not found in extracted transactions"


def test_pdf_lpg_found(extraction_result):
    df = extraction_result.dataframe
    found = df["description"].str.contains("LPG|GAS", case=False, na=False)
    assert found.any()


def test_pdf_refund_credit_marked(extraction_result):
    """Refund rows must be marked 'credit' in payment_method."""
    df = extraction_result.dataframe
    if "payment_method" in df.columns:
        refund_rows = df[df["description"].str.contains("REFUND|CREDIT", case=False, na=False)]
        if not refund_rows.empty:
            assert (refund_rows["payment_method"] == "credit").any()


def test_pdf_no_balance_rows(extraction_result):
    """Balance-forward / total rows must not appear in output."""
    df = extraction_result.dataframe
    bad = df["description"].str.upper().isin(
        {"BALANCE FORWARD", "BALANCE B/F", "TOTAL", "OPENING BALANCE", "CLOSING BALANCE"}
    )
    assert not bad.any(), "Balance rows leaked into output"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

def test_empty_bytes_returns_error():
    result = read_pdf(b"")
    assert result.errors
    assert result.rows_extracted == 0


def test_non_pdf_bytes_returns_error():
    result = read_pdf(b"not a pdf at all %% garbage")
    # Should not crash, should return errors or empty
    assert result.rows_extracted == 0 or result.errors


def test_oversized_file_rejected():
    big = b"x" * (11 * 1024 * 1024)
    result = read_pdf(big)
    assert result.errors
    assert result.rows_extracted == 0


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------

def test_clean_money_basic():
    assert clean_money("1,200.00") == 1200.0


def test_clean_money_negative_parens():
    assert clean_money("(500.00)") == -500.0


def test_clean_money_rupee_symbol():
    assert clean_money("₹1200.00") == 1200.0


def test_clean_money_rs_prefix():
    assert clean_money("Rs.980.00") == 980.0


def test_clean_money_none():
    assert clean_money(None) is None


def test_clean_money_blank():
    assert clean_money("") is None


def test_is_money_valid():
    assert is_money("1200.00")
    assert is_money("₹980")
    assert is_money("1,200.50")


def test_is_money_invalid():
    assert not is_money("BESCOM")
    assert not is_money("")
    assert not is_money(None)


def test_parse_date_iso():
    result = parse_date("2024-01-05")
    assert result is not None
    assert result.year == 2024


def test_parse_date_dd_mon_yy():
    result = parse_date("05 Jan 24")
    assert result is not None
    assert result.month == 1


def test_parse_date_slashes():
    result = parse_date("05/01/2024")
    assert result is not None


def test_parse_date_invalid():
    assert parse_date("not a date") is None
    assert parse_date("") is None
    assert parse_date(None) is None


def test_normalize_text():
    assert normalize_text("  Hello   World  ") == "Hello World"


def test_clean_description_strips_numbers():
    result = clean_description("BESCOM 123456789012 Bill")
    assert "123456789012" not in result
    assert "BESCOM" in result


def test_group_words_into_lines_basic():
    words = [
        {"text": "A", "x0": 10, "top": 100},
        {"text": "B", "x0": 50, "top": 100},
        {"text": "C", "x0": 10, "top": 120},
    ]
    lines = group_words_into_lines(words, tolerance=2.5)
    assert len(lines) == 2
    assert len(lines[0]["words"]) == 2  # A and B on same line
    assert len(lines[1]["words"]) == 1  # C alone


def test_find_headers_returns_dict():
    words = [
        {"text": "Date",        "x0": 40,  "x1": 80,  "top": 50},
        {"text": "Description", "x0": 150, "x1": 300, "top": 50},
        {"text": "Withdrawal",  "x0": 380, "x1": 440, "top": 50},
        {"text": "Deposit",     "x0": 455, "x1": 510, "top": 50},
        {"text": "Balance",     "x0": 530, "x1": 580, "top": 50},
    ]
    headers = find_headers(words)
    assert "date" in headers
    assert "description" in headers
    assert "withdrawal" in headers or "deposit" in headers
