"""
database/migrate.py
Safe, idempotent schema migration.
Adds missing columns to existing Supabase tables without dropping any data.
Run once: python -m database.migrate
"""
from __future__ import annotations

import logging
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from database.connection import get_engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Each entry: (table, column, SQL type, optional DEFAULT clause)
# Uses IF NOT EXISTS so reruns are safe.
# ---------------------------------------------------------------------------
MIGRATIONS = [
    # ---- transactions ----
    ("transactions", "batch_id",                    "TEXT",             "DEFAULT ''"),
    ("transactions", "source_row_number",           "INTEGER",          "DEFAULT 0"),
    ("transactions", "raw_description",             "TEXT",             "DEFAULT ''"),
    ("transactions", "cleaned_description",         "TEXT",             "DEFAULT ''"),
    ("transactions", "merchant_key",                "TEXT",             None),
    ("transactions", "merchant_name",               "TEXT",             None),
    ("transactions", "subcategory",                 "TEXT",             None),
    ("transactions", "category_status",             "TEXT",             None),
    ("transactions", "categorization_tier",         "INTEGER",          None),
    ("transactions", "categorization_method",       "TEXT",             None),
    ("transactions", "categorization_confidence",   "DOUBLE PRECISION", None),
    ("transactions", "factor_id",                   "TEXT",             None),
    ("transactions", "factor_method",               "TEXT",             None),
    ("transactions", "activity_quantity",           "DOUBLE PRECISION", None),
    ("transactions", "activity_unit",               "TEXT",             None),
    ("transactions", "estimated_co2e_kg",           "DOUBLE PRECISION", None),
    ("transactions", "emissions_status",            "TEXT",             None),
    ("transactions", "emissions_confidence",        "DOUBLE PRECISION", None),
    ("transactions", "factor_source",               "TEXT",             None),
    ("transactions", "factor_year",                 "INTEGER",          None),
    ("transactions", "estimation_notes",            "TEXT",             None),
    ("transactions", "updated_at",                  "TIMESTAMPTZ", "DEFAULT NOW()"),

    # ---- insights_history ----
    ("insights_history", "batch_id",                       "TEXT",             "DEFAULT ''"),
    ("insights_history", "total_spend_inr",                "DOUBLE PRECISION", "DEFAULT 0"),
    ("insights_history", "estimated_co2e_kg",              "DOUBLE PRECISION", "DEFAULT 0"),
    ("insights_history", "supported_spend_inr",            "DOUBLE PRECISION", "DEFAULT 0"),
    ("insights_history", "supported_spend_pct",            "DOUBLE PRECISION", "DEFAULT 0"),
    ("insights_history", "transaction_count",              "INTEGER",          "DEFAULT 0"),
    ("insights_history", "estimated_transaction_count",    "INTEGER",          "DEFAULT 0"),
    ("insights_history", "unsupported_transaction_count",  "INTEGER",          "DEFAULT 0"),
    ("insights_history", "methodology_version",            "TEXT",             "DEFAULT '1.0'"),
    ("insights_history", "created_at",                     "TIMESTAMPTZ",      "DEFAULT NOW()"),

    # ---- merchant_cache ----
    ("merchant_cache", "review_status", "TEXT",    "DEFAULT 'auto'"),
    ("merchant_cache", "subcategory",   "TEXT",    None),
    ("merchant_cache", "tier",          "INTEGER", None),
    ("merchant_cache", "updated_at",   "TIMESTAMPTZ", "DEFAULT NOW()"),
]


def run_migrations() -> None:
    engine = get_engine()
    if engine is None:
        logger.error("No DATABASE_URL configured.")
        return

    with engine.connect() as conn:
        for table, column, col_type, default in MIGRATIONS:
            default_clause = f" {default}" if default else ""
            sql = (
                f"ALTER TABLE {table} "
                f"ADD COLUMN IF NOT EXISTS {column} {col_type}{default_clause};"
            )
            try:
                conn.execute(text(sql))
                logger.info("  ✓ %s.%s", table, column)
            except Exception as exc:
                logger.warning("  ✗ %s.%s — %s", table, column, str(exc)[:100])

        conn.commit()
        logger.info("Migration complete.")


if __name__ == "__main__":
    run_migrations()
