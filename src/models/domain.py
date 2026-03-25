"""Core domain models for document processing.

Define the data shapes that flow through the entire pipeline. These models
represent document types, processing states, and the structured data
extracted from invoices, receipts, and contracts via Bedrock Claude.

Typical usage example:

    extraction = InvoiceExtraction(
        vendor_name="Acme Corp",
        total_amount=1500.00,
        line_items=[LineItem(description="Widget", unit_price=50, amount=50)],
    )
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Supported document categories for classification."""

    INVOICE = "invoice"
    RECEIPT = "receipt"
    CONTRACT = "contract"
    UNKNOWN = "unknown"


class ProcessingStatus(str, Enum):
    """Track a document's position in the processing pipeline.

    Attributes:
        UPLOADED: PDF landed in S3, awaiting processing.
        CLASSIFYING: sklearn classifier determining document type.
        EXTRACTING: Bedrock Claude extracting structured data.
        VALIDATING: Pandas checking extraction integrity.
        COMPLETED: Extraction stored in Postgres successfully.
        FAILED: An error occurred, check error_message for details.
    """

    UPLOADED = "uploaded"
    CLASSIFYING = "classifying"
    EXTRACTING = "extracting"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class LineItem(BaseModel):
    """A single line entry on an invoice or receipt.

    Attributes:
        description: What was purchased or billed.
        quantity: Number of units. Must be greater than zero.
        unit_price: Price per unit.
        amount: Total for this line (quantity * unit_price).
        category: Optional expense category for accounting.
    """

    description: str
    quantity: float = Field(default=1.0, gt=0)
    unit_price: float
    amount: float
    category: Optional[str] = None


class InvoiceExtraction(BaseModel):
    """Structured data extracted from an invoice document.

    Attributes:
        vendor_name: Company or individual that issued the invoice.
        invoice_number: Vendor's reference number for this invoice.
        invoice_date: Date the invoice was issued (MM/DD/YYYY).
        due_date: Payment deadline (MM/DD/YYYY).
        line_items: Itemized charges on the invoice.
        subtotal: Sum before tax.
        tax: Tax amount.
        total_amount: Final amount owed including tax.
        currency: ISO 4217 currency code.
        payment_terms: Terms like "Net 30" or "Due on receipt".
    """

    vendor_name: str
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    line_items: list[LineItem]
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total_amount: float
    currency: str = "USD"
    payment_terms: Optional[str] = None


class ReceiptExtraction(BaseModel):
    """Structured data extracted from a receipt document.

    Attributes:
        vendor_name: Business where the purchase was made.
        receipt_date: Date of the transaction (MM/DD/YYYY).
        line_items: Itemized purchases on the receipt.
        subtotal: Sum before tax.
        tax: Tax amount.
        total_amount: Final amount paid.
        payment_method: How payment was made (e.g. "Visa ending 4242").
    """

    vendor_name: str
    receipt_date: Optional[str] = None
    line_items: list[LineItem]
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total_amount: float
    payment_method: Optional[str] = None


class ContractExtraction(BaseModel):
    """Structured data extracted from a contract document.

    Attributes:
        parties: Names of individuals or organizations in the agreement.
        effective_date: When the contract takes effect (MM/DD/YYYY).
        expiration_date: When the contract expires (MM/DD/YYYY).
        contract_value: Total monetary value if specified.
        key_terms: Notable clauses or conditions.
        summary: Brief description of the contract's purpose.
    """

    parties: list[str]
    effective_date: Optional[str] = None
    expiration_date: Optional[str] = None
    contract_value: Optional[float] = None
    key_terms: list[str] = Field(default_factory=list)
    summary: Optional[str] = None
