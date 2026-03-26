"""Test storage service with an in-memory SQLite database."""

import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from src.models.database import (
    Base,
    ContractExtractionRow,
    InvoiceExtractionRow,
    LineItemRow,
    ReceiptExtractionRow,
)
from src.models.domain import (
    ContractExtraction,
    DocumentType,
    InvoiceExtraction,
    LineItem,
    ReceiptExtraction,
)
from src.services.storage import store, store_contract, store_invoice, store_receipt


@pytest.fixture
def db_session():
    """Use the local Docker Postgres for testing. Skip if not available."""
    try:
        engine = create_engine("postgresql://inkvault:inkvault@localhost:5432/inkvault")
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("Postgres not available (run: docker compose up -d postgres)")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
        session.rollback()  # don't persist test data


@pytest.fixture
def doc_id():
    """Return a random UUID as a document ID."""
    return uuid.uuid4()


def _invoice():
    return InvoiceExtraction(
        vendor_name="Acme Corp",
        invoice_number="INV-001",
        invoice_date="03/15/2025",
        due_date="04/14/2025",
        line_items=[
            LineItem(description="Widget A", quantity=5, unit_price=20.0, amount=100.0),
            LineItem(description="Widget B", quantity=3, unit_price=50.0, amount=150.0),
        ],
        subtotal=250.0,
        tax=20.0,
        total_amount=270.0,
        currency="USD",
        payment_terms="Net 30",
    )


def _receipt():
    return ReceiptExtraction(
        vendor_name="Corner Store",
        receipt_date="03/25/2025",
        line_items=[
            LineItem(description="Milk", quantity=1, unit_price=4.99, amount=4.99),
        ],
        subtotal=4.99,
        tax=0.40,
        total_amount=5.39,
        payment_method="Cash",
    )


def _contract():
    return ContractExtraction(
        parties=["Acme Corp", "Smith LLC"],
        effective_date="April 1, 2025",
        expiration_date="March 31, 2026",
        contract_value=50000.0,
        key_terms=["Non-compete for 12 months"],
        summary="Consulting services agreement.",
    )


class TestStoreInvoice:
    def test_creates_extraction_row(self, db_session, doc_id):
        store_invoice(db_session, doc_id, _invoice())
        db_session.flush()

        row = db_session.query(InvoiceExtractionRow).filter_by(document_id=doc_id).first()
        assert row is not None
        assert row.vendor_name == "Acme Corp"
        assert row.total_amount == 270.0
        assert row.payment_terms == "Net 30"

    def test_creates_line_items(self, db_session, doc_id):
        store_invoice(db_session, doc_id, _invoice())
        db_session.flush()

        items = db_session.query(LineItemRow).filter_by(extraction_type="invoice").all()
        assert len(items) == 2
        assert items[0].description in ("Widget A", "Widget B")

    def test_stores_raw_json(self, db_session, doc_id):
        raw = {"raw": "bedrock response"}
        store_invoice(db_session, doc_id, _invoice(), raw_json=raw)
        db_session.flush()

        row = db_session.query(InvoiceExtractionRow).filter_by(document_id=doc_id).first()
        assert row.raw_json == raw


class TestStoreReceipt:
    def test_creates_extraction_row(self, db_session, doc_id):
        store_receipt(db_session, doc_id, _receipt())
        db_session.flush()

        row = db_session.query(ReceiptExtractionRow).filter_by(document_id=doc_id).first()
        assert row is not None
        assert row.vendor_name == "Corner Store"
        assert row.payment_method == "Cash"

    def test_creates_line_items(self, db_session, doc_id):
        store_receipt(db_session, doc_id, _receipt())
        db_session.flush()

        items = db_session.query(LineItemRow).filter_by(extraction_type="receipt").all()
        assert len(items) == 1
        assert items[0].description == "Milk"


class TestStoreContract:
    def test_creates_extraction_row(self, db_session, doc_id):
        store_contract(db_session, doc_id, _contract())
        db_session.flush()

        row = db_session.query(ContractExtractionRow).filter_by(document_id=doc_id).first()
        assert row is not None
        assert row.parties == ["Acme Corp", "Smith LLC"]
        assert row.contract_value == 50000.0

    def test_no_line_items_for_contracts(self, db_session, doc_id):
        store_contract(db_session, doc_id, _contract())
        db_session.flush()

        items = db_session.query(LineItemRow).all()
        assert len(items) == 0


class TestStoreRouter:
    def test_routes_invoice(self, db_session, doc_id):
        result = store(db_session, doc_id, DocumentType.INVOICE, _invoice())
        assert isinstance(result, InvoiceExtractionRow)

    def test_routes_receipt(self, db_session, doc_id):
        result = store(db_session, doc_id, DocumentType.RECEIPT, _receipt())
        assert isinstance(result, ReceiptExtractionRow)

    def test_routes_contract(self, db_session, doc_id):
        result = store(db_session, doc_id, DocumentType.CONTRACT, _contract())
        assert isinstance(result, ContractExtractionRow)

    def test_generic_returns_none(self, db_session, doc_id):
        result = store(db_session, doc_id, DocumentType.OTHER, {"summary": "some doc"})
        assert result is None
