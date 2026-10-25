"""
utils/file_readers/excel_reader.py
Reads .xlsx / .xls files.
- Never executes macros or formulas.
- Maps common header aliases to canonical names.
- Handles debit/credit column convention.
- Passes through the same validation pipeline as CSV.
"""
from __future__ import annotations

import io
import re
from typing import Optional

import pandas as pd

from utils.file_readers.base import ExtractionResult

# Header alias mapping → canonical column names
_DATE_ALIASES = {"date", "transaction date", "txn date", "posted date", "value date", "trans date"}
_DESC_ALIASES = {
    "description", "transaction details", "narration", "merchant",
    "particulars", "details", "remarks", "memo", "transaction description",
}
_AMOUNT_ALIASES = {"amount", "transaction amount", "txn amount", "debit amount", "credit amount"}
_CURRENCY_ALIASES = {"currency", "ccy", "curr"}
_PAYMENT_ALIASES = {"payment method", "mode", "channel", "payment mode", "mode of payment"}


def _map_header(h: str) -> Optional[str]:
    """Map an Excel header to a canonical name, or None if not recognized."""
    h_lower = h.strip().lower()
    if h_lower in _DATE_ALIASES:
        return "date"
    if h_lower in _DESC_ALIASES:
        return "description"
    if h_lower in _AMOUNT_ALIASES:
        return "amount"
    if h_lower in _CURRENCY_ALIASES:
        return "currency"
    if h_lower in _PAYMENT_ALIASES:
        return "payment_method"
    return None


def _detect_header_row(df_raw: pd.DataFrame) -> int:
    """
    Try to find the row index that contains known column headers.
    Returns 0 (first row) by default.
    """
    for i, row in df_raw.iterrows():
        values = [str(v).strip().lower() for v in row.values if pd.notna(v)]
        if any(v in _DATE_ALIASES or v in _DESC_ALIASES for v in values):
            return int(str(i))
    return 0


def read_excel(file_bytes: bytes, worksheet_name: Optional[str] = None) -> ExtractionResult:
    """
    Parse Excel bytes (.xlsx or .xls) into a normalized DataFrame.
    If worksheet_name is None and multiple sheets exist, returns worksheet names
    in warnings/errors so the user can choose.
    """
    warnings: list[str] = []
    errors: list[str] = []

    # Detect format by signature
    file_like = io.BytesIO(file_bytes)
    is_xls = file_bytes[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # OLE2 signature

    try:
        if is_xls:
            xf = pd.ExcelFile(file_like, engine="xlrd")
        else:
            xf = pd.ExcelFile(file_like, engine="openpyxl")
    except Exception as exc:
        errors.append(
            "Could not open the Excel file. It may be password-protected, corrupted, "
            "or in an unsupported format (.xlsm is not supported)."
        )
        return ExtractionResult(
            dataframe=pd.DataFrame(),
            source_file_type="xls" if is_xls else "xlsx",
            source_parser="excel_reader",
            errors=errors,
        )

    sheet_names = xf.sheet_names

    # If no sheet specified and multiple sheets exist, prompt user
    if worksheet_name is None:
        if len(sheet_names) == 1:
            worksheet_name = sheet_names[0]
        else:
            return ExtractionResult(
                dataframe=pd.DataFrame(),
                source_file_type="xls" if is_xls else "xlsx",
                source_parser="excel_reader",
                warnings=[f"Multiple worksheets found: {sheet_names}. Please select one."],
                errors=["Worksheet selection required. Found: " + ", ".join(sheet_names)],
                requires_user_review=True,
                rows_extracted=0,
            )

    if worksheet_name not in sheet_names:
        errors.append(f"Worksheet '{worksheet_name}' not found. Available: {sheet_names}")
        return ExtractionResult(
            dataframe=pd.DataFrame(),
            source_file_type="xls" if is_xls else "xlsx",
            source_parser="excel_reader",
            errors=errors,
        )

    try:
        df_raw = xf.parse(worksheet_name, header=None, dtype=str)
    except Exception:
        errors.append("Could not parse the selected worksheet.")
        return ExtractionResult(
            dataframe=pd.DataFrame(),
            source_file_type="xls" if is_xls else "xlsx",
            source_parser="excel_reader",
            errors=errors,
        )

    if df_raw.empty:
        errors.append("The selected worksheet is empty.")
        return ExtractionResult(
            dataframe=pd.DataFrame(),
            source_file_type="xls" if is_xls else "xlsx",
            source_parser="excel_reader",
            errors=errors,
        )

    # Detect header row
    header_idx = _detect_header_row(df_raw)
    headers_raw = [str(v).strip() for v in df_raw.iloc[header_idx].values]
    data = df_raw.iloc[header_idx + 1:].copy()
    data.columns = headers_raw  # type: ignore[assignment]
    data = data.reset_index(drop=True)

    # Map headers
    mapped: dict[str, str] = {}
    for h in headers_raw:
        canonical = _map_header(h)
        if canonical:
            mapped[h] = canonical

    if not mapped:
        errors.append(
            "Could not identify any known column headers. "
            "Expected at least: date, description, amount."
        )
        return ExtractionResult(
            dataframe=pd.DataFrame(),
            source_file_type="xls" if is_xls else "xlsx",
            source_parser="excel_reader",
            errors=errors,
            requires_user_review=True,
        )

    # Handle debit/credit columns → signed amount
    debit_col = next((h for h in headers_raw if "debit" in h.lower() and "amount" in h.lower()), None)
    credit_col = next((h for h in headers_raw if "credit" in h.lower() and "amount" in h.lower()), None)
    if debit_col and credit_col and "amount" not in [_map_header(h) for h in headers_raw if _map_header(h) == "amount"]:
        # Derive signed amount: debit positive, credit negative
        try:
            debit_vals = pd.to_numeric(data[debit_col], errors="coerce").fillna(0)
            credit_vals = pd.to_numeric(data[credit_col], errors="coerce").fillna(0)
            data["amount"] = (debit_vals - credit_vals).astype(str)
            warnings.append(
                "Debit and credit columns detected. Amounts computed as: "
                "debit (expense) = positive, credit (refund/income) = negative. "
                "Please review this convention in the preview."
            )
            # Remove original debit/credit columns from mapping
            if debit_col in mapped:
                del mapped[debit_col]
            if credit_col in mapped:
                del mapped[credit_col]
            mapped["amount"] = "amount"
        except Exception:
            errors.append("Could not compute signed amount from debit/credit columns.")

    # Rename columns
    rename_map = {old: new for old, new in mapped.items() if old in data.columns}
    data = data.rename(columns=rename_map)
    # Keep only canonical columns
    canonical_cols = [c for c in ["date", "description", "amount", "currency", "payment_method"] if c in data.columns]
    data = data[canonical_cols].copy()

    # Drop entirely blank rows
    data = data.dropna(how="all").reset_index(drop=True)

    if data.empty:
        errors.append("No data rows found after parsing the worksheet.")
        return ExtractionResult(
            dataframe=pd.DataFrame(),
            source_file_type="xls" if is_xls else "xlsx",
            source_parser="excel_reader",
            errors=errors,
        )

    return ExtractionResult(
        dataframe=data,
        source_file_type="xls" if is_xls else "xlsx",
        source_parser="excel_reader",
        selected_worksheet=worksheet_name,
        warnings=warnings,
        errors=errors,
        rows_extracted=len(data),
    )
