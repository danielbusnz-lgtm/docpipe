"""Postgres table definitions.

These mirror the Pydantic domain models but handle persistence.
Each extraction type gets its own table linked back to documents
via foreign key. Line items are shared across invoices and receipts.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class Document(Base):
    """One row per uploaded PDF. Everything else links back here."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255))
    s3_key: Mapped[str] = mapped_column(String(500))
    doc_type: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    invoice_extraction: Mapped[Optional["InvoiceExtractionRow"]] = relationship(back_populates="document", uselist=False)
    receipt_extraction: Mapped[Optional["ReceiptExtractionRow"]] = relationship(back_populates="document", uselist=False)
    contract_extraction: Mapped[Optional["ContractExtractionRow"]] = relationship(back_populates="document", uselist=False)


class InvoiceExtractionRow(Base):
    """Extracted invoice data. raw_json keeps the full Bedrock response for debugging."""

    __tablename__ = "invoice_extractions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"))
    vendor_name: Mapped[str] = mapped_column(String(255))
    invoice_number: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    invoice_date: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    due_date: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    subtotal: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), default=None)
    tax: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), default=None)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    payment_terms: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    document: Mapped["Document"] = relationship(back_populates="invoice_extraction")


class ReceiptExtractionRow(Base):
    """Extracted receipt data. Same structure as invoice but with payment_method instead of due_date/terms."""

    __tablename__ = "receipt_extractions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"))
    vendor_name: Mapped[str] = mapped_column(String(255))
    receipt_date: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    subtotal: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), default=None)
    tax: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), default=None)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2))
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    document: Mapped["Document"] = relationship(back_populates="receipt_extraction")


class ContractExtractionRow(Base):
    """Extracted contract data. No line items or totals, just parties and terms."""

    __tablename__ = "contract_extractions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"))
    parties: Mapped[Optional[list]] = mapped_column(ARRAY(Text), default=None)
    effective_date: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    expiration_date: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    contract_value: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), default=None)
    key_terms: Mapped[Optional[list]] = mapped_column(ARRAY(Text), default=None)
    summary: Mapped[Optional[str]] = mapped_column(Text, default=None)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    document: Mapped["Document"] = relationship(back_populates="contract_extraction")


class LineItemRow(Base):
    """Shared across invoices and receipts.

    extraction_type tracks which table the parent lives in since
    extraction_id could point to either invoice_extractions or
    receipt_extractions.
    """

    __tablename__ = "line_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    extraction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    extraction_type: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(500))
    quantity: Mapped[Optional[float]] = mapped_column(Numeric(10, 3), default=1.0)
    unit_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), default=None)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    category: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    # no ORM relationship here because extraction_id can point to
    # either invoice_extractions or receipt_extractions. We query
    # line items directly by extraction_id + extraction_type instead.
