# Carbon Footprint Estimator — Antigravity

India-specific CO₂e estimation from bank transaction data.

## Overview

Upload a CSV, Excel, or PDF bank statement. The application validates, cleans,
categorizes merchants through a 5-tier pipeline, and estimates CO₂ emissions
using verified India-specific factors (CEA, HCES, BEE, MoEFCC).

> ⚠️ **Partial estimate**: Only transactions with supported India-specific factors
> are included in the total. This is not a complete carbon footprint assessment.

---

## Setup

### 1. Clone and create virtual environment

```bash
git clone <repo-url>
cd CfootAg4
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and add your DATABASE_URL (Supabase or local PostgreSQL)
```

**.env fields:**

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (Supabase pooled URL supported) |
| `LLM_API_KEY` | OpenAI/Anthropic key (optional, for Tier 5 LLM) |
| `LLM_MODEL` | LLM model name (e.g. `gpt-3.5-turbo`) |
| `ENABLE_LLM_FALLBACK` | `true` to enable Tier 5 LLM (default: `false`) |
| `ENABLE_EMBEDDING_FALLBACK` | `true` to enable Tier 4 embeddings (default: `false`) |
| `FUZZY_MATCH_THRESHOLD` | RapidFuzz threshold 0–100 (default: `90`) |
| `FUZZY_AMBIGUITY_GAP` | Minimum gap between top-2 fuzzy matches (default: `5`) |

### 4. Initialize database (optional)

```bash
python -c "from database.schema import initialize_db; initialize_db()"
```

### 5. Run the app

```bash
streamlit run dashboard/app.py
```

The app starts at [http://localhost:8501](http://localhost:8501).

---

## Running Tests

```bash
pytest
```

To see coverage:

```bash
pytest --cov=pipeline --cov=utils --cov=database --cov-report=term-missing
```

---

## Project Structure

```
.
├── dashboard/           # Streamlit frontend
│   ├── app.py           # Main page (home/landing)
│   └── pages/
│       ├── 1_Upload.py       # CSV/Excel/PDF upload + full pipeline
│       ├── 2_Dashboard.py    # CO2e overview and charts
│       ├── 3_Transactions.py # Transaction browser with filters
│       └── 4_Methodology.py  # Factor sources and methodology
├── database/            # SQLAlchemy models and schema
│   ├── base.py
│   ├── connection.py
│   ├── models.py
│   └── schema.py        # Table creation + India factor seeding
├── pipeline/            # Processing pipeline
│   ├── cleaning.py      # Merchant description normalization
│   ├── emissions.py     # CO2e calculation engine (Route A + B)
│   └── categorization/
│       ├── categories.py    # Canonical category enum
│       ├── tier0_cache.py   # DB merchant cache
│       ├── tier1_classifier.py  # TF-IDF + Logistic Regression
│       ├── tier2_dictionary.py  # Exact alias matching
│       ├── tier3_fuzzy.py   # RapidFuzz matching
│       ├── tier4_embedding.py   # Sentence embeddings (optional)
│       ├── tier5_llm.py     # LLM fallback (optional, disabled by default)
│       └── pipeline.py      # Orchestrator
├── utils/
│   ├── validation.py         # CSV/DataFrame validation + Pydantic model
│   └── file_readers/
│       ├── base.py
│       ├── csv_reader.py
│       ├── excel_reader.py
│       └── pdf_reader.py
├── models/              # Trained ML artifacts (gitignored)
├── tests/               # pytest test suite
│   ├── fixtures/        # Sample CSV files for testing
│   ├── test_validation.py
│   ├── test_cleaning.py
│   ├── test_emissions.py
│   └── test_categorization.py
├── .env.example         # Environment variable template
├── .gitignore
├── pytest.ini
└── requirements.txt
```

---

## Supported File Formats

| Format | Notes |
|---|---|
| `.csv` | UTF-8 or latin-1 encoded |
| `.xlsx` | Excel (no macros) |
| `.xls` | Legacy Excel |
| `.pdf` | Text-based PDFs only; scanned/image PDFs are not supported |

**Required columns:** `date`, `description`, `amount`  
**Optional:** `currency` (default: INR), `payment_method`

---

## Categorization Pipeline

Tiers run in order; higher-confidence results are never overwritten:

| Tier | Method | Notes |
|---|---|---|
| 0 | Merchant cache (DB) | Instant lookup for known merchants |
| 1 | TF-IDF + Logistic Regression | Requires trained model in `models/` |
| 2 | Dictionary / exact alias | Curated India-relevant alias map |
| 3 | RapidFuzz fuzzy matching | Threshold: 90, gap: 5 |
| 4 | Sentence embeddings | Optional (`ENABLE_EMBEDDING_FALLBACK=true`) |
| 5 | LLM fallback | Optional (`ENABLE_LLM_FALLBACK=true`), disabled by default |

---

## India-Specific Emission Factors

All factors are India-specific. No UK DEFRA / US EPA factors are used.

| Category | Factor ID | Type | Source |
|---|---|---|---|
| Electricity | `IN-CEA-ELECTRICITY-SPEND` | Spend-based | CEA V21.0 |
| LPG | `IN-MOEFCC-LPG-SPEND` | Spend-based | MoEFCC LCL |
| Petrol | `IN-BEE-PETROL-SPEND` | Spend-based | BEE India |
| Diesel | `IN-BEE-DIESEL-SPEND` | Spend-based | BEE India |
| Grocery | `IN-HCES-BASIC-GROCERY` | Spend-based | HCES India |
| Dairy | `IN-HCES-MILK-AND-DAIRY` | Spend-based | HCES India |
| … | … | … | … |

See the **Methodology & Sources** page in the app for the full registry.

---

## Privacy

- Files containing account numbers, card numbers, IFSC, UPI IDs, CVV, PINs, or passwords are **rejected outright**.
- We use a strict Pydantic model (`extra='forbid'`) — no unknown fields can enter the processing pipeline.
- Original uploaded files are not stored. Only cleaned, minimized transaction data is persisted.
- Never commit a real `.env` file. Only `.env.example` is tracked in git.

---

## Unsupported Categories

Categories with no current active India-specific factor (e.g. restaurants, clothing, e-commerce, air travel) always return `estimated_co2e_kg = NULL` — never `0`. See the Methodology page for the full list.

---

## License

MIT — see LICENSE file.
