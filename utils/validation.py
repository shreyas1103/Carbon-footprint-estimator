"""
utils/validation.py
CSV/Excel/PDF validation: header normalization, sensitive-column rejection,
required-column check, row-level type validation.

All functions are pure (no DB dependency) so they work even without a DB.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS = {"date", "description", "amount"}
OPTIONAL_COLUMNS = {"currency", "payment_method"}
ALLOWED_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS

# Regex patterns for sensitive column headers (normalized lowercase, no spaces/underscores)
_SENSITIVE_PATTERNS = [
    r"account\s*(?:no|num|number|id|holder)",
    r"acct\s*(?:no|num|number)",
    r"customer\s*(?:id|number|no)",
    r"card\s*(?:number|no|num)",
    r"debit\s*card",
    r"credit\s*card",
    r"cvv",
    r"expiry",
    r"expiration",
    r"ifsc",
    r"upi\s*(?:id|handle|vpa)",
    r"vpa",
    r"bank\s*account",
    r"password",
    r"\bpin\b",
    r"\botp\b",
    r"auth\s*token",
    r"secret",
    r"balance",
    r"opening\s*balance",
    r"closing\s*balance",
    r"available\s*balance",
    r"cheque\s*(?:no|number)",
    r"iban",
    r"swift",
    r"sort\s*code",
    r"routing\s*number",
    r"aadhaar",
    r"pan\s*(?:number|no|card)",
    r"passport",
]

_SENSITIVE_RE = re.compile(
    "|".join(f"(?:{p})" for p in _SENSITIVE_PATTERNS),
    re.IGNORECASE,
)

SUPPORTED_CURRENCIES = {"INR"}

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB default
MAX_ROWS = 50_000


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RowIssue:
    row_number: int  # 1-indexed original row
    column: Optional[str]
    issue: str


@dataclass
class ValidationResult:
    valid_df: pd.DataFrame
    invalid_rows: list[RowIssue]
    warnings: list[str]
    errors: list[str]         # fatal errors (cannot proceed)
    can_proceed: bool

    @property
    def valid_count(self) -> int:
        return len(self.valid_df)

    @property
    def invalid_count(self) -> int:
        return len(self.invalid_rows)


# ---------------------------------------------------------------------------
# Header normalization
# ---------------------------------------------------------------------------

def normalize_header(h: Any) -> str:
    """Lowercase, strip whitespace, collapse internal spaces to underscore."""
    if not isinstance(h, str):
        h = str(h)
    return re.sub(r"\s+", "_", h.strip().lower())


def _check_sensitive_headers(headers: list[str]) -> list[str]:
    """Return list of sensitive normalized header names found.
    Normalize underscores to spaces before matching so 'account_number' → 'account number' matches.
    """
    sensitive = []
    for h in headers:
        # Treat underscores as spaces for pattern matching only
        h_for_match = h.replace("_", " ")
        if _SENSITIVE_RE.search(h_for_match):
            sensitive.append(h)
    return sensitive


# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------

def validate_dataframe(
    df: pd.DataFrame,
    source_type: str = "csv",
) -> ValidationResult:
    """
    Validate a raw dataframe extracted from any source (CSV/Excel/PDF).

    Steps:
      1. Normalize and deduplicate headers.
      2. Reject if sensitive columns present.
      3. Reject if required columns missing.
      4. Drop extra columns (allowlist only).
      5. Row-level: date, description, amount validation.
      6. Currency check.
      7. Build ValidationResult.

    Never echoes sensitive cell values in errors.
    Does not require a database connection.
    """
    warnings: list[str] = []
    errors: list[str] = []

    # ---- 0. Empty file ----
    if df is None or df.empty:
        return ValidationResult(
            valid_df=pd.DataFrame(),
            invalid_rows=[],
            warnings=[],
            errors=["The uploaded file contains no data or only headers."],
            can_proceed=False,
        )

    # ---- 1. Normalize headers ----
    original_columns = list(df.columns)
    norm_cols = [normalize_header(c) for c in original_columns]

    # Check for duplicate headers
    seen: set[str] = set()
    dupes: list[str] = []
    for nc in norm_cols:
        if nc in seen:
            dupes.append(nc)
        seen.add(nc)
    if dupes:
        errors.append(
            f"Duplicate column names detected after normalization: {dupes}. "
            "Please remove duplicate columns and upload again."
        )
        return ValidationResult(
            valid_df=pd.DataFrame(),
            invalid_rows=[],
            warnings=warnings,
            errors=errors,
            can_proceed=False,
        )

    df.columns = norm_cols  # type: ignore[assignment]

    # ---- 2. Sensitive column check ----
    sensitive_found = _check_sensitive_headers(norm_cols)
    if sensitive_found:
        errors.append(
            f"Sensitive account/card identifier column(s) detected: "
            f"{sensitive_found}. Please remove those columns and upload again. "
            "We do not process files containing account numbers, card numbers, UPI IDs, "
            "IFSC codes, or similar sensitive identifiers."
        )
        return ValidationResult(
            valid_df=pd.DataFrame(),
            invalid_rows=[],
            warnings=warnings,
            errors=errors,
            can_proceed=False,
        )

    # ---- 3. Required columns ----
    missing = REQUIRED_COLUMNS - set(norm_cols)
    if missing:
        errors.append(
            f"Required column(s) missing: {sorted(missing)}. "
            f"The file must include: date, description, amount."
        )
        return ValidationResult(
            valid_df=pd.DataFrame(),
            invalid_rows=[],
            warnings=warnings,
            errors=errors,
            can_proceed=False,
        )

    # ---- 4. Drop non-allowed columns ----
    extra_cols = [c for c in norm_cols if c not in ALLOWED_COLUMNS]
    if extra_cols:
        warnings.append(
            f"Extra column(s) not in the allowed list were ignored: {extra_cols}. "
            "Only date, description, amount, currency, payment_method are processed."
        )
    df = df[[c for c in norm_cols if c in ALLOWED_COLUMNS]].copy()
    df = df.reset_index(drop=True)  # Ensure positional integer index

    # ---- 5. Row-level validation ----
    # Parse into separate lists to avoid pandas 2.x in-place mutation conflicts
    # (the 'date' column name shadows pd.DataFrame.date attribute)
    invalid_rows: list[RowIssue] = []
    valid_mask: list[bool] = [True] * len(df)
    parsed_dates: list = [None] * len(df)
    parsed_amounts: list = [None] * len(df)
    parsed_currencies: list = ["INR"] * len(df)

    col_names = df.columns.tolist()
    date_pos = col_names.index("date") if "date" in col_names else -1
    amt_pos = col_names.index("amount") if "amount" in col_names else -1
    desc_pos = col_names.index("description") if "description" in col_names else -1
    cur_pos = col_names.index("currency") if "currency" in col_names else -1

    for i in range(len(df)):
        row_num = i + 2  # 1-indexed + header row offset
        row_arr = df.iloc[i]
        row_valid = True

        # --- date ---
        raw_date = row_arr.iloc[date_pos] if date_pos >= 0 else None
        try:
            parsed_date = pd.to_datetime(raw_date, dayfirst=False)
            if pd.isna(parsed_date):
                raise ValueError("NaT")
            parsed_dates[i] = parsed_date.date()
        except Exception:
            invalid_rows.append(RowIssue(row_num, "date", "Invalid date value."))
            row_valid = False

        # --- description ---
        raw_desc = row_arr.iloc[desc_pos] if desc_pos >= 0 else None
        if not isinstance(raw_desc, str) or not str(raw_desc).strip():
            invalid_rows.append(
                RowIssue(row_num, "description", "Description is blank or missing.")
            )
            row_valid = False

        # --- amount ---
        raw_amt = row_arr.iloc[amt_pos] if amt_pos >= 0 else None
        try:
            amt = float(str(raw_amt).replace(",", "").strip())
            if not _is_finite(amt):
                raise ValueError("non-finite")
            parsed_amounts[i] = amt
        except Exception:
            invalid_rows.append(
                RowIssue(row_num, "amount", "Amount is not a valid finite number.")
            )
            row_valid = False

        # --- currency (if present) ---
        if cur_pos >= 0:
            currency_val = str(row_arr.iloc[cur_pos] or "INR").strip().upper()
            parsed_currencies[i] = currency_val
            if currency_val != "INR":
                warnings.append(
                    f"Row {row_num}: currency '{currency_val}' is not INR. "
                    "This transaction will be excluded from emissions estimates "
                    "until a validated conversion rate is applied."
                )

        if not row_valid:
            valid_mask[i] = False

    # ---- 5b. Write parsed values back to a fresh DataFrame ----
    df2 = df.copy()
    df2["date"] = parsed_dates
    df2["amount"] = parsed_amounts
    df2["currency"] = parsed_currencies

    # ---- 6. Default currency if missing ----
    if cur_pos < 0:
        warnings.append(
            "No 'currency' column found. All transactions assumed to be INR. "
            "If your data contains non-INR transactions, add a currency column."
        )

    # Build valid dataframe
    valid_df = df2.loc[[bool(v) for v in valid_mask]].reset_index(drop=True)

    if valid_df.empty and not errors:
        errors.append("No valid rows found after validation.")

    can_proceed = len(errors) == 0 and not valid_df.empty

    return ValidationResult(
        valid_df=valid_df,
        invalid_rows=invalid_rows,
        warnings=warnings,
        errors=errors,
        can_proceed=can_proceed,
    )


def _is_finite(value: float) -> bool:
    import math
    return math.isfinite(value)


# ---------------------------------------------------------------------------
# Pydantic strict model (Addendum B)
# ---------------------------------------------------------------------------

try:
    from pydantic import BaseModel, ConfigDict, field_validator
    from datetime import date as _date
    from typing import Optional as _Opt

    class TransactionRow(BaseModel):
        """
        Strict Pydantic model — extra='forbid' ensures no unknown fields
        (including account numbers) can slip through into downstream processing.
        """
        model_config = ConfigDict(extra="forbid")

        date: _date
        description: str
        amount: float
        currency: str = "INR"
        payment_method: _Opt[str] = None

        @field_validator("description")
        @classmethod
        def desc_non_empty(cls, v: str) -> str:
            if not v.strip():
                raise ValueError("description must not be blank")
            return v.strip()

        @field_validator("amount")
        @classmethod
        def amount_finite(cls, v: float) -> float:
            import math
            if not math.isfinite(v):
                raise ValueError("amount must be a finite number")
            return v

except ImportError:
    TransactionRow = None  # type: ignore[assignment, misc]
