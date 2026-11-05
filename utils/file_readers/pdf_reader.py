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

print("### UPDATED PDF READER LOADED ###")
# OCR fallback — optional heavy dependencies
try:
    import pymupdf
except ImportError:
    pymupdf = None

try:
    import pytesseract
    from PIL import Image
except ImportError:
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

def _canonical_header(line_text: str) -> Optional[str]:
    """Map a complete header phrase to a known column name."""
    normalized = normalize_text(line_text).lower()
    normalized = re.sub(r"[^a-z0-9/ ]+", " ", normalized)
    normalized = normalize_text(normalized)

    for kind, aliases in HEADER_ALIASES.items():
        if normalized in aliases:
            return kind

    # Also recognize aliases embedded in a longer header phrase.
    candidates = []
    for kind, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized):
                candidates.append((len(alias), kind))
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1]
    return None


def find_headers(words) -> dict:
    """
    Detect column headers using complete visual lines and short word groups.
    This handles multiword headers such as 'Transaction Date' and 'Debit Amount'
    even when the PDF extractor returns each word separately.
    Returns column-center x positions.
    """
    lines = group_words_into_lines(words, tolerance=4)
    best = {}
    best_score = 0

    for line in lines:
        ordered = sorted(line["words"], key=lambda w: float(w.get("x0", 0)))
        detected = []

        # Check each word and contiguous groups of 2–4 words.
        for i in range(len(ordered)):
            for width in (1, 2, 3, 4):
                chunk = ordered[i:i + width]
                if len(chunk) != width:
                    continue
                phrase = normalize_text(
                    " ".join(str(w.get("text", "")) for w in chunk)
                ).lower()
                kind = _canonical_header(phrase)
                if kind:
                    left = min(float(w.get("x0", 0)) for w in chunk)
                    right = max(float(w.get("x1", w.get("x0", 0))) for w in chunk)
                    detected.append((kind, (left + right) / 2, right - left))

        # For each kind, retain the widest phrase match to avoid selecting
        # only the word "date" from the phrase "transaction date".
        by_kind = {}
        for kind, center, width in detected:
            if kind not in by_kind or width > by_kind[kind][0]:
                by_kind[kind] = (width, center)

        if len(by_kind) > best_score:
            best_score = len(by_kind)
            best = by_kind

    if best_score < 2:
        return {}
    return {kind: center for kind, (_, center) in best.items()}


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
    if pymupdf is None or pytesseract is None or Image is None:
        return []
    results = []
    document = pymupdf.open(stream=pdf_data, filetype="pdf")
    for page in document:
        matrix = pymupdf.Matrix(2.5, 2.5)
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
# TEXT-LAYOUT FALLBACK (SBI-style statements)
# ============================================================

_SBI_ROW_RE = re.compile(
    r"^\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})\s+"
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})\s+"
    r"(.+?)\s+"
    r"(-|[\d,]+\.\d{2})\s+"       # reference/cheque column
    r"(-|[\d,]+\.\d{2})\s+"       # debit
    r"(-|[\d,]+\.\d{2})\s+"       # credit
    r"(-|[\d,]+\.\d{2})\s*$"      # balance
)

def parse_sbi_text_pages(text_pages: list[str]) -> list[dict]:
    """
    Parse text-based SBI statements whose transaction table is extracted as
    lines rather than reliably positioned table columns. Continuation lines
    are appended to the previous transaction description.
    """
    transactions: list[dict] = []
    current: Optional[dict] = None
    pending_marker = ""

    def save():
        nonlocal current
        if not current:
            return
        desc = clean_description(current.get("description", ""))
        amount = current.get("amount")
        date = current.get("date")
        if date is not None and desc and amount is not None and amount > 0:
            if desc.upper() not in _INVALID_DESCRIPTIONS:
                transactions.append({
                    "date": date,
                    "description": desc,
                    "amount": round(abs(float(amount)), 2),
                    "transaction_type": current.get("transaction_type", "unknown"),
                })
        current = None

    for page_text in text_pages:
        for raw_line in (page_text or "").splitlines():
            line = normalize_text(raw_line)
            if not line:
                continue

            match = _SBI_ROW_RE.match(line)
            if match:
                marker = current.get("description", "") if current and current.get("date") is None else ""
                save()
                value_date, post_date, description, _ref, debit, credit, _balance = match.groups()
                date = parse_date(value_date) or parse_date(post_date)
                debit_value = clean_money(debit) if debit != "-" else None
                credit_value = clean_money(credit) if credit != "-" else None

                # SBI transaction descriptions commonly start with WDL/DEP TFR
                # on the preceding line, so also use UPI/DR and UPI/CR markers.
                description = normalize_text(marker + " " + description)
                upper_desc = description.upper()
                if debit_value is not None and debit_value > 0:
                    amount, tx_type = debit_value, "debit"
                elif credit_value is not None and credit_value > 0:
                    amount, tx_type = credit_value, "credit"
                else:
                    amount, tx_type = None, "unknown"

                current = {
                    "date": date,
                    "description": description,
                    "amount": amount,
                    "transaction_type": tx_type,
                }
                continue

            # SBI statements place WDL TFR / DEP TFR immediately above a
            # transaction row. Attach it to the row's description when possible.
            if current is not None and current.get("date") is None:
                # Preserve the marker until the next dated transaction row.
                continue
            if current is not None:
                if line.upper() not in {"BALANCE", "STATEMENT OF ACCOUNT"} and not line.lower().startswith("page no."):
                    current["description"] = normalize_text(current["description"] + " " + line)
                continue

            # Keep transaction type marker for the next dated transaction line.
            if line.upper() in {"WDL TFR", "DEP TFR"}:
                current = {
                    "date": None,
                    "description": line,
                    "amount": None,
                    "transaction_type": "debit" if line.upper().startswith("WDL") else "credit",
                }

    save()
    return transactions


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

    # ---- Method 1b: line-based text fallback for statements such as SBI ----
    if not transactions and extracted_text_pages:
        try:
            transactions = parse_sbi_text_pages(extracted_text_pages)
            if transactions:
                warnings_list.append(
                    "Transactions extracted using the line-based statement fallback. "
                    "Review debit/credit classification before continuing."
                )
        except Exception as exc:
            warnings_list.append(f"Line-based PDF fallback failed: {str(exc)[:200]}")

    # ---- Method 2: OCR fallback ----
    if not transactions:
        if pymupdf is not None and pytesseract is not None and Image is not None:
            try:
                transactions = ocr_pdf(file_bytes)
                if transactions:
                    warnings_list.append("Transactions extracted via OCR. Verify dates and amounts carefully.")
            except Exception as exc:
                warnings_list.append(f"OCR fallback failed: {str(exc)[:200]}")
        elif is_scanned:
            warnings_list.append(
                "Install PyMuPDF, pytesseract, Pillow, and the Tesseract OCR application "
                "to enable OCR for scanned PDFs."
            )

    if not transactions:
        if extracted_text_pages and any(page.strip() for page in extracted_text_pages):
            warnings_list.append(
                "PDF text was readable, but the parser could not identify transaction rows. "
                "The bank statement may use unsupported header names or a different column layout."
            )
        return ExtractionResult(
            dataframe=pd.DataFrame(),
            source_file_type="pdf",
            source_parser="pdf_reader",
            warnings=warnings_list,
            errors=[
                "No transaction rows could be extracted from the PDF. "
                "If selectable text exists, check the statement's headers and column layout. "
                "If scanned, install PyMuPDF, pytesseract, Pillow, and the Tesseract OCR application. "
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
