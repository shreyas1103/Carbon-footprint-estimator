"""
utils/file_readers/csv_reader.py
Reads a CSV upload and returns an ExtractionResult.
All sensitive column checks are handled downstream in utils/validation.py.
"""
from __future__ import annotations

import io

import pandas as pd

from utils.file_readers.base import ExtractionResult


def read_csv(file_bytes: bytes) -> ExtractionResult:
    """
    Parse CSV bytes into a normalized DataFrame.
    Handles malformed CSV, empty files, encoding issues.
    """
    warnings: list[str] = []
    errors: list[str] = []

    try:
        df = pd.read_csv(io.BytesIO(file_bytes), dtype=str)
    except pd.errors.EmptyDataError:
        errors.append("The uploaded CSV is empty or contains only headers.")
        return ExtractionResult(
            dataframe=pd.DataFrame(),
            source_file_type="csv",
            source_parser="csv_reader",
            errors=errors,
        )
    except pd.errors.ParserError as exc:
        errors.append(f"The CSV could not be parsed. Please check the file format.")
        return ExtractionResult(
            dataframe=pd.DataFrame(),
            source_file_type="csv",
            source_parser="csv_reader",
            errors=errors,
        )
    except UnicodeDecodeError:
        # Try latin-1 fallback
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), dtype=str, encoding="latin-1")
            warnings.append("File was read with latin-1 encoding fallback.")
        except Exception:
            errors.append("Could not decode the CSV file. Please ensure it is UTF-8 or latin-1 encoded.")
            return ExtractionResult(
                dataframe=pd.DataFrame(),
                source_file_type="csv",
                source_parser="csv_reader",
                errors=errors,
            )

    if df.empty or df.columns.empty:
        errors.append("The CSV file is empty or has no columns.")
        return ExtractionResult(
            dataframe=pd.DataFrame(),
            source_file_type="csv",
            source_parser="csv_reader",
            errors=errors,
        )

    return ExtractionResult(
        dataframe=df,
        source_file_type="csv",
        source_parser="csv_reader",
        warnings=warnings,
        errors=errors,
        rows_extracted=len(df),
    )
