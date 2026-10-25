# Carbon Footprint Estimator — Antigravity Implementation Specification
**Scope:** Complete Release 1 (Milestones 1.1–1.4) and Release 2 (Milestones 2.1–2.5) for the existing Carbon Footprint Estimator from Spending Data project. Build the frontend and backend together, integrate with PostgreSQL/Supabase, and make the application runnable end-to-end.

> **Important implementation rule:** First inspect the existing repository and preserve working code, naming, and dependencies wherever possible. Extend/refactor only when necessary. Do not replace the project with a different framework without a clear reason. The roadmap names a Streamlit frontend and Python backend; use Streamlit + Python unless the repository already has a deliberate, working alternative. Do not invent carbon factors for unsupported categories.

---

## 1. Product goal and user workflow

A user uploads a CSV of bank transactions. The application validates it, normalizes merchant descriptions, categorizes merchants through a five-tier pipeline, estimates emissions only when a valid India-relevant factor is available, and displays a dashboard with clear uncertainty and coverage information.

Primary flow:
1. Open dashboard.
2. Upload a CSV.
3. See validation results and preview.
4. Confirm/continue with valid transactions.
5. Clean merchant descriptions.
6. Categorize merchants through Tier 0–5.
7. Review low-confidence and unsupported transactions.
8. Estimate CO₂e using the hybrid methodology described below.
9. Display totals, category breakdown, monthly trend, and estimation coverage.
10. Save records and insight history in PostgreSQL only when the data flow explicitly requests persistence; avoid duplicate inserts on reruns.

Privacy-first requirements:
- Accept only the allowlisted transaction columns.
- Reject CSVs containing sensitive account/card identifiers (see validation section).
- Never log raw account identifiers, secrets, API keys, or complete uploaded transaction rows.
- Never store bank credentials or ask for them.
- Secrets belong in `.env`, which must be gitignored. Commit `.env.example`, never a real `.env`.

## 2. Preserve/inspect existing project structure

Expected modules from the current project/roadmap (adapt paths to the actual repository rather than creating duplicate alternatives):

```text
.
├── dashboard/
│   ├── app.py
│   └── pages/
│       └── 1_Upload.py
├── database/
│   ├── base.py
│   ├── connection.py
│   ├── models.py
│   └── schema.py
├── db/
│   ├── schema.sql
│   └── queries.py                 # if the repository already uses db/
├── pipeline/
│   ├── cleaning.py                # or pipeline/cleaning.py
│   ├── categorization/
│   │   ├── tier0_cache.py
│   │   ├── tier1_classifier.py
│   │   ├── tier2_dictionary.py
│   │   ├── tier3_fuzzy.py
│   │   ├── tier4_embedding.py
│   │   └── tier5_llm.py
│   └── pipeline.py
├── utils/
│   └── validation.py
├── models/                         # trained artifacts, if used
├── notebooks/
│   └── model_training.ipynb
├── tests/
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

The repository may already use `dashboard/pages/1_Upload.py`, `utils/validation.py`, `pipeline/cleaning.py`, `db/schema.sql`, `db/connection.py`, and `db/queries.py`. Reuse these instead of creating competing modules. Keep imports consistent with the actual project. Avoid import-time database connections or API calls.

## 3. Technology and configuration

- Python 3.10+ (use the version already supported by the project).
- Streamlit for frontend.
- Pandas for tabular processing and previews.
- SQLAlchemy 2.x for PostgreSQL access.
- `psycopg` or the already-installed PostgreSQL driver.
- `python-dotenv` for local configuration.
- `rapidfuzz` for fuzzy merchant matching.
- `scikit-learn` for TF-IDF/logistic regression.
- `sentence-transformers` only for Tier 4 and load lazily; do not download/load a large model at app startup if not needed.
- LLM SDK only if Tier 5 is configured. Tier 5 must be optional and fail safely.
- `pytest` for automated tests.
- Use Supabase's **pooled connection string** when several team members or Streamlit sessions share the database. Never hardcode credentials.

`.env.example` should document (with blank placeholders):
```env
DATABASE_URL=
LLM_API_KEY=
LLM_MODEL=
ENABLE_LLM_FALLBACK=false
ENABLE_EMBEDDING_FALLBACK=false
FUZZY_MATCH_THRESHOLD=90
FUZZY_AMBIGUITY_GAP=5
```
Do not put actual keys or real database URLs in the file. Support a Supabase URL with SQLAlchemy's required driver syntax; do not print credentials in errors.

## 4. Data input contract and CSV validation (Milestone 1.3)

### Required columns
- `date`
- `description`
- `amount`

### Optional allowlisted columns
- `currency`
- `payment_method`

Normalize header whitespace/case before matching, e.g. ` Date ` → `date`. Do not accept arbitrary columns into the processing pipeline.

### Reject sensitive columns
Reject the upload with a clear, non-sensitive error if any column resembles:
- account number / account no / account_number
- account holder or customer ID
- card number / debit card / credit card / CVV / expiry
- IFSC
- UPI ID / UPI handle
- bank account identifiers
- passwords, PINs, OTPs, authentication tokens
- other columns that clearly expose financial account identifiers

Use normalized header names and a conservative denylist/regex. Do not echo sensitive values. Explain that the user should remove those columns and upload again. Do not silently drop a sensitive column and continue.

### Type and row validation
- `date`: parse to a date/datetime; invalid dates are row-level errors.
- `description`: must be a non-empty string after trimming; blank values are invalid.
- `amount`: numeric and finite. Reject nonnumeric, NaN, or infinite amounts.
- Accept positive expenses and negative refunds/credits, but document the convention. Do not convert every amount to absolute value silently.
- For carbon estimates, process expense transactions only by default (`amount > 0` if the input convention is expenses-positive). Negative transactions/refunds should be retained and clearly marked as excluded from the first version's emissions total unless a deliberate refund policy is implemented.
- Currency: default to INR only when omitted and make this assumption visible in the UI. If a provided currency is not INR, do not apply INR factors without a validated conversion rate. Mark unsupported/blocked until converted using a dated, sourced exchange rate. Do not silently treat other currencies as INR.
- Empty files, files with only headers, duplicate headers, malformed CSV, oversized uploads, and no valid rows must show clear messages.
- Keep row number and validation issue for each invalid row.
- Show valid/invalid counts and a preview before processing.
- Upload validation must not require a database connection.

Expected validation output: a structured result with `valid_df`, `invalid_rows`/issues, `warnings`, and a boolean indicating whether the upload can proceed.

## 5. Database schema and data integrity (Milestone 1.2)

Use the repository's existing model conventions, but implement equivalent structures. PostgreSQL types must be appropriate; use `NUMERIC`/`DECIMAL` for currency and factor values, not binary floating-point for stored money.

### 5.1 `transactions`
Recommended fields:
- `id` primary key (UUID or identity; use one consistent convention)
- `batch_id` UUID/string identifying one upload/import batch
- `transaction_date` DATE
- `raw_description` TEXT
- `cleaned_description` TEXT
- `amount` NUMERIC(14,2)
- `currency` VARCHAR(3), default `INR` only if absent from input and assumption is recorded
- `payment_method` TEXT nullable
- `merchant_key` TEXT nullable
- `merchant_name` TEXT nullable
- `category` TEXT nullable
- `subcategory` TEXT nullable
- `category_status` TEXT (e.g. `categorized`, `needs_review`, `unclassified`)
- `categorization_tier` SMALLINT nullable (0–5)
- `categorization_method` TEXT nullable
- `categorization_confidence` NUMERIC(5,4) nullable, range 0–1
- `factor_id` TEXT nullable
- `factor_method` TEXT nullable (`spend_based` or `activity_based`)
- `activity_quantity` NUMERIC nullable
- `activity_unit` TEXT nullable
- `estimated_co2e_kg` NUMERIC(14,4) nullable
- `emissions_status` TEXT (`estimated`, `unsupported`, `excluded_refund`, `needs_review`, `error`)
- `emissions_confidence` TEXT nullable (`high`, `medium`, `low`)
- `factor_source` TEXT nullable
- `factor_year` INTEGER nullable
- `estimation_notes` TEXT nullable
- `created_at`, `updated_at` timestamps

Rules:
- `estimated_co2e_kg = NULL` when no applicable factor exists. **Never store 0 as a substitute for unknown/unsupported emissions.**
- Do not store a factor ID unless it points to a known factor.
- Save original description and normalized description separately.
- Add a unique/idempotency strategy, such as unique `(batch_id, source_row_number)` or a stable import row key, to avoid duplicate inserts on Streamlit reruns.
- Add indexes for `batch_id`, `transaction_date`, `category`, `merchant_key`, `factor_id`, and any frequent lookup fields. Avoid excessive indexing.
- Add a constraint for confidence values to be between 0 and 1.

### 5.2 `merchant_cache`
Recommended fields:
- `id`
- `raw_merchant` or normalized merchant key (unique after normalization)
- `clean_merchant`
- `category`
- `subcategory` nullable
- `confidence` NUMERIC(5,4)
- `source` / `method`
- `tier` SMALLINT
- `review_status` (e.g. `approved`, `auto`, `needs_review`)
- `created_at`
- `last_used`
- `updated_at`

Cache only stable merchant/category decisions. Cache writes from LLM/fuzzy results should follow confidence/review policy; uncertain decisions must not become trusted Tier 0 results. A user correction, if implemented, should be explicitly confirmed before it becomes an approved cache entry.

### 5.3 `insights_history`
Recommended fields:
- `id`
- `batch_id`
- `generated_at`
- `total_spend_inr` NUMERIC(14,2)
- `estimated_co2e_kg` NUMERIC(14,4) nullable
- `supported_spend_inr` NUMERIC(14,2)
- `supported_spend_pct` NUMERIC(5,2)
- `transaction_count`
- `estimated_transaction_count`
- `unsupported_transaction_count`
- `methodology_version`
- `summary_json` JSONB nullable

Persist only aggregate insight data necessary for history. Avoid duplicating sensitive transaction data in this table.

### 5.4 Carbon factor registry
Maintain a factor registry (database table or versioned data file loaded by the app) with:
- `factor_id` (unique)
- `category` / `subcategory`
- `factor_type` (`spend_based` or `activity_based`)
- `value`
- `unit` (`kgCO2e/INR`, `kgCO2/kWh`, `kgCO2/L`, `kgCO2/kg`, etc.)
- `country` (India for the factors below)
- `base_year` / `reference_year`
- `source_name`, `source_reference`, `source_version`
- `confidence`
- `valid_from`, `valid_to` nullable
- `methodology_notes`
- `active` boolean

Factor registry and transaction `factor_id` must not be conflated. Keep physical factors and spend-based factors as separate records with different IDs, even when derived from the same source.

## 6. India-specific hybrid carbon estimation approach

Use the hybrid approach below. All factors must have country, year, source, unit, method, and confidence recorded. The current factor workbook is India-based. **Do not use UK DEFRA spend factors, UK electricity factors, US EPA factors, PPP conversion, or a foreign factor as a silent fallback for Indian transactions.** Foreign reference factors may remain in a research workbook, but they are not active production factors for India.

### Route A — Spend-based factor
Formula:
`estimated_co2e_kg = spend_inr × factor_kgco2e_per_inr`

Use only when a defensible India-specific spend factor exists for a reasonably coherent category. These factors can be derived from physical factors and HCES spend/quantity data, but if the app multiplies rupees directly by the resulting factor, the runtime method is still `spend_based`.

### Route B — Activity-based factor
Formula:
`activity_quantity = spend_inr / effective_price_per_unit`
`estimated_co2e_kg = activity_quantity × physical_factor_kgco2e_per_unit`

Use only when:
- the transaction/category has a meaningful physical unit,
- the quantity bridge is defensible,
- price per unit is sourced/current and applicable to the user's region/tariff, or the user supplies quantity,
- fixed fees/taxes/standing charges are handled or disclosed.

Prefer Route B when the user provides an actual quantity (e.g. litres, kWh, kg). If quantity is inferred from spend and an assumed average price, label it as an estimate and lower confidence. Do not claim precision that the source data does not support.

### Important no-double-counting rule
- A factor in `kgCO2e/INR` is used by multiplying spending directly.
- A factor in `kgCO2/kWh`, `kgCO2/L`, or `kgCO2/kg` is used only after obtaining a quantity in that unit.
- Never multiply spend by a spend factor and then multiply the result by a physical factor.
- If using a spend factor derived from HCES and a physical factor, the derived spend factor is already the final spend factor at runtime.

### Active India factor data supplied by the project workbook

Load the following rows as **spend-based factors** (kgCO2e/INR). These values are from the current project workbook and must be traceable to its source/methodology metadata. Preserve the exact values; do not round in storage.

| factor_id | Category | Value (kgCO2e/INR) | Confidence | Use rule |
|---|---|---:|---|---|
| `IN-HCES-RICE-AND-RICE-PRODUCTS` | Food > Rice and rice products | 0.07048581883787187 | medium | Only if classifier/mapping specifically supports rice; not a universal grocery factor |
| `IN-HCES-WHEAT-AND-WHEAT-PRODUCTS` | Food > Wheat and wheat products | 0.01210098015315142 | medium | Specific category only |
| `IN-HCES-COARSE-GRAINS` | Food > Coarse grains | 0.005561874060700431 | medium | Specific category only |
| `IN-HCES-PULSES-AND-PULSE-PRODUCTS` | Food > Pulses | 0.004027566759451551 | medium | Specific category only |
| `IN-HCES-SUGAR-AND-SWEETENERS` | Food > Sugar and sweeteners | 0.003699943926194361 | medium | Specific category only |
| `IN-HCES-MILK-AND-DAIRY` | Food > Milk and dairy | 0.1255438890163547 | medium | Dairy-specific transactions only |
| `IN-HCES-MEAT-FISH-(EXCLUDING-EGGS)` | Food > Meat and fish | 0.06844688332133109 | medium | Do not use for eggs unless source mapping explicitly permits it |
| `IN-HCES-EDIBLE-OILS` | Food > Edible oils | 0.01840805461327834 | medium | Specific category only |
| `IN-HCES-VEGETABLES-(KG-BASED-ITEMS)` | Food > Vegetables | 0.00124394517499368 | medium | Category average; source basis is limited |
| `IN-HCES-FRESH-FRUIT-(KG-BASED-ITEMS)` | Food > Fresh fruit | 0.0006504095558087095 | medium | Category average; source basis is limited |
| `IN-HCES-BASIC-GROCERY` | Food > Basic grocery basket | 0.04246780031372872 | medium | Only for grocery merchants where a mixed grocery basket is plausible; not restaurants/food delivery |
| `IN-CEA-ELECTRICITY-SPEND` | Utilities > Electricity bill | 0.1325303878714435 | high | Spend-based factor at runtime; do not apply kWh factor again |
| `IN-MOEFCC-LPG-SPEND` | Utilities > LPG/cooking gas | 0.04715845926839721 | high | Spend-based factor at runtime; do not apply LPG physical factor again |
| `IN-BEE-PETROL-SPEND` | Transport fuel > Petrol | 0.02209753236010448 | high | Only when petrol is known |
| `IN-BEE-DIESEL-SPEND` | Transport fuel > Diesel | 0.02853545300348392 | high | Only when diesel is known |
| `IN-HCES-VEHICLE-FUEL-COMBINED-SPEND` | Transport fuel > Unknown vehicle fuel | 0.02470813417651744 | high | Use only when fuel type is genuinely unknown and a combined estimate is acceptable; label blended estimate |

**Factor ID safety:** If the workbook uses an ID like `IN-CEA-ELECTRICITY` for a spend factor, rename it to an unambiguous spend ID such as `IN-CEA-ELECTRICITY-SPEND`. Keep physical IDs separate. Never use the same ID for two units/methods.

### Physical activity factors available from the project workbook (Route B only)
These are not spend factors:
- `IN-ELEC-CEA-V21-2024-25`: `0.7117 kgCO2/kWh`, India, CEA V21.0, FY 2024–25. Use only with actual/inferred kWh.
- `IN-LPG-MOEF-LCL`: `3.13 kgCO2/kg LPG`, MoEFCC Low Carbon Lifestyles source. Use only with actual/inferred kg LPG.
- Petrol: `2.27 kgCO2/L`, India road-fuel reference cited by project workbook/DPIIT/WRI India context. Keep source traceability and verify the exact source citation in the workbook before describing it as officially verified.
- Diesel: `2.64 kgCO2/L`, India road-fuel reference cited by project workbook/DPIIT/WRI India context. Keep source traceability and verify exact citation before describing it as officially verified.
- `0.82 kgCO2/kWh` from older MoEFCC source is historical/superseded; do not use as current default when the CEA V21.0 factor is configured.

Route B should be preferred if a reliable quantity is supplied by the user (for example, kWh from an electricity bill or litres from a fuel receipt). If the system only has spend and cannot defend a local unit price, use an eligible Route A factor instead. Do not infer kWh from bill amount if the bill contains significant fixed charges and no suitable effective tariff is known.

### Category mapping and policy

Use canonical categories and subcategories. Merchant names alone do not always reveal the actual purchased product. A fuel station description may not reveal petrol vs diesel; a supermarket may sell both supported and unsupported items. Apply the following conservative mapping:

| Canonical category | Examples / transaction signals | Estimation rule |
|---|---|---|
| `utilities.electricity` | Electricity board/provider, electricity bill | Route B if kWh and physical factor available; otherwise `IN-CEA-ELECTRICITY-SPEND` Route A |
| `utilities.lpg` | LPG cylinder refill, cooking gas | Route B if kg known or inferable with defensible price; otherwise `IN-MOEFCC-LPG-SPEND` Route A |
| `transport_fuel.petrol` | Petrol pump / petrol receipt where petrol is explicit | Route B if litres known or defensibly inferred; otherwise `IN-BEE-PETROL-SPEND` |
| `transport_fuel.diesel` | Diesel pump / diesel receipt where diesel is explicit | Route B if litres known or defensibly inferred; otherwise `IN-BEE-DIESEL-SPEND` |
| `transport_fuel.unknown` | Fuel station, type not identifiable | Use combined spend factor only if accepted as a disclosed blended estimate; otherwise unsupported/needs review |
| `food.rice` | Explicit rice purchase / identifiable item | Route A rice factor |
| `food.wheat_products` | Explicit wheat/flour/wheat products | Route A wheat factor |
| `food.coarse_grains` | Explicit coarse grains | Route A coarse grains factor |
| `food.pulses` | Explicit pulses/dal | Route A pulses factor |
| `food.sugar_sweeteners` | Sugar/sweeteners | Route A sugar factor |
| `food.milk_dairy` | Milk, curd, cheese, dairy-specific merchant/description | Route A dairy factor |
| `food.meat_fish` | Meat/fish purchases | Route A meat/fish factor; do not include eggs by default |
| `food.edible_oils` | Cooking oil | Route A edible oil factor |
| `food.vegetables` | Explicit vegetable purchase | Route A vegetable factor |
| `food.fresh_fruit` | Explicit fruit purchase | Route A fresh fruit factor |
| `food.basic_grocery` | Grocery/supermarket where a mixed food basket is plausible | Route A basic grocery factor; medium confidence; do not use for restaurant/food delivery or a general retailer whose basket is unknown |
| `food.restaurant_delivery` | Restaurants, cafes, food delivery apps | Unsupported until a defensible India-specific factor is sourced; do not substitute basic-grocery factor |
| `shopping.clothing` | Clothing stores, apparel purchases | Unsupported by current active India factors |
| `shopping.footwear` | Shoe/footwear stores | Unsupported by current active India factors |
| `shopping.general_ecommerce` | General marketplace / e-commerce merchant | Unsupported unless product/category is known; do not infer product type from marketplace name |
| `shopping.electronics` | Electronics purchases | Unsupported by current active India factors |
| `transport.public_transit` | Bus/metro/train pass or ticket | Unsupported unless a suitable India-specific factor and defensible activity unit are added |
| `transport.taxi_rideshare` | Taxi/ride-hailing | Unsupported unless distance/mode or a defensible India-specific spend factor is added |
| `transport.air_travel` | Airline transaction | Unsupported unless route/distance/class and suitable factor are available |
| `transport.vehicle_purchase` | Car/bike purchase | Unsupported; do not estimate from purchase amount alone without an appropriate lifecycle/production factor |
| `entertainment` | Cinema, streaming, events, gaming | Unsupported by current active India factors |
| `healthcare` | Hospital, pharmacy, doctor | Unsupported by current active India factors |
| `telecom_internet` | Mobile, broadband, internet bills | Unsupported by current active India factors |
| `personal_care` | Salon, cosmetics, personal-care goods | Unsupported by current active India factors |
| `education` | Tuition, books, courses | Unsupported by current active India factors |
| `housing_rent` | Rent, maintenance, society charges | Unsupported by current active India factors; electricity is handled separately if identified |
| `insurance_finance` | Insurance premiums, bank charges, investments | Unsupported; transfers/investments are not consumer-goods emissions |
| `cash_withdrawal_transfer` | ATM withdrawal, UPI transfer, internal transfer, credit-card payment | Exclude from consumption emissions to avoid double counting; label `excluded_non_consumption` |
| `refund_credit` | Refunds, reimbursements, salary/income, credits | Exclude from emissions total by default; preserve row and status |
| `other_unclassified` | Unknown or ambiguous transaction | No factor; unsupported/needs review |

This list is intentionally conservative. Add categories only when an India-specific factor and defensible mapping are documented. A merchant classifier may predict a broad category, but the emissions engine must independently check whether a compatible factor exists.

### Unsupported category policy — non-negotiable
For unsupported categories:
- `factor_id = NULL`
- `estimated_co2e_kg = NULL`
- `emissions_status = 'unsupported'` or `needs_review`
- Store a reason such as `NO_INDIA_FACTOR`, `AMBIGUOUS_PRODUCT`, `NON_CONSUMPTION`, or `NON_INR_CURRENCY`.
- Display them in an “Unsupported / needs review” table with date, cleaned merchant/description, spend, predicted category, reason, and a way to correct category if a review workflow exists.
- Do not use zero emissions as a placeholder.
- Do not silently fall back to UK DEFRA, US EPA, or an unrelated category factor.
- Do not include unsupported spend in estimated emissions totals.
- Report both **emissions estimated for supported transactions** and **spend coverage percentage** so the total cannot be mistaken for the user's complete footprint.
- Optionally display an estimated-coverage disclaimer: “This is a partial estimate based only on transactions with supported factors.”
- If a low-confidence factor is used, explicitly label it low confidence and include it in coverage only if the factor is valid for that category. Prefer leaving unsupported rather than applying a misleading factor.

### Coverage metrics
Compute:
- `total_expense_spend_inr`: sum of eligible positive INR expenses in the selected batch/time period.
- `supported_spend_inr`: sum of spend for eligible transactions with a valid emissions estimate.
- `supported_spend_pct = supported_spend_inr / total_expense_spend_inr * 100` when denominator > 0, else `NULL`.
- `estimated_co2e_kg`: sum only non-null emissions for eligible estimated transactions.
- `estimated_transaction_count`, `unsupported_transaction_count`, `excluded_transaction_count`.
- Never divide by zero. Never label the emissions total “total footprint” without stating the supported coverage.

## 7. Merchant cleaning (Milestone 1.4)

Implement deterministic, conservative normalization in `pipeline/cleaning.py`:
- Preserve `raw_description`.
- Create `cleaned_description` and a normalized `merchant_key`.
- Unicode normalization, lowercase/casefold, trim whitespace, collapse repeated spaces.
- Remove obvious transaction reference noise only when confidently identifiable (e.g. long reference numbers, masked account fragments); avoid deleting meaningful merchant tokens.
- Normalize separators and common payment prefixes/suffixes.
- Maintain a configurable alias/stopword list.
- Do not over-normalize. For example, distinct businesses with similar names must not collapse into one merchant.
- Make cleaning idempotent: applying it twice yields the same result.
- Include unit tests for messy strings, UPI-style descriptions with identifiers removed from logs, punctuation, numbers, and near-identical merchant names.

## 8. Categorization pipeline orchestration (Milestone 2.5)

Pipeline order must be exactly:
1. Tier 0 — merchant cache
2. Tier 1 — TF-IDF + Logistic Regression classifier (when trained/available and confidence is sufficient)
3. Tier 2 — exact dictionary/alias matching
4. Tier 3 — RapidFuzz fuzzy matching
5. Tier 4 — sentence embedding semantic similarity (optional fallback)
6. Tier 5 — LLM fallback (optional final fallback)
7. Unclassified / needs review

If the repository's existing roadmap expects dictionary/fuzzy before the ML model, keep the interfaces modular and document the actual order. However, for this spec use the order above so the cache and trained classifier can short-circuit repeated/known cases; never let a lower-confidence model overwrite a confident exact dictionary match. A deterministic exact alias match may be promoted before the classifier if the existing implementation already follows that convention, provided the order is documented and tests prove correct precedence. **No result from any tier may overwrite a higher-priority confident result.**

Every result must contain:
- `category`
- `subcategory` (nullable)
- `merchant_name` / `merchant_key`
- `tier`
- `method`
- `confidence` in [0,1]
- `status` (`categorized`, `needs_review`, `unclassified`)
- `reason` / matched alias/model label as appropriate

### Tier 0 — Cache
- Query by normalized `merchant_key`.
- Only use cache entries marked approved/auto and with valid category.
- Update `last_used` safely.
- Cache hit should skip later tiers.
- Never trust a cache entry with invalid category, expired/inactive factor mapping, or unresolved review state.

### Tier 1 — TF-IDF + Logistic Regression
- Training notebook: `notebooks/model_training.ipynb`.
- Train using reviewed/labeled merchant examples, not synthetic guesses presented as ground truth.
- Use train/test split with stratification where possible; handle rare categories carefully.
- Save vectorizer and model as versioned artifacts under `models/`.
- Load artifacts lazily and handle missing artifacts gracefully.
- Return predicted category and model probability/confidence.
- Set a configurable acceptance threshold; default `0.80` unless project data indicates a validated alternative.
- Report precision, recall, macro-F1 and confusion matrix. Do not claim accuracy if the model was not evaluated.
- If confidence is below threshold, continue to the next tier instead of forcing a category.
- A classifier prediction alone does not guarantee an emissions factor exists.

### Tier 2 — Dictionary / exact alias
- Use explicit, version-controlled aliases and canonical categories.
- Normalize aliases with the same cleaning function.
- Exact normalized match only.
- High confidence (typically 0.99 or 1.0) when the alias is unambiguous.
- Ambiguous aliases should be marked `needs_review`, not randomly assigned.
- Keep category aliases separate from carbon factor registry.

### Tier 3 — RapidFuzz
- Default threshold `90` on a 0–100 similarity scale.
- Require at least a 5-point gap between best and second-best candidate. If the gap is smaller, mark ambiguous and continue/fall through.
- Threshold and ambiguity gap are configurable.
- Use `rapidfuzz`, not the removed/deprecated `fuzzywuzzy` package.
- Test exact, near-match, and unrelated strings.

### Tier 4 — Sentence embeddings
- Optional semantic fallback; load the embedding model only when enabled and needed.
- Compare merchant description to carefully curated merchant/category examples.
- Similarity thresholds must be configurable and calibrated on labeled validation examples; do not invent a claim that one universal threshold is reliable.
- If the best and second-best matches are too close, return `needs_review`.
- If dependency/model download fails, continue safely to Tier 5 or unclassified.

### Tier 5 — LLM fallback
- Disabled by default unless a valid API key and explicit configuration are present.
- Send only the minimum normalized merchant text needed; remove transaction reference strings and all sensitive data.
- Ask for a single category from a fixed enum, a short reason, and confidence. Validate output against schema/enum.
- Treat LLM confidence as uncalibrated. Never use it as proof of truth.
- Apply rate limits, timeout, bounded retries, and graceful fallback.
- Do not make an external call for every transaction; batch/caching can be used when safe.
- Never send amounts, dates, account/card numbers, UPI IDs, user identifiers, or the full uploaded file unless strictly required (it is not required for merchant category).
- An LLM result should be `needs_review` or low confidence unless independently validated by an approved rule.
- If unavailable, erroring, or disabled, return unclassified rather than crashing the batch.

### Orchestration and errors
- One failing tier must not abort the entire upload.
- Record the tier/method and failure reason safely.
- Do not log secrets or complete raw rows.
- Use deterministic outputs for deterministic tiers.
- Run category assignment and emissions calculation as separate stages.

## 9. Emissions calculation engine

Create a separate pure function/service, e.g. `pipeline/emissions.py`:
Input: transaction amount/currency, category/subcategory, optional actual quantity, optional price-per-unit and its source/date, and factor registry.
Output: `factor_id`, `factor_method`, `activity_quantity`, `activity_unit`, `estimated_co2e_kg`, `emissions_status`, `emissions_confidence`, `factor_source`, `factor_year`, `estimation_notes`.

Logic:
1. Exclude income, refunds, internal transfers, cash withdrawals, card bill payments, and other non-consumption transactions from emissions total; store explicit exclusion status.
2. Check currency; only apply INR factors to INR spend.
3. Check if user supplied valid activity quantity. If yes, select matching physical factor and compute Route B.
4. If no quantity, select a valid active India-specific spend factor for the exact category and compute Route A.
5. If no eligible factor, return unsupported with NULL emissions.
6. Never use a factor for a broad category if transaction text indicates a different or ambiguous product.
7. Keep factor provenance in each transaction record.
8. Round only for display; preserve full precision in storage/calculation.
9. Handle negative amounts/refunds by the explicit policy, not by accidental negative emissions.
10. Add unit tests proving no double application of factors.

For Route B, if quantity is inferred from spend:
- `quantity = spend / effective_price_per_unit`
- Price must include an identified source, region/coverage, date, unit, and confidence.
- If no reliable price is available, do not infer quantity; use Route A if available.
- UI must say “quantity estimated from spend” when relevant.

## 10. Frontend requirements — Streamlit

Build a clean, professional, responsive-feeling light UI. Prefer a soft warm light theme (cream/off-white background, green/navy accents), readable cards, consistent spacing, and clear empty/error/loading states. Avoid a dark theme.

### Pages/sections
1. **Dashboard / Overview**
   - Current batch selector or recent batch summary.
   - Estimated CO₂e (kg) for supported transactions only.
   - Supported spend coverage (%).
   - Supported/unsupported/excluded transaction counts.
   - Category emissions chart (estimated categories only).
   - Monthly trend when date range supports it.
   - Visible partial-estimate disclaimer and methodology link.
2. **Upload Transactions**
   - CSV uploader, file constraints, required/optional columns.
   - Validation messages, counts, and preview.
   - Confirm/process button; avoid processing automatically on every rerun.
   - Progress/status per stage: validate → clean → categorize → estimate → save.
   - Friendly errors without stack traces/secrets.
3. **Transactions**
   - Search/filter by date, category, status, tier, confidence, and emissions status.
   - Show spend, category, estimation method, emissions or “Not estimated,” factor source, and reason.
   - Unsupported emissions must display “Not estimated — no supported factor,” never `0 kg`.
4. **Review / Unsupported**
   - List ambiguous, low-confidence, and unsupported records.
   - Explain why not estimated.
   - If manual correction is implemented, require user confirmation and log corrections; do not silently mutate shared cache.
5. **Methodology & Sources**
   - Explain Route A and Route B with formulas.
   - Show factor source, reference year, unit, confidence, and category applicability.
   - Clearly identify factors as India-based and any estimates as partial.
6. **History** (if time permits in these milestones)
   - Batch-level historical summaries from `insights_history`.

### UI behavior
- Use Streamlit session state carefully; don't reinsert/reprocess on every rerun.
- Use a unique `batch_id` per upload.
- Use progress indicators and helpful empty states.
- Make unsupported spend and estimated emissions visually distinct.
- Do not make a chart that implies unsupported transactions have zero emissions.
- Downloadable processed CSV may be provided, but do not include sensitive data or credentials.
- All charts must handle empty/all-null data without errors.
- Add date/category filters and keep totals consistent with filtered data.

## 11. Milestone-by-milestone implementation and acceptance criteria

### Release 1 — Foundations: Data & Dashboard Skeleton

#### Milestone 1.1 — Project Setup
Build:
- Verify Git repository/folder structure and `.gitignore`.
- Create/use virtual environment instructions.
- Ensure `requirements.txt` is complete.
- Configure `.env.example` and `database/connection.py` (or existing equivalent).
- Add connection health check.
- Add a minimal working `dashboard/app.py`.

Acceptance:
- `streamlit run dashboard/app.py` starts.
- A test query such as `SELECT 1` succeeds when `DATABASE_URL` is configured.
- If the DB is not configured/unavailable, the app gives a friendly message and upload validation can still be explored without crashing.
- `.env` and model secrets are not committed.
- README explains setup/run/test commands.

#### Milestone 1.2 — Database Schema
Build:
- SQL schema/migrations for `transactions`, `merchant_cache`, `insights_history`, and factor registry if stored in DB.
- SQLAlchemy models aligned with schema.
- Indexes, unique/idempotency constraints, foreign keys as appropriate.
- NUMERIC types for money/factors.
- Safe `create_all`/migration strategy; avoid destructive schema drops.

Acceptance:
- Tables are created and queryable in the configured PostgreSQL database.
- Re-running setup does not duplicate or destroy data.
- Tests verify important constraints and nullable emissions behavior.
- `factor_id` is nullable for unsupported transactions.

#### Milestone 1.3 — CSV Upload + Validation
Build:
- `dashboard/pages/1_Upload.py`.
- `utils/validation.py`.
- Header normalization, allowlist, sensitive-column rejection, data type/row validation, preview, structured errors.

Acceptance:
- Valid sample CSV previews and proceeds.
- Invalid sample CSV shows clear row/column errors.
- Empty/malformed CSV and missing required columns are handled.
- Sensitive columns are rejected without exposing values.
- Unsupported currency is not silently estimated using INR factors.

#### Milestone 1.4 — Data Cleaning
Build:
- `pipeline/cleaning.py`.
- Cleaning tests.
- Add `cleaned_description` and `merchant_key`.

Acceptance:
- Cleaning is deterministic and idempotent.
- Useful merchant tokens are retained.
- Messy samples normalize consistently.
- Original descriptions remain available for display where appropriate, but sensitive/reference data is not logged.

### Release 2 — Categorization Pipeline

#### Milestone 2.1 — Dictionary + Fuzzy Matching (Tiers 2–3)
Build:
- `pipeline/categorization/tier2_dictionary.py`.
- `pipeline/categorization/tier3_fuzzy.py`.
- Curated alias/category map.

Acceptance:
- Exact aliases match correctly.
- Near matches above threshold match only with adequate ambiguity gap.
- Nonmatches and ambiguous matches fall through / need review.
- Tests cover exact, near-match, ambiguous, and unrelated descriptions.

#### Milestone 2.2 — Merchant Cache (Tier 0)
Build:
- Cache read/write query functions and `tier0_cache.py`.
- Safe update of last-used timestamp.
- Validated cache category/status rules.

Acceptance:
- Repeated merchant lookup hits cache and avoids later tiers.
- Invalid/unapproved cache entries are ignored.
- Idempotent upsert prevents duplicates.
- Cache confidence and source are retained.

#### Milestone 2.3 — TF-IDF + Logistic Regression (Tier 1)
Build:
- Labeled dataset format and notebook.
- Training/evaluation pipeline and saved artifacts.
- Classifier module with threshold and safe missing-model behavior.

Acceptance:
- Model trains/evaluates on real labeled examples.
- Precision/recall/macro-F1 and confusion matrix are produced.
- Missing or low-confidence model falls through safely.
- The model does not force a category when confidence is below threshold.

#### Milestone 2.4 — Embedding Similarity (Tier 4)
Build:
- Optional embedding fallback.
- Curated reference examples and configurable thresholds.

Acceptance:
- Semantically similar descriptions can match even when wording differs.
- Ambiguous/low-similarity cases fall through to Tier 5/unclassified.
- Disabled/missing model does not crash processing.

#### Milestone 2.5 — LLM Fallback + Orchestration (Tier 5)
Build:
- Optional LLM client, strict structured-output validation, timeout/retry/rate limit.
- `pipeline/categorization/tier5_llm.py`.
- `pipeline/categorization/pipeline.py` (or project’s existing orchestration module).
- End-to-end pipeline: validate → clean → categorize → estimate emissions → persist → dashboard.

Acceptance:
- Entire chain runs on a sample CSV.
- Every valid transaction has a categorization outcome (categorized, needs_review, or unclassified).
- Every transaction also has an emissions outcome (estimated, unsupported, excluded, or error).
- Unsupported categories do not crash the run and do not get zero emissions.
- LLM disabled/no key/API failure results in safe unclassified fallback.
- No secrets or sensitive transaction data appear in logs.
- Re-running Streamlit does not duplicate records.
- Tests cover the full pipeline and DB-independent pure functions.

## 12. Canonical category enum

Use these canonical values consistently in code, model training, DB, UI, and factor mapping:

```text
utilities.electricity
utilities.lpg
transport_fuel.petrol
transport_fuel.diesel
transport_fuel.unknown
food.rice
food.wheat_products
food.coarse_grains
food.pulses
food.sugar_sweeteners
food.milk_dairy
food.meat_fish
food.edible_oils
food.vegetables
food.fresh_fruit
food.basic_grocery
food.restaurant_delivery
shopping.clothing
shopping.footwear
shopping.general_ecommerce
shopping.electronics
transport.public_transit
transport.taxi_rideshare
transport.air_travel
transport.vehicle_purchase
entertainment
healthcare
telecom_internet
personal_care
education
housing_rent
insurance_finance
cash_withdrawal_transfer
refund_credit
other_unclassified
```

Important: canonical categories are not a promise that an emissions factor exists. Categorization and emissions support are separate. A valid category can have `factor_id = NULL` and emissions status `unsupported`.

## 13. Suggested dictionary aliases (starter set; review and expand)

Only use aliases that are sufficiently unambiguous. These are examples, not an exhaustive or guaranteed mapping:
- Electricity: `electricity bill`, known electricity distribution company bill names, `power bill`.
- LPG: `lpg refill`, `cooking gas`, known LPG cylinder provider names.
- Petrol/diesel: explicit product text or a verified merchant/receipt signal; generic `fuel station` must map to `transport_fuel.unknown`, not automatically petrol.
- Grocery: `grocery`, `supermarket`, `kirana`, `provision store` → `food.basic_grocery` only if merchant nature strongly supports grocery.
- Rice/wheat/pulses/dairy/vegetables/fruit/oil/sugar: only when transaction description explicitly identifies the item or a dedicated merchant is unambiguous.
- Restaurants/delivery: `restaurant`, `cafe`, food delivery merchants → `food.restaurant_delivery` (currently unsupported).
- Clothing/footwear/e-commerce/entertainment/healthcare/telecom etc. map to their canonical categories but remain unsupported for emissions unless factors are added.
- UPI/payment gateways alone do not identify the purchase category. Do not infer category from `UPI`, `PAYTM`, `PHONEPE`, `RAZORPAY`, `POS`, `ECOM`, or a bank's generic transaction marker.

Do not add a category factor just because a merchant is easy to classify. Factor mapping requires independent evidence.

## 14. Testing plan

Use pytest and keep unit tests independent of a live database where possible.

### Validation tests
- Valid CSV.
- Missing required column.
- Header whitespace/case.
- Sensitive column rejection.
- Empty file.
- Empty description.
- Invalid date.
- Nonnumeric/NaN/infinite amount.
- Non-INR currency.
- Refund/negative amount policy.
- Duplicate headers.

### Cleaning tests
- Whitespace/case/punctuation.
- Payment prefixes and reference-number cleanup.
- Meaningful numbers/tokens retained when needed.
- Idempotence.
- Similar merchants not accidentally merged.

### Categorization tests
- Cache hit short-circuits.
- Approved vs unapproved cache entries.
- Exact dictionary match.
- Fuzzy match above threshold and ambiguity gap.
- Fuzzy ambiguity.
- Model missing/low confidence.
- Embedding disabled/error.
- LLM disabled/error/invalid JSON/invalid category.
- Every output category belongs to canonical enum or is unclassified.
- Tier/method/confidence are always populated consistently.

### Emissions tests
- Spend factor formula.
- Physical factor × known quantity.
- Spend-to-quantity conversion only with valid price.
- No double multiplication.
- Missing factor yields `NULL` emissions + `unsupported`.
- Unsupported restaurant/e-commerce does not get grocery factor.
- Unknown fuel policy behaves as configured.
- Non-INR is not estimated with INR factors.
- Refunds/transfers are excluded.
- Coverage denominator and zero-denominator behavior.
- Rounding occurs only in presentation.

### Database/integration tests
- Schema can initialize safely.
- Insert/read transaction.
- Factor ID foreign key/validation.
- Unique import row prevents duplicates.
- Full sample CSV flows through all stages.
- DB unavailable gives friendly error and does not leak secrets.

## 15. Required demo fixtures

Create small synthetic fixtures with no real bank/account data:
1. `valid_transactions.csv`: electricity bill, LPG refill, explicit petrol purchase, grocery merchant, restaurant, clothing store, generic marketplace, UPI transfer, refund.
2. `invalid_missing_columns.csv`: missing `amount`.
3. `invalid_sensitive_column.csv`: includes a fake `account_number` column; app must reject it.
4. `invalid_rows.csv`: malformed date, nonnumeric amount, blank description.
5. `ambiguous_merchants.csv`: generic fuel station, payment gateway-only descriptions, ambiguous merchant strings.

Expected outcomes:
- Electricity/LPG/petrol can be estimated by a valid Route A factor or Route B with valid quantity/price inputs.
- Generic grocery may use `IN-HCES-BASIC-GROCERY` only when grocery is a plausible basket.
- Restaurant, clothing, generic marketplace, healthcare, telecom, and other unsupported categories remain categorized where possible but emissions are NULL/unsupported.
- UPI transfer is excluded as non-consumption.
- Refund is excluded from emissions by default.
- Dashboard clearly displays the partial-estimate coverage.

## 16. Definition of done for Milestones 1.1–2.5

Do not claim completion unless all are true:
- App starts with the documented command.
- Database connection is configurable and secrets are protected.
- Schema tables and indexes exist.
- CSV validation and cleaning work.
- All five categorization tiers have modular interfaces; optional tiers fail safely.
- The full pipeline runs end-to-end.
- Category mapping is independent from emissions factor mapping.
- India factor registry uses correct units and distinct IDs for spend vs physical factors.
- Unsupported categories are NULL/not estimated, never silently zero and never assigned foreign factors.
- Dashboard reports emissions, coverage, unsupported/excluded counts, and methodology.
- Tests pass and the README includes setup, environment variables, schema initialization, test commands, and known limitations.
- No fake model metrics, fake sources, invented factor values, or undocumented assumptions are shown to users.

## 17. Implementation order for Antigravity

1. Inspect the repository and report the existing structure and working features before editing.
2. Reconcile the actual code with this spec; preserve good existing work.
3. Complete Milestone 1.1 and run app + DB health check.
4. Complete Milestone 1.2 and test schema/idempotency.
5. Complete Milestone 1.3 and test valid/invalid CSVs.
6. Complete Milestone 1.4 and cleaning tests.
7. Complete Milestones 2.1 and 2.2, then test deterministic matching/cache.
8. Complete Milestone 2.3 and report actual model evaluation only if labeled data exists.
9. Complete Milestone 2.4 with a lazy optional dependency.
10. Complete Milestone 2.5 with LLM disabled by default and safe fallback.
11. Implement the emissions engine, factor registry, coverage metrics, and dashboard integration.
12. Run all tests, fix regressions, update README, and provide a concise final report with files changed, commands run, tests passed, and any blockers.

**Do not stop after generating a plan or mock UI. Implement the code in the existing repository, run tests, and report honestly what is complete versus blocked.**

---

# ADDENDUM A — PDF, EXCEL, AND CSV UPLOAD SUPPORT

Implement this as an addition to the existing specification. Preserve all previous features and requirements. Inspect the repository first and integrate with the existing upload/validation pipeline; do not create duplicate competing implementations.

## A1. Objective
The transaction upload page must support `.csv`, `.xlsx`, `.xls`, and `.pdf`. Each format requires its own safe extraction path, then all formats must produce the same canonical transaction schema: `date`, `description`, `amount`, with optional `currency` and `payment_method` only if the project retains these fields.

## A2. Frontend upload experience
- Allow CSV, Excel, or PDF on the same upload page.
- Show accepted extensions, file-size limit, privacy notice, and unsupported-file states.
- After extraction, show a normalized transaction preview, validation errors/warnings, valid/invalid row counts, and rows eligible for emissions processing.
- Do not persist or process the data until the user confirms.
- Give clear errors for encrypted/password-protected files, malformed files, scanned PDFs requiring OCR, and files with no extractable transactions.
- Do not expose stack traces or secrets in the UI.
- Prevent duplicate processing/inserts on Streamlit reruns with a stable batch ID and idempotency keys.

## A3. CSV handling
Keep all existing CSV validation: normalized headers, required columns, sensitive-column rejection, row-level errors, empty/malformed file handling, invalid date/amount/description handling, and currency checks. Do not expose sensitive values in errors. Preserve negative/refund rows but exclude them from emissions under the existing policy.

## A4. Excel handling (`.xlsx`, `.xls`)
- Use `openpyxl` for `.xlsx`; use an appropriate reader such as `xlrd` for `.xls` if `.xls` support is implemented. Do not support `.xlsm` unless separately designed and secured.
- Show worksheet names and let the user select the transaction worksheet. Auto-select only if there is exactly one plausible worksheet; otherwise require selection.
- Preview the selected worksheet before processing.
- Map common header aliases:
  - date: `date`, `transaction date`, `txn date`, `posted date`
  - description: `description`, `transaction details`, `narration`, `merchant`, `particulars`, `details`
  - amount: `amount`, `transaction amount`, `txn amount`
  - currency: `currency`, `ccy`
  - payment method: `payment method`, `mode`, `channel`
- If `debit` and `credit` columns exist, derive an expense-positive signed amount only under a documented and tested convention: debit/expense positive; credit/refund/income negative. Show the convention in the preview. If the source semantics are ambiguous, require review rather than guessing.
- Handle native Excel date cells and text dates.
- If the header row cannot be identified confidently, ask the user to select the header row or return a clear unsupported-layout error.
- Never execute macros or spreadsheet formulas. If formula cells lack cached values, warn and ask the user to export values or correct the workbook.
- Reject sensitive identifier columns using the same policy as CSV.
- Limit file size, row count, and worksheet dimensions.

## A5. PDF handling
- Use `pdfplumber` or another maintained local text/table extraction library.
- First detect whether the PDF has extractable text. Support only statement layouts that can be parsed confidently.
- Use a modular parser/adapter interface, such as `parse_pdf_statement(file_bytes) -> ExtractionResult`, returning normalized rows, parser/version, warnings, and errors.
- Add bank/layout-specific parsers only when representative synthetic fixtures and tests exist.
- For unknown layouts, show “PDF layout not yet supported” and recommend CSV/Excel export; never guess transaction amounts.
- Detect scanned/image-only PDFs. If OCR is not implemented, clearly say OCR is unsupported; do not return an empty successful import. If OCR is added later, make it opt-in and flag extracted values for review.
- Handle encrypted/password-protected and malformed PDFs safely. Do not attempt password cracking.
- Run extracted rows through the same shared validation as CSV/Excel.
- Handle wrapped descriptions, page headers/footers, repeated headers, and continuation rows only where verified by tests.

## A6. Common extraction architecture
Adapt to the existing repository rather than duplicating modules. Suggested modules:
- `utils/file_readers/base.py`
- `utils/file_readers/csv_reader.py`
- `utils/file_readers/excel_reader.py`
- `utils/file_readers/pdf_reader.py`
- Existing `utils/validation.py` as shared canonical validation

Each reader should return a structured result containing:
- normalized `dataframe`
- `source_file_type`
- `source_parser` and parser version
- selected worksheet when relevant
- warnings and errors
- `requires_user_review`
- number of rows extracted

All formats must pass through the same validation → cleaning → categorization → emissions → persistence pipeline. File parsing must not directly assign categories or emission factors.

## A7. Security and privacy
- Default maximum upload size: 10 MB, configurable; use a lower existing project limit if one exists.
- Configure maximum rows and worksheet dimensions.
- Validate extension and file signature/content; do not trust extension alone.
- Reject unsupported or malformed formats.
- Do not log or permanently store original statement files by default.
- Use in-memory processing where practical; safely clean temporary files if needed.
- Never log account/card identifiers, UPI IDs, credentials, full statement contents, or secrets.
- Never send full files/statements to an LLM; the categorization LLM may receive only sanitized merchant text as specified in the main specification.
- Do not silently add cloud document processing or OCR.

## A8. Tests and acceptance criteria
Test:
- Valid CSV, `.xlsx`, and `.xls` (if `.xls` is supported).
- Multiple sheets and explicit sheet selection.
- Header aliases, native/text dates, debit-credit conversion/sign convention.
- Missing columns, sensitive columns, empty/malformed files.
- Supported text-based PDF layout, unknown layout, scanned PDF, encrypted/password-protected PDF.
- Oversized files, excessive row/sheet dimensions, formula cells without cached values.
- No duplicate inserts on reruns.
- Ambiguous rows flagged for review.
- All formats yield the same canonical schema and emissions behavior.

## A9. Documentation and honest support boundaries
Update README and upload-page help text with supported extensions, size/row limits, Excel sheet selection, actually supported PDF layouts, OCR limitation, debit/credit sign convention, privacy/retention behavior, and CSV/Excel fallback guidance. Do not claim support for every bank's PDF layout.

## A10. Definition of done
- CSV, Excel, and supported text-based PDFs show preview and validation before confirmation.
- All accepted formats normalize to the same schema.
- Unsupported or unreadable files fail clearly and safely; they must not be treated as valid empty uploads.
- Tests pass and README documents actual support.
- Preserve all existing India-specific factor, hybrid Route A/Route B, unsupported-category, and no-double-counting rules.

---

# ADDENDUM B — ACCOUNT NUMBER SAFETY ASSURANCE

## B1. User-facing statement

Use the following statement in the upload page's privacy/security section and project documentation **only after the implementation and tests below are in place**:

> “We enforce this at the schema level, not just in application logic. We use Pydantic with `extra='forbid'`, so our data model only has fields for date, description, and amount — account number, IFSC code, balance are never even parsed into an object that could later leak. If any extra field is present in the uploaded file, the system rejects it rather than silently ignoring it. Combined with the fact that we never persist the raw uploaded file — only the reduced, 3-field dataset goes into PostgreSQL — the account number physically never exists anywhere in our system beyond the initial file buffer in memory.”

## B2. Required implementation — do not make unsupported security claims

The quoted statement is a target assurance, not permission to make an unverified claim. Implement and test all requirements below before displaying it unconditionally.

1. **Strict Pydantic model**
   - Define a Pydantic input model with `extra='forbid'`.
   - Validate every normalized row before it enters the processing/persistence pipeline.
   - Core transaction fields are `date`, `description`, and `amount`. If the existing project retains optional `currency` or `payment_method`, explicitly document that the schema is not literally limited to three fields, and use a strict allowlist.
   - Unknown fields must cause a clear validation failure; never silently drop unknown columns.
   - Keep extraction metadata (file type, selected worksheet, row number, parser warnings) separate from the transaction payload.

2. **Reject sensitive fields before constructing transaction objects**
   - Inspect normalized column headers before mapping rows into Pydantic models.
   - Reject columns indicating account number, IFSC, card number, CVV, expiry, account holder/customer ID, UPI ID, balance, available balance, opening/closing balance, credentials, PIN, OTP, or similar sensitive information.
   - Never include sensitive cell values in logs, exceptions, validation messages, telemetry, or UI output.
   - Do not silently ignore extra columns. Explain that the user must remove the unaccepted column, without echoing its cell values.

3. **Raw-file handling**
   - Process uploads in memory where practical.
   - Do not save original uploaded files to PostgreSQL, local disk, object storage, logs, analytics, or backups.
   - Do not send original files, full statement text, account identifiers, balances, or complete transaction rows to an LLM or external service.
   - If temporary disk storage is unavoidable for a parser, use a secure temporary file, restrict access, and delete it reliably in a `finally` block. Document this exception; do not claim the file only exists in memory if it does not.
   - Clear references to uploaded bytes/dataframes where practical after processing. Do not promise forensic memory erasure; Python cannot guarantee that.
   - Avoid retaining uploaded originals in Streamlit session state longer than required.

4. **Persisted-data minimization**
   - Reconcile this assurance with the main database schema. The main specification includes processing metadata such as `batch_id`, cleaned description, category, factor ID, confidence, and emissions.
   - Therefore, do not falsely claim PostgreSQL stores only three columns if the implemented schema stores additional fields.
   - The defensible claim is that sensitive account identifiers and original uploaded files are not persisted, while only an allowlisted, minimized transaction representation and necessary processing metadata are stored.
   - If the product requirement is literally to persist only `date`, `description`, and `amount`, implement that design consistently and ensure all other persisted metadata is handled separately and reviewed. Do not leave contradictory schema behavior.

5. **Apply equally to CSV, Excel, and PDF**
   - CSV: inspect headers before row-object creation.
   - Excel: inspect the selected worksheet's headers before row-object creation.
   - PDF: do not map account numbers or balance fields into transaction payloads. If the parser cannot confidently isolate transaction rows from account/balance sections, reject the file or require review.
   - If a source cannot be parsed safely, fail closed and recommend exporting only the required transaction fields.

6. **Security tests**
   - Pydantic rejects unexpected fields due to `extra='forbid'`.
   - Files containing account-number, IFSC, balance, card-number, UPI-ID, and credential columns are rejected before transaction objects are created.
   - Sensitive values do not appear in captured logs, exceptions, or user-facing errors.
   - Original file bytes are not written to disk or database in the normal upload flow.
   - All supported formats use the same sensitive-field checks and strict validation.
   - LLM requests contain only sanitized merchant text, never account identifiers or full rows.
   - Documentation states exactly what is and is not persisted.

## B3. Truthfulness requirement
Do not display the quoted assurance until implementation and tests support it. If a technical limitation exists, display a narrower, accurate statement instead. In particular, do not claim that an account number “physically never exists anywhere” beyond an in-memory buffer unless temporary files, logs, telemetry, exception traces, session state, and all persistence paths have been checked and tested. Prefer a precise statement about what the application does and does not store.
