import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from finance_agent.db.base import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    display_name: Mapped[str] = mapped_column(Text)
    bank_name: Mapped[str] = mapped_column(Text)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class Statement(Base):
    __tablename__ = "statements"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "drive_file_id", name="uq_statements_account_drive_file"
        ),
        CheckConstraint(
            "status IN ('pending', 'verified', 'failed', 'processed')",
            name="ck_statements_status",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id")
    )
    drive_file_id: Mapped[str] = mapped_column(Text)
    file_name: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(Text)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    opening_balance: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    closing_balance: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    status: Mapped[str] = mapped_column(Text)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="ck_categories_score_range"),
        CheckConstraint(
            "type IN ('income', 'expense', 'transfer')", name="ck_categories_type"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text)
    score: Mapped[int]
    type: Mapped[str] = mapped_column(Text)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(
            "category_source IN ('rule', 'llm', 'manual')",
            name="ck_transactions_category_source",
        ),
        CheckConstraint(
            "review_status IN ('auto', 'needs_review', 'confirmed')",
            name="ck_transactions_review_status",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    statement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("statements.id")
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True
    )
    txn_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    description: Mapped[str] = mapped_column(Text)
    counterparty: Mapped[str | None] = mapped_column(Text, nullable=True)
    running_balance: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    category_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    review_status: Mapped[str] = mapped_column(Text, default="auto")


class FixedCost(Base):
    __tablename__ = "fixed_costs"
    __table_args__ = (
        CheckConstraint(
            "frequency IN ('monthly', 'quarterly', 'yearly')",
            name="ck_fixed_costs_frequency",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id")
    )
    name: Mapped[str] = mapped_column(Text)
    expected_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    frequency: Mapped[str] = mapped_column(Text)


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint(
            "report_type IN ('weekly', 'monthly')", name="ck_reports_report_type"
        ),
        CheckConstraint(
            "delivery_status IN ('pending', 'sent', 'failed')",
            name="ck_reports_delivery_status",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    report_type: Mapped[str] = mapped_column(Text)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    content_html: Mapped[str] = mapped_column(Text)
    delivery_status: Mapped[str] = mapped_column(Text, default="pending")
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class InvestmentRecommendation(Base):
    __tablename__ = "investment_recommendations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.id")
    )
    surplus_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    rationale: Mapped[str] = mapped_column(Text)
    allocation_proposal: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
