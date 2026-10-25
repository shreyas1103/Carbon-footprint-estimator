"""
pipeline/cleaning.py
Deterministic, idempotent merchant description cleaning.
Produces cleaned_description and merchant_key from raw_description.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

# ---------------------------------------------------------------------------
# Configurable stopwords / prefixes to remove
# ---------------------------------------------------------------------------

PAYMENT_PREFIXES = [
    r"UPI[/-]",
    r"NEFT[/-]",
    r"IMPS[/-]",
    r"RTGS[/-]",
    r"POS[/-]?",
    r"ECOM[/-]?",
    r"BIL[/-]?",
    r"MMT[/-]?",
    r"INB[/-]?",
    r"CLG[/-]?",
]

# Patterns that look like transaction reference numbers (long digit strings)
_REF_NUMBER_RE = re.compile(r"\b\d{9,}\b")

# Masked account fragments like XXXXXX1234
_MASKED_ACCT_RE = re.compile(r"X{4,}\d+", re.IGNORECASE)

# Common UPI suffixes like @okaxis, @ybl, @paytm, @oksbi
_UPI_HANDLE_RE = re.compile(r"@[a-z0-9]+\b", re.IGNORECASE)

# Collapse multiple spaces/underscores
_MULTI_SPACE_RE = re.compile(r"[\s_]+")

# Compiled prefix pattern
_PREFIX_RE = re.compile(
    r"^(?:" + "|".join(PAYMENT_PREFIXES) + r")",
    re.IGNORECASE,
)

# Common transaction label suffixes (e.g. "to abc@okaxis" → "abc")
_TO_FROM_RE = re.compile(r"\b(?:to|from|by|via)\b\s+", re.IGNORECASE)


def _unicode_normalize(text: str) -> str:
    """NFKC Unicode normalization to canonical form."""
    return unicodedata.normalize("NFKC", text)


def clean_description(raw: str) -> tuple[str, str]:
    """
    Clean a raw bank transaction description.

    Returns:
        (cleaned_description, merchant_key)

    Rules:
    - Unicode NFKC normalization.
    - Casefold for merchant_key; preserve title case in cleaned_description.
    - Strip leading/trailing whitespace.
    - Remove obvious transaction reference numbers (9+ consecutive digits).
    - Remove masked account fragments (XXXX1234).
    - Remove UPI handles (@okaxis, @ybl, etc.).
    - Remove known payment method prefixes (UPI/, NEFT/, etc.).
    - Normalize separators (-, /, |, _) to spaces.
    - Collapse repeated spaces.
    - Do NOT over-normalize: preserve merchant tokens.
    - Idempotent: applying twice yields the same result.
    """
    if not isinstance(raw, str):
        raw = str(raw)

    text = _unicode_normalize(raw)
    text = text.strip()

    # Remove payment method prefixes
    text = _PREFIX_RE.sub("", text).strip()

    # Remove "to / from / by" leads from UPI-style strings
    text = _TO_FROM_RE.sub("", text).strip()

    # Remove UPI handles
    text = _UPI_HANDLE_RE.sub("", text).strip()

    # Remove masked account fragments
    text = _MASKED_ACCT_RE.sub("", text).strip()

    # Remove long reference numbers (9+ digits) — but keep short numbers
    # that may be meaningful (e.g., "4G" or "7-Eleven" style)
    text = _REF_NUMBER_RE.sub("", text).strip()

    # Normalize separators to space
    text = re.sub(r"[/|_\-]+", " ", text).strip()

    # Collapse multiple spaces
    text = _MULTI_SPACE_RE.sub(" ", text).strip()

    # cleaned_description: title-case, spaces
    cleaned_description = text.strip()

    # merchant_key: casefold, collapse spaces, remove punctuation except hyphens
    merchant_key = cleaned_description.casefold()
    merchant_key = re.sub(r"[^\w\s-]", "", merchant_key)
    merchant_key = _MULTI_SPACE_RE.sub(" ", merchant_key).strip()

    return cleaned_description, merchant_key


def clean_dataframe(df) -> object:
    """
    Apply clean_description to every row in a DataFrame.
    Adds 'cleaned_description' and 'merchant_key' columns.
    Preserves original 'description' as 'raw_description'.
    Returns the modified DataFrame.
    """
    import pandas as pd

    df = df.copy()
    if "description" not in df.columns:
        return df

    if "raw_description" not in df.columns:
        df["raw_description"] = df["description"]

    cleaned_keys = df["description"].apply(
        lambda x: clean_description(x) if isinstance(x, str) else ("", "")
    )
    df["cleaned_description"] = [ck[0] for ck in cleaned_keys]
    df["merchant_key"] = [ck[1] for ck in cleaned_keys]

    return df
