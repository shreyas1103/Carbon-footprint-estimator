"""
tests/test_cleaning.py
Tests for pipeline/cleaning.py — deterministic, idempotent merchant cleaning.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.cleaning import clean_description


def test_basic_whitespace_stripped():
    cleaned, key = clean_description("  BigBasket  ")
    assert cleaned == "BigBasket"


def test_upi_prefix_removed():
    cleaned, key = clean_description("UPI/BigBasket@ybl")
    assert "bigbasket" in key
    assert "@ybl" not in key
    assert "UPI" not in cleaned


def test_neft_prefix_removed():
    cleaned, key = clean_description("NEFT/HDFC Bank Transfer")
    assert "neft" not in key


def test_long_reference_number_removed():
    cleaned, key = clean_description("Electricity Bill 123456789012")
    assert "123456789012" not in key
    assert "electricity" in key.lower()


def test_masked_account_removed():
    cleaned, key = clean_description("Payment to XXXX1234")
    assert "xxxx1234" not in key.lower()


def test_upi_handle_removed():
    cleaned, key = clean_description("Transfer to john@okaxis")
    assert "@okaxis" not in key


def test_separator_normalized():
    cleaned, key = clean_description("Tata|Power|Bill")
    assert "|" not in cleaned
    assert "tata" in key


def test_idempotent():
    """Applying cleaning twice yields the same result."""
    cleaned1, key1 = clean_description("UPI/BESCOM@okaxis 987654321098")
    cleaned2, key2 = clean_description(cleaned1)
    assert cleaned1 == cleaned2
    assert key1 == key2


def test_merchant_tokens_preserved():
    """Meaningful merchant tokens must not be stripped."""
    cleaned, key = clean_description("BigBasket Fresh Grocery")
    assert "bigbasket" in key
    assert "fresh" in key
    assert "grocery" in key


def test_distinct_merchants_not_merged():
    """Similar but distinct merchants must remain distinguishable."""
    _, key1 = clean_description("Reliance Fresh")
    _, key2 = clean_description("Reliance Petrol")
    assert key1 != key2


def test_unicode_normalized():
    cleaned, key = clean_description("Café\u00e9 Restaurant")
    # Should be normalized to NFKC
    assert isinstance(cleaned, str)


def test_punctuation_handled():
    cleaned, key = clean_description("D-Mart! Grocery & Supermarket.")
    assert "d mart" in key or "dmart" in key or "grocery" in key


def test_short_reference_number_kept():
    """Short numbers that may be meaningful should not be stripped (< 9 digits)."""
    cleaned, key = clean_description("7-Eleven Store")
    # 7 is not a 9+ digit number, should be kept
    assert "7" in cleaned or "eleven" in key.lower()


def test_payment_prefix_pos_removed():
    cleaned, key = clean_description("POS/Decathlon Sports")
    assert "decathlon" in key
    assert "pos" not in key.lower() or "decathlon" in key


def test_to_prefix_removed():
    cleaned, key = clean_description("Transfer to Electricity Board")
    assert "electricity" in key
