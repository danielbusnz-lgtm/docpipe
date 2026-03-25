"""SQLAlchemy ORM table definitions for PostgreSQL.

Map Python classes to Postgres tables. Each class represents one table
and each attribute represents one column. These mirror the Pydantic
domain models but define how data is persisted, not how it flows
through the pipeline.

Typical usage example:

    from src.db.session import get_session
    from src.models.database import Document

    with get_session() as session:
        doc = Document(id=uuid4(), filename="invoice.pdf", s3_key="docs/invoice.pdf")
        session.add(doc)
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
    """Anchor table for uploaded documents.

    Attributes:
        id: Unique identifier for the document.
        filename: Original name of the uploaded file.
        s3_key: Object key in the S3 bucket.
        doc_type: Classified document type (invoice, receipt, contract).
        created_at: When the document was uploaded.
        updated_at: Last status change timestamp.
    """

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
    """Structured data extracted from an invoice document.

    Attributes:
        id: Primary key.
        document_id: Foreign key to the documents table.
        vendor_name: Company that issued the invoice.
        invoice_number: Vendor's reference number.
        invoice_date: When the invoice was issued.
        due_date: Payment deadline.
        subtotal: Sum before tax.
        tax: Tax amount.
        total_amount: Final amount owed.
        currency: ISO 4217 currency code.
        payment_terms: Terms like "Net 30".
        raw_json: Full Bedrock response for debugging.
    """

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
    line_items: Mapped[list["LineItemRow"]] = relationship(
        back_populates="invoice_extraction",
        foreign_keys="LineItemRow.extraction_id",
    )


class ReceiptExtractionRow(Base):
    """Structured data extracted from a receipt document.

    Attributes:
        id: Primary key.
        document_id: Foreign key to the documents table.
        vendor_name: Business where the purchase was made.
        receipt_date: Date of the transaction.
        subtotal: Sum before tax.
        tax: Tax amount.
        total_amount: Final amount paid.
        payment_method: How payment was made.
        raw_json: Full Bedrock response for debugging.
    """

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
    line_items: Mapped[list["LineItemRow"]] = relationship(
        back_populates="receipt_extraction",
        foreign_keys="LineItemRow.extraction_id",
    )


class ContractExtractionRow(Base):
    """Structured data extracted from a contract document.

    Attributes:
        id: Primary key.
        document_id: Foreign key to the documents table.
        parties: Names of individuals or organizations.
        effective_date: When the contract takes effect.
        expiration_date: When the contract expires.
        contract_value: Total monetary value.
        key_terms: Notable clauses or conditions.
        summary: Brief description of the contract.
        raw_json: Full Bedrock response for debugging.
    """

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
    """A single line entry shared across invoice and receipt extractions.

    Attributes:
        id: Primary key.
        extraction_id: Foreign key to the parent extraction row.
        extraction_type: Which table the parent belongs to ("invoice" or "receipt").
        description: What was purchased or billed.
        quantity: Number of units.
        unit_price: Price per unit.
        amount: Total for this line.
        category: Optional expense category.
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

    invoice_extraction: Mapped[Optional["InvoiceExtractionRow"]] = relationship(
        back_populates="line_items",
        foreign_keys=[extraction_id],
        primaryjoin="LineItemRow.extraction_id == InvoiceExtractionRow.id",
    )
    receipt_extraction: Mapped[Optional["ReceiptExtractionRow"]] = relationship(
        back_populates="line_items",
        foreign_keys=[extraction_id],
        primaryjoin="LineItemRow.extraction_id == ReceiptExtractionRow.id",
    )
