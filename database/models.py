from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


class MerchantCache(Base):
    __tablename__ = "merchant_cache"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    raw_merchant: Mapped[str] = mapped_column(Text, nullable=False)

    clean_merchant: Mapped[str] = mapped_column(Text, nullable=False)

    category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    confidence: Mapped[float | None] = mapped_column(
        Numeric(5, 4),
        nullable=True
    )

    source: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow
    )

    last_used: Mapped[datetime | None] = mapped_column(
        nullable=True
    )

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="merchant_record"
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    transaction_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    raw_merchant: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    merchant: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    merchant_id: Mapped[int | None] = mapped_column(
        ForeignKey("merchant_cache.id"),
        nullable=True
    )

    amount: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="INR",
        nullable=False
    )

    payment_method: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True
    )

    category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    upload_batch: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow
    )

    merchant_record: Mapped["MerchantCache | None"] = relationship(
        back_populates="transactions"
    )


class InsightsHistory(Base):
    __tablename__ = "insights_history"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    month: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    year: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    total_emission: Mapped[float | None] = mapped_column(
        Numeric(12, 2),
        nullable=True
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    recommendations: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    generated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow
    )