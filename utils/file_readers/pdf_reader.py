"""
utils/file_readers/pdf_reader.py
Robust word-based PDF transaction extractor with OCR fallback.
Returns ExtractionResult compatible with the validation pipeline.

Method 1: pdfplumber word extraction + visual line grouping + header detection.
Method 2: OCR fallback via PyMuPDF + pytesseract (requires optional installs).
"""
from __future__ import annotations

import re
from io import BytesIO
from typing import Optional

import pandas as pd
import pdfplumber

from utils.file_readers.base import ExtractionResult

# OCR fallback — optional heavy dependencies
try:
    import fitz  # PyMuPDF
    import pytesseract
    from PIL import Image
except ImportError:
    fitz = None
    pytesseract = None
    Image = None

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB

# ============================================================
# REGEX
# ============================================================

DATE_RE = re.compile(
    r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}\b"
    r"|\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b"
    r"|\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b"
)

MONEY_RE = re.compile(
    r"^\(?[+-]?(?:₹|Rs\.?|INR\s*)?"
    r"[\d,]+(?:\.\d{1,2})?\)?$"
)

# ============================================================
# HEADER ALIASES
# ============================================================

HEADER_ALIASES = {
    "date": {
        "date", "transaction date", "txn date", "posting date", "value date"
    },
    "description": {
        "description", "details", "transaction details", "transaction detail",
        "narration", "particulars", "remarks", "merchant",
        "transaction description", "reference"
    },
    "deposit": {
        "deposit", "deposits", "credit", "credits", "credit amount",
        "cr amount", "cr"
    },
    "withdrawal": {
        "withdrawal", "withdrawals", "debit", "debits", "debit amount",
        "dr amount", "dr"
    },
    "amount": {
        "amount", "transaction amount", "txn amount", "value"
    },
    "balance": {
        "balance", "closing balance", "available balance", "running balance"
    },
    "type": {
        "type", "transaction type", "txn type", "dr/cr", "credit/debit"
    },
}


# ============================================================
# HELPERS
# ============================================================

def normalize_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clean_money(value) -> Optional[float]:
    if value is None:
        return None
    value = str(value).strip()
    if value == "":
        return None
    value = (
        value.replace(",", "").replace("₹", "").replace("Rs.", "")
        .replace("Rs", "").replace("INR", "").strip()
    )
    negative = value.startswith("(") and value.endswith(")")
    value = value.replace("(", "").replace(")", "")
    try:
        number = float(value)
        return -number if negative else number
    except Exception:
        return None


def is_money(value) -> bool:
    if value is None:
        return False
    value = str(value).strip()
    if not re.search(r"\d", value):
        return False
    return MONEY_RE.match(value) is not None or clean_money(value) is not None


def parse_date(value):
    if not value:
        return None
    value = str(value).strip()
    formats = [
        "%d %b %y", "%d %b %Y", "%d %B %y", "%d %B %Y",
        "%d-%m-%Y", "%d-%m-%y", "%d/%m/%Y", "%d/%m/%y",
        "%Y-%m-%d", "%Y/%m/%d",
    ]
    for fmt in formats:
        try:
            result = pd.to_datetime(value, format=fmt)
            if pd.notna(result):
                return result
        except Exception:
            pass
    try:
        result = pd.to_datetime(value, errors="coerce")
        if pd.notna(result):
            return result
    except Exception:
        pass
    return None


def clean_description(value: str) -> str:
    value = normalize_text(value)
    # Strip long account/card/reference numbers
    value = re.sub(r"(?<!\w)\d{6,}(?!\w)", " ", value)
    # Strip leading date fragments
    value = re.sub(r"^\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}\s+", "", value)
    value = re.sub(r"^[A-Za-z]{3,9}\s+\d{2,4}\s+", "", value)
    value = re.sub(r"^\d{1,2}\s+(?=[A-Za-z])", "", value)
    return normalize_text(value).strip(" |:-")


# ============================================================
# VISUAL LINE GROUPING
# ============================================================

def group_words_into_lines(words, tolerance=2.5):
    words = sorted(
        words,
        key=lambda x: (float(x.get("top", 0)), float(x.get("x0", 0))),
    )
    groups = []
    for word in words:
        text = str(word.get("text", "")).strip()
        if not text:
            continue
        top = float(word.get("top", 0))
        if groups and abs(top - groups[-1]["top"]) <= tolerance:
            groups[-1]["words"].append(word)
        else:
            groups.append({"top": top, "words": [word]})
    for group in groups:
        group["words"] = sorted(group["words"], key=lambda x: float(x.get("x0", 0)))
    return groups


# ============================================================
# HEADER DETECTION
# ============================================================

def find_headers(words) -> dict:
    lines = group_words_into_lines(words, tolerance=3)
    best_line = None
    best_score = -1
    for line in lines:
        texts = [normalize_text(w.get("text", "")).lower() for w in line["words"]]
        score = sum(
            1 for aliases in HEADER_ALIASES.values()
            if any(t in aliases for t in texts)
        )
        if score > best_score and score >= 2:
            best_score = score
            best_line = line["words"]
    if best_line is None:
        return {}
    headers = {}
    for word in sorted(best_line, key=lambda x: float(x["x0"])):
        text = normalize_text(word.get("text", "")).lower()
        center = (float(word["x0"]) + float(word.get("x1", word["x0"]))) / 2
        for kind, aliases in HEADER_ALIASES.items():
            if text in aliases and kind not in headers:
                headers[kind] = center
    return headers


# ============================================================
# COLUMN RANGES
# ============================================================

def create_column_ranges(headers, page_width) -> dict:
    ordered = sorted((position, name) for name, position in headers.items())
    ranges = {}
    for i, (position, name) in enumerate(ordered):
        left = 0 if i == 0 else (ordered[i - 1][0] + position) / 2
        right = page_width if i == len(ordered) - 1 else (position + ordered[i + 1][0]) / 2
        ranges[name] = (left, right)
    return ranges


def in_column(x, column_range) -> bool:
    if column_range is None:
        return False
    return column_range[0] <= x < column_range[1]


def get_column_text(words, column_range) -> str:
    if column_range is None:
        return ""
    values = [w.get("text", "") for w in words if in_column(float(w.get("x0", 0)), column_range)]
    return clean_description(" ".join(values))


def find_date(words, date_range):
    if date_range is None:
        return None
    date_words = [w.get("text", "") for w in words if in_column(float(w.get("x0", 0)), date_range)]
    match = DATE_RE.search(" ".join(date_words))
    return parse_date(match.group(0)) if match else None


def find_money_in_column(words, column_range) -> Optional[float]:
    if column_range is None:
        return None
    for w in words:
        x = float(w.get("x0", 0))
        text = str(w.get("text", "")).strip()
        if in_column(x, column_range) and is_money(text):
            return clean_money(text)
    return None


# ============================================================
# PAGE PARSER
# ============================================================

_IGNORE_PHRASES = {
    "BANK DEPOSITS ARE COVERED", "NOMINATION DETAILS",
    "REPORT IRREGULARITIES", "REWARD POINTS STATEMENT",
    "SCHEME OPENING", "PAGE ",
}

_INVALID_DESCRIPTIONS = {
    "BALANCE FORWARD", "BALANCE B/F", "TOTAL",
    "OPENING BALANCE", "CLOSING BALANCE",
}


def parse_page(page, table_bbox=None) -> list[dict]:
    words = page.extract_words(x_tolerance=2, y_tolerance=2, keep_blank_chars=False)
    if not words:
        return []
    headers = find_headers(words)
    if not headers:
        return []
    columns = create_column_ranges(headers, page.width)
    lines = group_words_into_lines(words)
    if table_bbox:
        y_start, y_end = table_bbox[1], table_bbox[3]
        lines = [l for l in lines if y_start - 3 <= l["top"] <= y_end + 3]

    transactions: list[dict] = []
    current_date = None
    current_transaction: Optional[dict] = None

    def save_current():
        nonlocal current_transaction
        if not current_transaction:
            return
        desc = clean_description(current_transaction.get("description", ""))
        amount = current_transaction.get("amount")
        date = current_transaction.get("date")
        if date is not None and desc and amount is not None and amount > 0:
            if desc.upper() not in _INVALID_DESCRIPTIONS:
                transactions.append({
                    "date": date,
                    "description": desc,
                    "amount": round(abs(amount), 2),
                    "transaction_type": current_transaction.get("transaction_type", "unknown"),
                })
        current_transaction = None

    for line in lines:
        lw = line["words"]
        full_upper = normalize_text(" ".join(w["text"] for w in lw)).upper()
        if any(phrase in full_upper for phrase in _IGNORE_PHRASES):
            continue

        detected_date = find_date(lw, columns.get("date"))
        if detected_date is not None:
            current_date = detected_date

        description = get_column_text(lw, columns.get("description"))
        deposit = find_money_in_column(lw, columns.get("deposit"))
        withdrawal = find_money_in_column(lw, columns.get("withdrawal"))
        amount = find_money_in_column(lw, columns.get("amount"))
        type_text = get_column_text(lw, columns.get("type")).lower()

        transaction_amount = None
        transaction_type = "unknown"

        if withdrawal is not None:
            transaction_amount = abs(withdrawal)
            transaction_type = "debit"
        elif deposit is not None:
            transaction_amount = abs(deposit)
            transaction_type = "credit"
        elif amount is not None:
            transaction_amount = abs(amount)
            if any(w in type_text for w in ("debit", "dr")):
                transaction_type = "debit"
            elif any(w in type_text for w in ("credit", "cr")):
                transaction_type = "credit"
            else:
                du = description.upper()
                if any(w in du for w in ("RECEIVED", "DEPOSIT", "CREDIT", "SALARY", "INTEREST", "REFUND", "REVERSAL", "CASH DEPOSIT")):
                    transaction_type = "credit"
                else:
                    transaction_type = "debit"

        if transaction_amount is not None:
            save_current()
            if "BALANCE FORWARD" in description.upper() or description.upper() == "TOTAL":
                current_transaction = None
                continue
            current_transaction = {
                "date": current_date,
                "description": description,
                "amount": transaction_amount,
                "transaction_type": transaction_type,
            }
        elif current_transaction is not None and description:
            current_transaction["description"] = clean_description(
                current_transaction["description"] + " " + description
            )

    save_current()
    return transactions


# ============================================================
# OCR FALLBACK
# ============================================================

def parse_ocr_page(words, page_width) -> list[dict]:
    if not words:
        return []
    headers = find_headers(words)
    if not headers:
        return []
    columns = create_column_ranges(headers, page_width)
    lines = group_words_into_lines(words, tolerance=12)

    transactions: list[dict] = []
    current_date = None
    current_transaction: Optional[dict] = None

    def save():
        nonlocal current_transaction
        if not current_transaction:
            return
        desc = clean_description(current_transaction.get("description", ""))
        amount = current_transaction.get("amount")
        if current_transaction.get("date") is not None and desc and amount is not None and amount > 0:
            transactions.append({
                "date": current_transaction["date"],
                "description": desc,
                "amount": round(abs(amount), 2),
                "transaction_type": current_transaction.get("transaction_type", "unknown"),
            })
        current_transaction = None

    for line in lines:
        lw = line["words"]
        date = find_date(lw, columns.get("date"))
        if date is not None:
            current_date = date
        description = get_column_text(lw, columns.get("description"))
        deposit = find_money_in_column(lw, columns.get("deposit"))
        withdrawal = find_money_in_column(lw, columns.get("withdrawal"))
        amount = find_money_in_column(lw, columns.get("amount"))

        transaction_amount = None
        transaction_type = "unknown"

        if withdrawal is not None:
            transaction_amount, transaction_type = abs(withdrawal), "debit"
        elif deposit is not None:
            transaction_amount, transaction_type = abs(deposit), "credit"
        elif amount is not None:
            transaction_amount = abs(amount)
            du = description.upper()
            if any(w in du for w in ("RECEIVED", "DEPOSIT", "CREDIT", "SALARY", "INTEREST", "REFUND")):
                transaction_type = "credit"
            else:
                transaction_type = "debit"

        if transaction_amount is not None:
            save()
            current_transaction = {"date": current_date, "description": description, "amount": transaction_amount, "transaction_type": transaction_type}
        elif current_transaction is not None and description:
            current_transaction["description"] = clean_description(
                current_transaction["description"] + " " + description
            )

    save()
    return transactions


def ocr_pdf(pdf_data: bytes) -> list[dict]:
    if fitz is None or pytesseract is None or Image is None:
        return []
    results = []
    document = fitz.open(stream=pdf_data, filetype="pdf")
    for page in document:
        matrix = fitz.Matrix(2.5, 2.5)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
        data_dict = pytesseract.image_to_data(image, config="--psm 6", output_type=pytesseract.Output.DICT)
        words = []
        for i, text in enumerate(data_dict["text"]):
            text = str(text).strip()
            if not text:
                continue
            words.append({
                "text": text,
                "x0": data_dict["left"][i],
                "x1": data_dict["left"][i] + data_dict["width"][i],
                "top": data_dict["top"][i],
                "bottom": data_dict["top"][i] + data_dict["height"][i],
            })
        results.extend(parse_ocr_page(words, pixmap.width))
    return results


# ============================================================
# DEDUPLICATION + DATAFRAME BUILD
# ============================================================

def _build_dataframe(transactions: list[dict]) -> pd.DataFrame:
    """Deduplicate and build the final normalized DataFrame."""
    unique, seen = [], set()
    for t in transactions:
        date = t.get("date")
        date_key = str(date.date()) if hasattr(date, "date") else str(date)
        key = (date_key, t.get("description", ""), round(float(t.get("amount", 0)), 2), t.get("transaction_type", "unknown"))
        if key not in seen:
            seen.add(key)
            unique.append(t)

    df = pd.DataFrame(unique)
    for col in ("date", "description", "amount", "transaction_type"):
        if col not in df.columns:
            df[col] = None

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").abs()
    df["description"] = df["description"].astype(str).apply(clean_description)
    df["transaction_type"] = df["transaction_type"].fillna("unknown").astype(str).str.lower()

    df = df.dropna(subset=["date", "amount"])
    df = df[df["amount"] > 0]
    df = df[df["description"].str.len() > 0]

    _invalid = {"BALANCE FORWARD", "BALANCE B/F", "TOTAL", "OPENING BALANCE", "CLOSING BALANCE"}
    df = df[~df["description"].str.upper().isin(_invalid)]
    df = df.drop_duplicates().reset_index(drop=True)

    # Rename transaction_type → debit sign convention: debit = positive, credit = positive
    # Keep transaction_type as a column for the pipeline
    return df[["date", "description", "amount", "transaction_type"]]


# ============================================================
# PUBLIC INTERFACE — ExtractionResult
# ============================================================

def read_pdf(file_bytes: bytes) -> ExtractionResult:
    """
    Parse a PDF bank statement and return an ExtractionResult.
    Method 1: pdfplumber word extraction.
    Method 2: OCR fallback (requires PyMuPDF + pytesseract).
    """
    warnings_list: list[str] = []
    errors_list: list[str] = []

    if not file_bytes:
        return ExtractionResult(
            dataframe=pd.DataFrame(),
            source_file_type="pdf",
            source_parser="pdf_reader",
            errors=["The uploaded PDF file is empty."],
            rows_extracted=0,
        )

    if len(file_bytes) > MAX_FILE_BYTES:
        return ExtractionResult(
            dataframe=pd.DataFrame(),
            source_file_type="pdf",
            source_parser="pdf_reader",
            errors=[f"PDF exceeds maximum size of {MAX_FILE_BYTES // 1024 // 1024} MB."],
            rows_extracted=0,
        )

    transactions: list[dict] = []
    extracted_text_pages: list[str] = []
    is_scanned = False

    # ---- Method 1: pdfplumber ----
    try:
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            total_text = ""
            for page in pdf.pages:
                text = page.extract_text() or ""
                extracted_text_pages.append(text)
                total_text += text
                words = page.extract_words(x_tolerance=2, y_tolerance=2, keep_blank_chars=False)
                tables = page.find_tables()
                table_bbox = None
                if tables:
                    table_bbox = max(tables, key=lambda t: (t.bbox[2] - t.bbox[0]) * (t.bbox[3] - t.bbox[1])).bbox
                page_txns = parse_page(page, table_bbox)
                transactions.extend(page_txns)

            if not total_text.strip():
                is_scanned = True
                warnings_list.append("PDF appears to be image-only (scanned). Attempting OCR fallback.")
    except Exception as exc:
        warnings_list.append(f"pdfplumber extraction warning: {str(exc)[:200]}")

    # ---- Method 2: OCR fallback ----
    if not transactions:
        if fitz is not None and pytesseract is not None:
            try:
                transactions = ocr_pdf(file_bytes)
                if transactions:
                    warnings_list.append("Transactions extracted via OCR. Verify dates and amounts carefully.")
            except Exception as exc:
                warnings_list.append(f"OCR fallback failed: {str(exc)[:200]}")
        elif is_scanned:
            warnings_list.append(
                "Install PyMuPDF + pytesseract + Tesseract to enable OCR for scanned PDFs."
            )

    if not transactions:
        return ExtractionResult(
            dataframe=pd.DataFrame(),
            source_file_type="pdf",
            source_parser="pdf_reader",
            warnings=warnings_list,
            errors=[
                "No transaction rows could be extracted from the PDF. "
                "Please ensure it is a text-based bank statement (not a scanned image). "
                "If scanned, install PyMuPDF and pytesseract for OCR support. "
                "Alternatively, export the statement as CSV or Excel from your bank's website."
            ],
            rows_extracted=0,
        )

    # Build DataFrame
    try:
        df = _build_dataframe(transactions)
    except Exception as exc:
        return ExtractionResult(
            dataframe=pd.DataFrame(),
            source_file_type="pdf",
            source_parser="pdf_reader",
            warnings=warnings_list,
            errors=[f"Failed to build transaction table: {str(exc)[:300]}"],
            rows_extracted=0,
        )

    if df.empty:
        return ExtractionResult(
            dataframe=pd.DataFrame(),
            source_file_type="pdf",
            source_parser="pdf_reader",
            warnings=warnings_list,
            errors=["PDF was parsed but no valid transactions remained after filtering."],
            rows_extracted=0,
        )

    # Rename for pipeline compatibility: use 'description' as-is, no 'transaction_type' needed downstream
    # Add transaction_type as payment_method hint
    if "transaction_type" in df.columns:
        df = df.rename(columns={"transaction_type": "payment_method"})

    warnings_list.append(
        f"PDF extraction complete. Extracted {len(df)} transactions. "
        "Review the 'payment_method' column (debit/credit) for accuracy."
    )

    return ExtractionResult(
        dataframe=df,
        source_file_type="pdf",
        source_parser="pdf_reader (word-based)",
        warnings=warnings_list,
        errors=[],
        rows_extracted=len(df),
    )
