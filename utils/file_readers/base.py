"""
utils/file_readers/base.py
Shared dataclass for extraction results from any file format.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class ExtractionResult:
    """Normalized result from any file reader."""
    dataframe: pd.DataFrame
    source_file_type: str                  # csv | xlsx | xls | pdf
    source_parser: str                     # module name
    parser_version: str = "1.0"
    selected_worksheet: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    requires_user_review: bool = False
    rows_extracted: int = 0

    def is_ok(self) -> bool:
        return len(self.errors) == 0 and not self.dataframe.empty
