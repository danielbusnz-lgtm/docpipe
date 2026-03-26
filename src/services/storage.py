"""Write validated extractions to Postgres.

Maps Pydantic domain models to SQLAlchemy ORM rows and persists them.
The session is passed in so the caller (pipeline processor) controls
the transaction boundary.
"""

import logging
import uuid

from sqlalchemy.orm import Session

from src.models.database import (
    ContractExtractionRow,
    InvoiceExtractionRow,
    LineItemRow,
    ReceiptExtractionRow,
)
from src.models.domain import (
    ContractExtraction,
    DocumentType,
    InvoiceExtraction,
    ReceiptExtraction,
)

logger = logging.getLogger(__name__)


def _store_line_items(session: Session, extraction_id: uuid.UUID,
                      extraction_type: str, line_items: list) -> int:
    """Create LineItemRow for each line item. Returns count."""
    for item in line_items:
        row = LineItemRow(
            extraction_id=extraction_id,
            extraction_type=extraction_type,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            amount=item.amount,
            category=item.category,
        )
        session.add(row)
    return len(line_items)


def store_invoice(session: Session, document_id: uuid.UUID,
                  extraction: InvoiceExtraction, raw_json: dict | None = None):
    """Write an invoice extraction + its line items to Postgres."""
    row = InvoiceExtractionRow(
        document_id=document_id,
        vendor_name=extraction.vendor_name,
        invoice_number=extraction.invoice_number,
        invoice_date=extraction.invoice_date,
        due_date=extraction.due_date,
        subtotal=extraction.subtotal,
        tax=extraction.tax,
        total_amount=extraction.total_amount,
        currency=extraction.currency,
        payment_terms=extraction.payment_terms,
        raw_json=raw_json,
    )
    session.add(row)
    session.flush()  # get the generated row.id for line items

    count = _store_line_items(session, row.id, "invoice", extraction.line_items)
    logger.info("Stored invoice %s: %d line items", document_id, count)
    return row


def store_receipt(session: Session, document_id: uuid.UUID,
                  extraction: ReceiptExtraction, raw_json: dict | None = None):
    """Write a receipt extraction + its line items to Postgres."""
    row = ReceiptExtractionRow(
        document_id=document_id,
        vendor_name=extraction.vendor_name,
        receipt_date=extraction.receipt_date,
        subtotal=extraction.subtotal,
        tax=extraction.tax,
        total_amount=extraction.total_amount,
        payment_method=extraction.payment_method,
        raw_json=raw_json,
    )
    session.add(row)
    session.flush()

    count = _store_line_items(session, row.id, "receipt", extraction.line_items)
    logger.info("Stored receipt %s: %d line items", document_id, count)
    return row


def store_contract(session: Session, document_id: uuid.UUID,
                   extraction: ContractExtraction, raw_json: dict | None = None):
    """Write a contract extraction to Postgres. No line items."""
    row = ContractExtractionRow(
        document_id=document_id,
        parties=extraction.parties,
        effective_date=extraction.effective_date,
        expiration_date=extraction.expiration_date,
        contract_value=extraction.contract_value,
        key_terms=extraction.key_terms,
        summary=extraction.summary,
        raw_json=raw_json,
    )
    session.add(row)
    logger.info("Stored contract %s", document_id)
    return row


def store(session: Session, document_id: uuid.UUID, doc_type: DocumentType,
          extraction, raw_json: dict | None = None):
    """Route to the correct storage function based on document type."""
    if isinstance(extraction, InvoiceExtraction):
        return store_invoice(session, document_id, extraction, raw_json)
    elif isinstance(extraction, ReceiptExtraction):
        return store_receipt(session, document_id, extraction, raw_json)
    elif isinstance(extraction, ContractExtraction):
        return store_contract(session, document_id, extraction, raw_json)
    elif isinstance(extraction, dict):
        # generic extraction, just log it. Could store as JSON in future.
        logger.info("Generic extraction for %s, not stored in typed table", document_id)
        return None
    else:
        logger.warning("Unknown extraction type %s for %s", type(extraction), document_id)
        return None
