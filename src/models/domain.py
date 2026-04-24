"""Data shapes for the extraction pipeline.

These Pydantic models define what Claude returns via the Anthropic API after
processing a document. Every other module consumes these: the
validator checks them, storage writes them to Postgres, the API
returns them.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Supported document categories for classification."""

    INVOICE = "invoice"
    RECEIPT = "receipt"
    CONTRACT = "contract"
    OTHER = "other"
    UNKNOWN = "unknown"


class ProcessingStatus(str, Enum):
    """Pipeline status, stored in DynamoDB so callers can poll for progress.

    FAILED also captures the error_message.
    """

    UPLOADED = "uploaded"
    CLASSIFYING = "classifying"
    EXTRACTING = "extracting"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class LineItem(BaseModel):
    """Single line on an invoice or receipt."""

    description: str
    quantity: float = Field(default=1.0, gt=0)
    unit_price: float
    amount: float
    category: Optional[str] = None


class InvoiceExtraction(BaseModel):
    """What Claude returns after parsing an invoice.

    Dates come back as strings because Claude's format is
    unpredictable (MM/DD/YYYY, "January 5, 2025", etc.).
    The validator normalizes them later.
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
    """What Claude returns after parsing a receipt.

    Receipts differ from invoices: they represent completed payments
    (no due_date or payment_terms), and include payment_method instead.
    """

    vendor_name: str
    receipt_date: Optional[str] = None
    line_items: list[LineItem]
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total_amount: float
    payment_method: Optional[str] = None


class ContractExtraction(BaseModel):
    """What Claude returns after parsing a contract.

    Structurally different from invoice/receipt: no line items or
    totals, but has parties, legal terms, and date ranges instead.
    """

    parties: list[str]
    effective_date: Optional[str] = None
    expiration_date: Optional[str] = None
    contract_value: Optional[float] = None
    key_terms: list[str] = Field(default_factory=list)
    summary: Optional[str] = None
