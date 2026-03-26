"""Test the extractor with mock Anthropic client."""

import json
from unittest.mock import MagicMock

import pytest
from anthropic import APIError

from src.models.domain import (
    ContractExtraction,
    DocumentType,
    InvoiceExtraction,
    ReceiptExtraction,
)
from src.services.extractor import (
    ExtractionError,
    _truncate_text,
    extract,
)


def _mock_response(data: dict):
    """Build a fake Anthropic messages.create() response."""
    response = MagicMock()
    content_block = MagicMock()
    content_block.text = json.dumps(data)
    response.content = [content_block]
    response.usage = MagicMock(input_tokens=150, output_tokens=80)
    return response


SAMPLE_INVOICE = {
    "vendor_name": "Acme Corp",
    "invoice_number": "INV-2025-001",
    "invoice_date": "03/15/2025",
    "due_date": "04/14/2025",
    "line_items": [
        {"description": "Widget", "quantity": 10, "unit_price": 25.0, "amount": 250.0}
    ],
    "subtotal": 250.0,
    "tax": 20.0,
    "total_amount": 270.0,
    "currency": "USD",
    "payment_terms": "Net 30",
}

SAMPLE_RECEIPT = {
    "vendor_name": "Corner Store",
    "receipt_date": "03/25/2025",
    "line_items": [
        {"description": "Milk", "quantity": 1, "unit_price": 4.99, "amount": 4.99},
        {"description": "Bread", "quantity": 2, "unit_price": 3.50, "amount": 7.00},
    ],
    "subtotal": 11.99,
    "tax": 0.96,
    "total_amount": 12.95,
    "payment_method": "Visa ending 4242",
}

SAMPLE_CONTRACT = {
    "parties": ["Acme Corp", "Smith Consulting LLC"],
    "effective_date": "April 1, 2025",
    "expiration_date": "March 31, 2026",
    "contract_value": 120000.0,
    "key_terms": ["Non-compete for 12 months", "Monthly payment of $10,000"],
    "summary": "Consulting agreement for software development services.",
}


class TestTruncateText:
    def test_short_text_unchanged(self):
        assert _truncate_text("hello", max_chars=100) == "hello"

    def test_long_text_truncated(self):
        text = "a" * 200
        assert len(_truncate_text(text, max_chars=100)) == 100


class TestExtract:
    def _make_client(self, response_data):
        client = MagicMock()
        client.messages.create.return_value = _mock_response(response_data)
        return client

    def test_invoice_extraction(self):
        client = self._make_client(SAMPLE_INVOICE)
        result = extract(client, "INVOICE #001 From Acme Corp Bill To Customer Due Date Net 30 Total $270.00 tax included", DocumentType.INVOICE)
        assert isinstance(result, InvoiceExtraction)
        assert result.vendor_name == "Acme Corp"
        client.messages.create.assert_called_once()

    def test_receipt_extraction(self):
        client = self._make_client(SAMPLE_RECEIPT)
        result = extract(client, "RECEIPT Corner Store 123 Main St Milk $4.99 Bread $3.50 Subtotal $8.49 Tax $0.68 Total $12.95", DocumentType.RECEIPT)
        assert isinstance(result, ReceiptExtraction)

    def test_contract_extraction(self):
        client = self._make_client(SAMPLE_CONTRACT)
        result = extract(client, "SERVICE AGREEMENT entered into by and between Acme Corp and Smith Consulting LLC effective April 1 2025", DocumentType.CONTRACT)
        assert isinstance(result, ContractExtraction)

    def test_generic_extraction(self):
        client = self._make_client({"summary": "utility bill", "amounts": [150.0]})
        result = extract(client, "Electric bill account number 12345 service address 123 Main St billing period January amount due $150.00", DocumentType.OTHER)
        assert isinstance(result, dict)

    def test_short_text_raises(self):
        client = MagicMock()
        with pytest.raises(ExtractionError, match="too short"):
            extract(client, "hi", DocumentType.INVOICE)
        client.messages.create.assert_not_called()

    def test_retry_on_failure(self):
        client = MagicMock()
        error = APIError(
            message="rate limited",
            request=MagicMock(),
            body={"error": {"message": "rate limited"}},
        )
        client.messages.create.side_effect = [
            error,
            _mock_response(SAMPLE_INVOICE),
        ]
        result = extract(client, "INVOICE #001 From Acme Corp Bill To Customer Due Date Net 30 Total Due $270.00 payment", DocumentType.INVOICE)
        assert isinstance(result, InvoiceExtraction)
        assert client.messages.create.call_count == 2

    def test_raises_after_retries_exhausted(self):
        client = MagicMock()
        error = APIError(
            message="rate limited",
            request=MagicMock(),
            body={"error": {"message": "rate limited"}},
        )
        client.messages.create.side_effect = error
        with pytest.raises(ExtractionError, match="failed after"):
            extract(client, "INVOICE #001 From Acme Corp Bill To Customer Due Date Net 30 Total Due $270.00 payment", DocumentType.INVOICE)
        assert client.messages.create.call_count == 2  # initial + 1 retry

    def test_called_with_correct_model(self):
        client = self._make_client(SAMPLE_INVOICE)
        extract(client, "INVOICE #001 From Acme Corp Bill To Customer Due Date Net 30 Total $270.00 tax", DocumentType.INVOICE, model="test-model")
        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "test-model"

    def test_output_config_included_for_typed_docs(self):
        client = self._make_client(SAMPLE_INVOICE)
        extract(client, "INVOICE #001 From Acme Corp Bill To Customer Due Date Net 30 Total $270.00 tax", DocumentType.INVOICE)
        call_kwargs = client.messages.create.call_args.kwargs
        assert "output_config" in call_kwargs

    def test_no_output_config_for_generic(self):
        client = self._make_client({"summary": "something"})
        extract(client, "Some random document text that is long enough to pass the minimum length check for processing", DocumentType.OTHER)
        call_kwargs = client.messages.create.call_args.kwargs
        assert "output_config" not in call_kwargs
