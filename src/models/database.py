"""Postgres table definitions.

Extraction results live here. Document metadata (filename, status,
s3_key) lives in DynamoDB, so there's no documents table. The
extraction tables reference document_id as a plain UUID column
without a foreign key.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class InvoiceExtractionRow(Base):
    """Extracted invoice data. raw_json keeps the full Claude response for debugging."""

    __tablename__ = "invoice_extractions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
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


class ReceiptExtractionRow(Base):
    """Extracted receipt data. Same structure as invoice but with payment_method instead of due_date/terms."""

    __tablename__ = "receipt_extractions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    vendor_name: Mapped[str] = mapped_column(String(255))
    receipt_date: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    subtotal: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), default=None)
    tax: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), default=None)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2))
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class ContractExtractionRow(Base):
    """Extracted contract data. No line items or totals, just parties and terms."""

    __tablename__ = "contract_extractions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    parties: Mapped[Optional[list]] = mapped_column(ARRAY(Text), default=None)
    effective_date: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    expiration_date: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    contract_value: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), default=None)
    key_terms: Mapped[Optional[list]] = mapped_column(ARRAY(Text), default=None)
    summary: Mapped[Optional[str]] = mapped_column(Text, default=None)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=None)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


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
