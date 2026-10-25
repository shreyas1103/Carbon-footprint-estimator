"""
dashboard/pages/1_Upload.py
Upload page: CSV, Excel, and PDF transaction upload with validation and processing.
Full pipeline: validate → clean → categorize → estimate → (save to DB if available).
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
import streamlit as st

def safe_int(value):
    if value is None or pd.isna(value):
        return None
    return int(value)
from pipeline.categorization.pipeline import categorize_dataframe
from pipeline.cleaning import clean_dataframe
from pipeline.emissions import apply_emissions_to_dataframe, compute_coverage_metrics
from utils.file_readers.csv_reader import read_csv
from utils.file_readers.excel_reader import read_excel
from utils.file_readers.pdf_reader import read_pdf
from utils.validation import validate_dataframe, MAX_FILE_BYTES
from datetime import date
today = date.today()
st.set_page_config(
    page_title="Upload Transactions — Carbon Footprint Estimator",
    page_icon="📁",
    layout="wide",
)

st.title("📁 Upload Transactions")
st.caption(
    "Upload a bank statement CSV, Excel, or PDF to estimate your carbon footprint. "
    "We accept: date, description, amount, (optional) currency, payment_method columns only."
)

# ---- Privacy notice ----
with st.expander("🔒 Privacy & Security", expanded=False):
    st.markdown("""
**What we accept:** `date`, `description`, `amount`, and optionally `currency`, `payment_method`.

**What we reject:** Any column resembling account numbers, card numbers, IFSC codes, UPI IDs,
CVV, PINs, OTPs, passwords, or other sensitive financial identifiers.
If such a column is found, the entire file is rejected with a clear explanation.

**Storage:** We use a strict Pydantic model (`extra='forbid'`) so only allowed fields
enter our processing pipeline. We do not store the original uploaded file.
Only the processed transaction data (no raw account identifiers) is saved to the database.

**Currency:** Only INR transactions are used for emissions estimates. Other currencies are
flagged and excluded from calculations until a validated exchange rate is applied.
    """)

# ---- File uploader ----
MAX_MB = MAX_FILE_BYTES // (1024 * 1024)
uploaded_file = st.file_uploader(
    f"Choose a file (max {MAX_MB} MB)",
    type=["csv", "xlsx", "xls", "pdf"],
    key="transaction_file_upload",
    help="Supported: CSV, Excel (.xlsx, .xls), PDF (text-based bank statements only)",
)

if not uploaded_file:
    st.info("Upload a file above to get started.", icon="👆")
    st.stop()

# ---- Check file size ----
file_bytes = uploaded_file.read()
if len(file_bytes) > MAX_FILE_BYTES:
    st.error(
        f"File too large ({len(file_bytes) / 1024 / 1024:.1f} MB). "
        f"Maximum allowed: {MAX_MB} MB. Please reduce the file size.",
        icon="🚫",
    )
    st.stop()

file_ext = uploaded_file.name.rsplit(".", 1)[-1].lower()

# ---------------------------------------------------------------------------
# Step 1: Extract (parse) the file
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Step 1: File Extraction")

extraction_result = None

if file_ext == "csv":
    with st.spinner("Parsing CSV..."):
        extraction_result = read_csv(file_bytes)

elif file_ext in ("xlsx", "xls"):
    with st.spinner("Reading Excel file..."):
        # First pass to detect sheets
        initial_result = read_excel(file_bytes, worksheet_name=None)

    if initial_result.requires_user_review and initial_result.warnings:
        # Ask user to pick a sheet
        import io
        try:
            if file_ext == "xls":
                xf = pd.ExcelFile(io.BytesIO(file_bytes), engine="xlrd")
            else:
                xf = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")
            sheet_names = xf.sheet_names
        except Exception:
            sheet_names = []

        if sheet_names:
            selected_sheet = st.selectbox(
                "Multiple worksheets found. Select the one containing transactions:",
                sheet_names,
                key="sheet_selector",
            )
            with st.spinner(f"Parsing worksheet: {selected_sheet}"):
                extraction_result = read_excel(file_bytes, worksheet_name=selected_sheet)
        else:
            st.error("Could not read the Excel file structure.")
            st.stop()
    else:
        extraction_result = initial_result

elif file_ext == "pdf":
    with st.spinner("Extracting tables from PDF (text-based only)..."):
        extraction_result = read_pdf(file_bytes)

else:
    st.error(f"Unsupported file type: .{file_ext}. Please upload a CSV, Excel, or PDF.")
    st.stop()

# ---- Show extraction errors ----
if extraction_result.errors:
    for err in extraction_result.errors:
        st.error(err, icon="🚫")
    if not extraction_result.is_ok():
        st.stop()

# ---- Show extraction warnings ----
for warn in extraction_result.warnings:
    st.warning(warn, icon="⚠️")

if extraction_result.rows_extracted > 0:
    st.success(
        f"✓ Extracted **{extraction_result.rows_extracted}** rows "
        f"from {file_ext.upper()} file via `{extraction_result.source_parser}`.",
        icon="✅",
    )

# ---------------------------------------------------------------------------
# Step 2: Validation
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Step 2: Validation")

with st.spinner("Validating data..."):
    validation_result = validate_dataframe(
        extraction_result.dataframe, source_type=extraction_result.source_file_type
    )

# ---- Show validation errors ----
if validation_result.errors:
    for err in validation_result.errors:
        st.error(err, icon="🚫")
    if not validation_result.can_proceed:
        st.stop()

# ---- Show validation warnings ----
for warn in validation_result.warnings:
    st.warning(warn, icon="⚠️")

# ---- Summary ----
col1, col2, col3 = st.columns(3)
col1.metric("✅ Valid rows", validation_result.valid_count)
col2.metric("❌ Invalid rows", validation_result.invalid_count)
col3.metric("📋 Total extracted", extraction_result.rows_extracted)

# ---- Invalid rows detail ----
if validation_result.invalid_rows:
    with st.expander(f"View {validation_result.invalid_count} invalid rows", expanded=False):
        inv_data = [
            {"Row": r.row_number, "Column": r.column or "—", "Issue": r.issue}
            for r in validation_result.invalid_rows
        ]
        st.dataframe(pd.DataFrame(inv_data), use_container_width=True)

# ---- Preview valid rows ----
st.markdown("**Preview (first 10 valid rows):**")
st.dataframe(
    validation_result.valid_df.head(10),
    use_container_width=True,
)

if not validation_result.can_proceed:
    st.error("No valid rows to process. Please fix the issues and upload again.")
    st.stop()

# ---------------------------------------------------------------------------
# Step 3: Confirm and Process
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Step 3: Process")

# Use session state to prevent reprocessing on every Streamlit rerun
if "processing_batch_id" not in st.session_state:
    st.session_state["processing_batch_id"] = None
if "processed_df" not in st.session_state:
    st.session_state["processed_df"] = None

process_btn = st.button(
    "🚀 Process Transactions",
    type="primary",
    key="btn_process_transactions",
    help="Clean, categorize, and estimate emissions for all valid rows.",
)

if process_btn:
    batch_id = str(uuid.uuid4())
    st.session_state["processing_batch_id"] = batch_id

    df = validation_result.valid_df.copy()

    # Progress bar
    progress = st.progress(0, text="Starting pipeline...")

    # Step 3a: Clean
    progress.progress(10, text="Cleaning merchant descriptions...")
    df = clean_dataframe(df)
    progress.progress(30, text="Cleaning complete.")

    # Step 3b: Categorize
    # Use a dedicated read-session for Tier 0 cache — isolated from the save session.
    progress.progress(35, text="Categorizing merchants (Tier 0–5 pipeline)...")
    cat_session = None
    try:
        from database.connection import get_session
        cat_session = get_session()
    except Exception:
        pass

    try:
        df = categorize_dataframe(df, session=cat_session)
    finally:
        if cat_session:
            try:
                cat_session.rollback()  # reset any failed queries
            except Exception:
                pass
            cat_session.close()

    progress.progress(70, text="Categorization complete.")

    # Step 3c: Emissions
    progress.progress(75, text="Estimating CO₂e emissions...")
    df["batch_id"] = batch_id
    df["source_row_number"] = range(1, len(df) + 1)
    df = apply_emissions_to_dataframe(df)
    progress.progress(90, text="Emissions calculated.")

    # Step 3d: Save to DB (if available) — fresh session, independent of categorization.
    saved_to_db = False
    save_session = None
    try:
        from database.connection import get_session
        save_session = get_session()
        if save_session:
            from database.models import Transaction
            from datetime import date as _date

            for _, row in df.iterrows():
                # Idempotency check: skip if (batch_id, source_row_number) exists
                existing = (
                    save_session.query(Transaction)
                    .filter_by(
                        batch_id=str(row["batch_id"]),
                        source_row_number=int(row["source_row_number"]),
                    )
                    .first()
                )
                if existing:
                    continue

                t = Transaction(
                    batch_id=str(row["batch_id"]),
                    source_row_number=safe_int(row.get("source_row_number")),
                    transaction_date=row.get("date"),
                    description=str(
                       row.get("description")
                       if pd.notna(row.get("description"))
                       else row.get("raw_description", row.get("cleaned_description", ""))
                    ),
                    raw_description=str(row.get("raw_description", row.get("description", ""))),
                    cleaned_description=str(row.get("cleaned_description", "")),
                    amount=float(row.get("amount", 0)),
                    currency=str(row.get("currency", "INR") or "INR"),
                    payment_method=row.get("payment_method"),
                    merchant_key=row.get("merchant_key"),
                    merchant_name=row.get("cleaned_description"),
                    category=row.get("category"),
                    subcategory=row.get("subcategory"),
                    category_status=row.get("category_status"),
                    categorization_tier=safe_int(row.get("categorization_tier")),
                    categorization_method=row.get("categorization_method"),
                    categorization_confidence=row.get("categorization_confidence"),
                    factor_id=row.get("factor_id"),
                    factor_method=row.get("factor_method"),
                    activity_quantity=row.get("activity_quantity"),
                    activity_unit=row.get("activity_unit"),
                    estimated_co2e_kg=row.get("estimated_co2e_kg"),
                    emissions_status=row.get("emissions_status"),
                    emissions_confidence=(
                        str(row["emissions_confidence"])
                        if pd.notna(row.get("emissions_confidence"))
                        else None
                    ),
                    factor_source=row.get("factor_source"),
                    factor_year=safe_int(row.get("factor_year")),
                    estimation_notes=row.get("estimation_notes"),
                )
                save_session.add(t)

            for obj in save_session.new:
             if isinstance(obj, Transaction):
                print("\n========== TRANSACTION DEBUG ==========")

                print("source_row_number:", repr(obj.source_row_number))
                print("categorization_tier:", repr(obj.categorization_tier))
                print("factor_year:", repr(obj.factor_year))
                print("amount:", repr(obj.amount))
                print("categorization_confidence:", repr(obj.categorization_confidence))
                print("activity_quantity:", repr(obj.activity_quantity))
                print("estimated_co2e_kg:", repr(obj.estimated_co2e_kg))

                print("=======================================\n")
            save_session.commit()

            # Save summary to insights_history
            metrics = compute_coverage_metrics(df)
            from database.models import InsightsHistory
            insight = InsightsHistory(
                batch_id=batch_id,
                month=today.month,
                year=today.year,
                total_spend_inr=metrics["total_expense_spend_inr"],
                estimated_co2e_kg=metrics["estimated_co2e_kg"],
                supported_spend_inr=metrics["supported_spend_inr"],
                supported_spend_pct=metrics["supported_spend_pct"],
                transaction_count=metrics["total_transactions"],
                estimated_transaction_count=metrics["estimated_count"],
                unsupported_transaction_count=metrics["unsupported_count"],
                methodology_version="1.0",
            )
            save_session.add(insight)
            save_session.commit()
            saved_to_db = True
    except Exception as exc:
        import traceback
        if save_session:
            try:
                save_session.rollback()
            except Exception:
                pass
        st.error(f"Database save failed: {exc}")
        st.code(traceback.format_exc())
    finally:
        if save_session:
            save_session.close()

    progress.progress(100, text="Pipeline complete!")
    st.session_state["processed_df"] = df
    st.session_state["last_batch_id"] = batch_id

    if saved_to_db:
        st.success("✓ Data saved to database.", icon="💾")
    else:
        st.info("Database not configured — results are in-session only.", icon="ℹ️")


# ---------------------------------------------------------------------------
# Step 4: Results
# ---------------------------------------------------------------------------
processed_df = st.session_state.get("processed_df")

if processed_df is not None:
    st.divider()
    st.subheader("Step 4: Results")

    metrics = compute_coverage_metrics(processed_df)

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "🌿 Estimated CO₂e",
        f"{metrics['estimated_co2e_kg']:.2f} kg" if metrics['estimated_co2e_kg'] else "—",
        help="Sum of emissions for transactions with a valid India factor only.",
    )
    col2.metric(
        "📊 Spend Coverage",
        f"{metrics['supported_spend_pct']:.1f}%" if metrics['supported_spend_pct'] else "—",
        help="% of eligible INR spend covered by supported emissions factors.",
    )
    col3.metric("✅ Estimated", metrics["estimated_count"])
    col4.metric("❓ Unsupported", metrics["unsupported_count"])

    st.warning(
        "⚠️ This total represents only the transactions with supported India-specific factors. "
        "It is **not** your complete carbon footprint.",
        icon="ℹ️",
    )

    # Results tabs
    tab1, tab2, tab3 = st.tabs(["📋 All Transactions", "❓ Unsupported / Review", "⬇️ Download"])

    with tab1:
        display_cols = [
            "date", "cleaned_description", "amount", "currency",
            "category", "category_status", "emissions_status",
            "estimated_co2e_kg", "emissions_confidence", "estimation_notes",
        ]
        available = [c for c in display_cols if c in processed_df.columns]
        st.dataframe(processed_df[available], use_container_width=True)

    with tab2:
        unsupported = processed_df[
            processed_df.get("emissions_status", pd.Series(dtype=str)).isin(
                ["unsupported", "needs_review"]
            )
        ] if "emissions_status" in processed_df.columns else pd.DataFrame()

        if unsupported.empty:
            st.success("All transactions have emissions estimates!", icon="✅")
        else:
            st.info(
                f"{len(unsupported)} transactions could not be estimated. "
                "Reasons are shown in 'estimation_notes'."
            )
            review_cols = [
                "date", "cleaned_description", "amount", "category",
                "emissions_status", "estimation_notes",
            ]
            avail = [c for c in review_cols if c in unsupported.columns]
            st.dataframe(unsupported[avail], use_container_width=True)

    with tab3:
        # Remove sensitive columns before download
        safe_cols = [
            c for c in processed_df.columns
            if c not in ("raw_description",)  # keep cleaned only
        ]
        csv_download = processed_df[safe_cols].to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download processed CSV",
            data=csv_download,
            file_name=f"carbon_footprint_{st.session_state.get('last_batch_id', 'export')[:8]}.csv",
            mime="text/csv",
            key="btn_download_csv",
        )
        st.caption(
            "The downloaded file contains cleaned data only — no raw transaction references or account identifiers."
        )
