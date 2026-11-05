"""
dashboard/pages/1_Upload.py
EcoTrack — Statement Ingestion & Processing Pipeline
Sleek drag-and-drop file upload with visual 4-step pipeline:
  01 Upload Statement
  02 Extract Transactions
  03 Categorize Spending
  04 Calculate Emissions
Preserves all existing working extraction, cleaning, categorization, and emission logic.
"""
from __future__ import annotations
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))

sys.path.insert(0, str(PROJECT_ROOT))


import os
import sys
import uuid
from datetime import date

# Ensure the actual project root is available for imports
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st

from components.sidebar import render_sidebar
from pipeline.categorization.pipeline import categorize_dataframe
from pipeline.cleaning import clean_dataframe
from pipeline.emissions import apply_emissions_to_dataframe, compute_coverage_metrics
from utils.file_readers.csv_reader import read_csv
from utils.file_readers.excel_reader import read_excel
from utils.file_readers.pdf_reader import read_pdf
from utils.validation import validate_dataframe, MAX_FILE_BYTES


def safe_int(value):
    if value is None or pd.isna(value):
        return None
    try:
        return int(value)
    except Exception:
        return None


# ── Page Configuration ──
st.set_page_config(
    page_title="Upload Statement — EcoTrack",
    page_icon="📁",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_sidebar(current_page="Upload Statement")


# ── Page Header ──
st.markdown("""
<div style="margin-bottom: 24px;">
    <div style="font-size: 13px; font-weight: 700; color: #246B45; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">
        Data Ingestion
    </div>
    <div style="font-size: 30px; font-weight: 800; color: #1F2933; letter-spacing: -0.02em; margin-bottom: 6px;">
        Upload Bank Statement
    </div>
    <div style="font-size: 14.5px; color: #78847D; max-width: 680px; line-height: 1.5;">
        Upload your account or card statements in PDF, CSV, or Excel format. Our privacy filter strips sensitive identifiers before running multi-tier categorization and emission factor mapping.
    </div>
</div>
""", unsafe_allow_html=True)


# ── Visual 4-Step Pipeline Header ──
st.markdown("""
<div class="eco-card" style="padding: 18px 24px; margin-bottom: 24px;">
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;">
        <div style="display: flex; align-items: center; gap: 10px;">
            <div style="width: 28px; height: 28px; border-radius: 8px; background: #246B45; color: white; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 800;">1</div>
            <div>
                <div style="font-size: 13px; font-weight: 700; color: #1F2933;">Upload Statement</div>
                <div style="font-size: 11px; color: #78847D;">PDF, CSV, Excel</div>
            </div>
        </div>
        <div style="display: flex; align-items: center; gap: 10px;">
            <div style="width: 28px; height: 28px; border-radius: 8px; background: #E7F3EB; color: #246B45; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 800;">2</div>
            <div>
                <div style="font-size: 13px; font-weight: 700; color: #1F2933;">Extract & Clean</div>
                <div style="font-size: 11px; color: #78847D;">Strip PII & normalize</div>
            </div>
        </div>
        <div style="display: flex; align-items: center; gap: 10px;">
            <div style="width: 28px; height: 28px; border-radius: 8px; background: #E7F3EB; color: #246B45; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 800;">3</div>
            <div>
                <div style="font-size: 13px; font-weight: 700; color: #1F2933;">Categorize Spend</div>
                <div style="font-size: 11px; color: #78847D;">ML & dictionary tiers</div>
            </div>
        </div>
        <div style="display: flex; align-items: center; gap: 10px;">
            <div style="width: 28px; height: 28px; border-radius: 8px; background: #E7F3EB; color: #246B45; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 800;">4</div>
            <div>
                <div style="font-size: 13px; font-weight: 700; color: #1F2933;">Compute Footprint</div>
                <div style="font-size: 11px; color: #78847D;">India-specific factors</div>
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Privacy Guarantee Expander ──
with st.expander("🛡️ Privacy & Security Safeguards (Click to view)", expanded=False):
    st.markdown("""
    - **Whitelisted Columns:** Only `date`, `description`, `amount`, and optional `currency`, `payment_method` enter the pipeline.
    - **Rejection of Sensitive Fields:** Any file containing account numbers, card PANs, CVVs, IFSC codes, UPI IDs, passwords, or balance columns is strictly rejected before processing.
    - **In-Memory Sanitization:** Statements are parsed directly in memory. Raw uploaded files are never persisted to disk.
    - **Currency Guarantee:** Non-INR currencies are safely isolated and flagged until official conversion factors are verified.
    """)


# ── File Uploader ──
MAX_MB = MAX_FILE_BYTES // (1024 * 1024)

uploaded_file = st.file_uploader(
    f"Drop your statement here or click to browse (Max {MAX_MB} MB)",
    type=["csv", "xlsx", "xls", "pdf"],
    key="transaction_file_upload",
    help="Supported: PDF (e-statements), CSV (bank exports), Excel (.xlsx, .xls)",
)

if not uploaded_file:
    st.markdown("""
    <div style="text-align: center; padding: 24px; color: #78847D; font-size: 13.5px;">
        Supported institutions: HDFC, ICICI, SBI, Axis, Kotak, Standard Chartered, and generic statement exports.
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ── File Size Check ──
file_bytes = uploaded_file.read()
if len(file_bytes) > MAX_FILE_BYTES:
    st.error(
        f"File exceeds maximum allowed limit ({len(file_bytes) / 1024 / 1024:.1f} MB > {MAX_MB} MB). Please upload a smaller file.",
        icon="🚫",
    )
    st.stop()

file_ext = uploaded_file.name.rsplit(".", 1)[-1].lower()


# ── Step 1: Extraction ──
st.markdown("""
<div style="margin: 24px 0 12px 0;">
    <div style="font-size: 16px; font-weight: 700; color: #1F2933;">Pipeline Step 1: File Parsing</div>
</div>
""", unsafe_allow_html=True)

extraction_result = None

if file_ext == "csv":
    with st.spinner("Extracting transactions from CSV..."):
        extraction_result = read_csv(file_bytes)

elif file_ext in ("xlsx", "xls"):
    with st.spinner("Reading Excel statement sheets..."):
        initial_result = read_excel(file_bytes, worksheet_name=None)

    if initial_result.requires_user_review and initial_result.warnings:
        sheet_choice = st.selectbox(
            "Select Worksheet",
            initial_result.warnings,
            key="sheet_selector",
        )
        if sheet_choice:
            with st.spinner(f"Extracting '{sheet_choice}'..."):
                extraction_result = read_excel(file_bytes, worksheet_name=sheet_choice)
        else:
            st.stop()
    else:
        extraction_result = initial_result

elif file_ext == "pdf":
    with st.spinner("Extracting text and transaction tables from PDF..."):
        extraction_result = read_pdf(file_bytes)


# ── Handle Extraction Result ──
# ── Handle Extraction Result ──

if extraction_result is None:
    st.error("Extraction failed: No result returned by the file reader.", icon="❌")
    st.stop()

# Display extraction warnings, if any
if extraction_result.warnings:
    for warning in extraction_result.warnings:
        st.warning(warning)

# Check extraction status using the actual ExtractionResult method
if not extraction_result.is_ok():

    if extraction_result.errors:
        for error in extraction_result.errors:
            st.error(f"Extraction error: {error}", icon="❌")
    else:
        st.error(
            "Extraction failed: No valid transaction rows were extracted.",
            icon="❌"
        )

    st.stop()

# Get extracted dataframe
raw_df = extraction_result.dataframe

st.success(
    f"✓ Extracted {len(raw_df):,} raw transaction rows "
    f"from '{uploaded_file.name}'",
    icon="📄"
)


# ── Step 2: Validation ──
st.markdown("""
<div style="margin: 20px 0 12px 0;">
    <div style="font-size: 16px; font-weight: 700; color: #1F2933;">Pipeline Step 2: Privacy Check & Schema Validation</div>
</div>
""", unsafe_allow_html=True)

with st.spinner("Verifying schema and ensuring no sensitive data is present..."):
    val_result = validate_dataframe(raw_df)

# Check whether validation allows processing to continue
if not val_result.can_proceed:

    st.error(
        "Validation Rejected: This file does not conform to privacy or format requirements.",
        icon="🚫"
    )

    for err in val_result.errors:
        st.error(f"• {err}")

    # Show warnings, if any
    for warning in val_result.warnings:
        st.warning(warning)

    # Show invalid row count if available
    if val_result.invalid_count > 0:
        st.warning(
            f"{val_result.invalid_count} transaction rows were rejected during validation."
        )

    st.stop()

# Display validation warnings
for warning in val_result.warnings:
    st.warning(f"Note: {warning}")

# Use only validated rows for further processing
valid_df = val_result.valid_df

st.success(
    f"Schema verified: {len(valid_df):,} transactions cleared for carbon accounting.",
    icon="🛡️"
)

if valid_df.empty:
    st.error("No valid transactions available for processing.")
    st.stop()

if val_result.warnings:
    for w in val_result.warnings:
        st.warning(f"Note: {w}")

valid_df = val_result.valid_df
st.success(f"✓ Schema verified: {len(valid_df):,} transactions cleared for carbon accounting.", icon="🛡️")


# ── Step 3: Cleaning, Categorization, and Emissions ──
st.markdown("""
<div style="margin: 20px 0 12px 0;">
    <div style="font-size: 16px; font-weight: 700; color: #1F2933;">Pipeline Step 3: Categorization & India Factor Computation</div>
</div>
""", unsafe_allow_html=True)

progress_bar = st.progress(0, text="Initializing processing pipeline...")

with st.spinner("Cleaning merchant descriptions and normalizing payment channels..."):
    progress_bar.progress(20, text="Sanitizing descriptions...")

    cleaned_df = clean_dataframe(valid_df)

    if cleaned_df is None or cleaned_df.empty:
        st.error("Data cleaning failed or returned no transactions.")
        st.stop()

with st.spinner("Categorizing merchants via cache, ML, dictionary, and fuzzy tiers..."):
    progress_bar.progress(50, text="Running multi-tier categorization...")
    cat_df = categorize_dataframe(cleaned_df)

with st.spinner("Applying India-specific factors (CEA, HCES, BEE, MoEFCC)..."):
    progress_bar.progress(80, text="Calculating emissions...")
    final_df = apply_emissions_to_dataframe(cat_df)

progress_bar.progress(100, text="Pipeline execution complete!")


# ── Save to Database if Available ──
batch_id = str(uuid.uuid4())
saved_to_db = False

try:
    from database.connection import get_session
    from database.models import Transaction, InsightsHistory

    save_session = get_session()
    if save_session is not None:
        for _, row in final_df.iterrows():
            tx_obj = Transaction(
                batch_id=batch_id,
                transaction_date=pd.to_datetime(row["date"]).date() if pd.notna(row.get("date")) else None,
                raw_description=str(row.get("raw_description", "")),
                cleaned_description=str(row.get("cleaned_description", "")),
                amount=float(row["amount"]) if pd.notna(row.get("amount")) else 0.0,
                currency=str(row.get("currency", "INR")),
                payment_method=str(row.get("payment_method", "debit")),
                category=str(row["category"]) if pd.notna(row.get("category")) else None,
                subcategory=str(row["subcategory"]) if pd.notna(row.get("subcategory")) else None,
                category_status=str(row.get("category_status", "unclassified")),
                categorization_tier=safe_int(row.get("categorization_tier")),
                categorization_method=str(row.get("categorization_method", "")),
                categorization_confidence=float(row["categorization_confidence"]) if pd.notna(row.get("categorization_confidence")) else None,
                emissions_status=str(row.get("emissions_status", "unsupported")),
                estimated_co2e_kg=float(row["estimated_co2e_kg"]) if pd.notna(row.get("estimated_co2e_kg")) else None,
                emissions_confidence=str(row.get("emissions_confidence", "")),
                factor_id=str(row.get("factor_id", "")),
                factor_source=str(row.get("factor_source", "")),
                estimation_notes=str(row.get("estimation_notes", "")),
            )
            save_session.add(tx_obj)
        save_session.commit()
        saved_to_db = True
        save_session.close()
except Exception as db_exc:
    saved_to_db = False

# Update session state for instant dashboard usage
st.session_state["processed_df"] = final_df
st.session_state["last_batch_id"] = batch_id


# ── Success Confirmation ──
if saved_to_db:
    st.success(f"✓ All {len(final_df):,} transactions successfully processed and stored in database.", icon="💾")
else:
    st.info(f"✓ Processed {len(final_df):,} transactions in-session. (Database optional)", icon="✨")


# ── Summary Snapshot & Next Steps ──
metrics = compute_coverage_metrics(final_df)

st.markdown("""
<div style="margin: 28px 0 16px 0;">
    <div style="font-size: 18px; font-weight: 800; color: #1F2933;">Batch Summary & Impact</div>
</div>
""", unsafe_allow_html=True)

col_m1, col_m2, col_m3, col_m4 = st.columns(4)

with col_m1:
    tot_co2 = metrics.get("estimated_co2e_kg", 0.0)
    co2_str = f"{tot_co2:,.1f} kg CO₂e" if tot_co2 else "0.0 kg"
    st.metric("Total Batch Emissions", co2_str)

with col_m2:
    cov = metrics.get("supported_spend_pct", 0.0)
    st.metric("Spend Coverage", f"{cov:.1f}%")

with col_m3:
    st.metric("Estimated Transactions", metrics.get("estimated_count", 0))

with col_m4:
    st.metric("Unsupported Transactions", metrics.get("unsupported_count", 0))


# ── Direct Navigation to Dashboard ──
st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
col_nav1, col_nav2 = st.columns([1, 1])

with col_nav1:
    if st.button("📊 Open Dashboard to View Analytics", type="primary", use_container_width=True):
        st.switch_page("pages/2_Dashboard.py")

with col_nav2:
    if st.button("🔍 Explore All Transactions in Detail", use_container_width=True):
        st.switch_page("pages/4_Transactions.py")
