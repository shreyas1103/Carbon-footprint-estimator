"""
database/models.py
SQLAlchemy ORM models aligned with the PostgreSQL schema.
Uses NUMERIC for all money/factor fields (no binary float for stored values).
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

from database.base import Base


def _gen_uuid():
    return str(uuid.uuid4())


class Transaction(Base):
    """
    Stores one bank transaction row, its cleaning/categorization results,
    and its emissions estimate (or null if unsupported).
    """
    __tablename__ = "transactions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    batch_id = Column(String(36), nullable=False, index=True)
    source_row_number = Column(Integer, nullable=False)

    transaction_date = Column(Date, nullable=False)
    description = Column(Text, nullable=False)
    raw_description = Column(Text, nullable=True)
    cleaned_description = Column(Text, nullable=True)
    amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    payment_method = Column(Text, nullable=True)

    merchant_key = Column(Text, nullable=True, index=True)
    merchant_name = Column(Text, nullable=True)

    category = Column(Text, nullable=True, index=True)
    subcategory = Column(Text, nullable=True)
    category_status = Column(Text, nullable=True)  # categorized|needs_review|unclassified
    categorization_tier = Column(Integer, nullable=True)
    categorization_method = Column(Text, nullable=True)
    categorization_confidence = Column(Float, nullable=True)

    factor_id = Column(Text, nullable=True, index=True)
    factor_method = Column(Text, nullable=True)   # spend_based|activity_based
    activity_quantity = Column(Float, nullable=True)
    activity_unit = Column(Text, nullable=True)
    estimated_co2e_kg = Column(Float, nullable=True)
    emissions_status = Column(Text, nullable=True)  # estimated|unsupported|excluded_refund|needs_review|error
    emissions_confidence = Column(Text, nullable=True)  # high|medium|low
    factor_source = Column(Text, nullable=True)
    factor_year = Column(Integer, nullable=True)
    estimation_notes = Column(Text, nullable=True)

    created_at = Column(
    DateTime(timezone=False),
    nullable=False,
    default=datetime.utcnow
    )

    updated_at = Column(
    DateTime(timezone=True),
    server_default=func.now(),
    onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("batch_id", "source_row_number", name="uq_batch_row"),
        CheckConstraint(
            "categorization_confidence IS NULL OR (categorization_confidence >= 0 AND categorization_confidence <= 1)",
            name="chk_confidence_range",
        ),
        Index("ix_transactions_date", "transaction_date"),
    )


class MerchantCache(Base):
    """
    Stores previously resolved merchant → category mappings.
    Only approved/auto entries with valid categories should be trusted.
    """
    __tablename__ = "merchant_cache"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    raw_merchant = Column(Text, nullable=False)
    merchant_key = Column(Text, nullable=True, index=True)
    clean_merchant = Column(Text, nullable=False, unique=True)
    category = Column(Text, nullable=False)
    subcategory = Column(Text, nullable=True)
    confidence = Column(Numeric(5, 4), nullable=False)
    source = Column(Text, nullable=True)
    tier = Column(SmallInteger, nullable=True)
    review_status = Column(Text, nullable=False, default="auto")  # approved|auto|needs_review
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="chk_cache_confidence",
        ),
    )


class InsightsHistory(Base):
    """
    Batch-level aggregated emission summaries.
    """
    __tablename__ = "insights_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Required by the existing Supabase schema
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)

    # Batch information
    batch_id = Column(Text, nullable=True, default="")

    # Emission summary
    total_emission = Column(Numeric, nullable=True)
    total_spend_inr = Column(Float, nullable=True, default=0)
    estimated_co2e_kg = Column(Float, nullable=True, default=0)
    supported_spend_inr = Column(Float, nullable=True, default=0)
    supported_spend_pct = Column(Float, nullable=True, default=0)

    # Transaction counts
    transaction_count = Column(Integer, nullable=True, default=0)
    estimated_transaction_count = Column(Integer, nullable=True, default=0)
    unsupported_transaction_count = Column(Integer, nullable=True, default=0)

    # Text summaries
    summary = Column(Text, nullable=True)
    recommendations = Column(Text, nullable=True)
    methodology_version = Column(Text, nullable=True, default="1.0")

    # Timestamps
    generated_at = Column(DateTime(timezone=False), nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Optional structured summary
    summary_json = Column(JSON, nullable=True)


class CarbonFactor(Base):
    """
    Registry of India-specific carbon emission factors.
    Physical factors and spend-based factors are separate records with distinct IDs.
    """
    __tablename__ = "carbon_factors"

    factor_id = Column(Text, primary_key=True)
    category = Column(Text, nullable=False, index=True)
    subcategory = Column(Text, nullable=True)
    factor_type = Column(Text, nullable=False)  # spend_based|activity_based
    value = Column(Numeric(20, 10), nullable=False)
    unit = Column(Text, nullable=False)
    country = Column(Text, nullable=False, default="India")
    base_year = Column(Integer, nullable=True)
    source_name = Column(Text, nullable=True)
    source_reference = Column(Text, nullable=True)
    source_version = Column(Text, nullable=True)
    confidence = Column(Text, nullable=True)   # high|medium|low
    valid_from = Column(Date, nullable=True)
    valid_to = Column(Date, nullable=True)
    methodology_notes = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
