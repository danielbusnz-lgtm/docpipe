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

from sqlalchemy import (
    ARRAY,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    s3_key = Column(String(500), nullable=False)
    doc_type = Column(String(50))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    invoice_extraction = relationship("InvoiceExtractionRow", back_populates="document", uselist=False)
    receipt_extraction = relationship("ReceiptExtractionRow", back_populates="document", uselist=False)
    contract_extraction = relationship("ContractExtractionRow", back_populates="document", uselist=False)


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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    vendor_name = Column(String(255), nullable=False)
    invoice_number = Column(String(100))
    invoice_date = Column(String(50))
    due_date = Column(String(50))
    subtotal = Column(Numeric(12, 2))
    tax = Column(Numeric(12, 2))
    total_amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="USD")
    payment_terms = Column(String(100))
    raw_json = Column(JSONB)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    document = relationship("Document", back_populates="invoice_extraction")
    line_items = relationship("LineItemRow", back_populates="extraction", foreign_keys="LineItemRow.extraction_id")


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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    vendor_name = Column(String(255), nullable=False)
    receipt_date = Column(String(50))
    subtotal = Column(Numeric(12, 2))
    tax = Column(Numeric(12, 2))
    total_amount = Column(Numeric(12, 2), nullable=False)
    payment_method = Column(String(50))
    raw_json = Column(JSONB)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    document = relationship("Document", back_populates="receipt_extraction")
    line_items = relationship("LineItemRow", back_populates="extraction", foreign_keys="LineItemRow.extraction_id")


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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    parties = Column(ARRAY(Text))
    effective_date = Column(String(50))
    expiration_date = Column(String(50))
    contract_value = Column(Numeric(12, 2))
    key_terms = Column(ARRAY(Text))
    summary = Column(Text)
    raw_json = Column(JSONB)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    document = relationship("Document", back_populates="contract_extraction")


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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    extraction_id = Column(UUID(as_uuid=True), nullable=False)
    extraction_type = Column(String(50), nullable=False)
    description = Column(String(500), nullable=False)
    quantity = Column(Numeric(10, 3), default=1.0)
    unit_price = Column(Numeric(12, 2))
    amount = Column(Numeric(12, 2), nullable=False)
    category = Column(String(100))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    extraction = relationship(
        "InvoiceExtractionRow",
        back_populates="line_items",
        foreign_keys=[extraction_id],
        primaryjoin="LineItemRow.extraction_id == InvoiceExtractionRow.id",
    )
