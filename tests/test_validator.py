"""Test validation rules for extracted document data."""

from src.models.domain import (
    ContractExtraction,
    InvoiceExtraction,
    LineItem,
    ReceiptExtraction,
)
from src.services.validator import validate


def _good_invoice(**overrides):
    defaults = {
        "vendor_name": "Acme Corp",
        "invoice_number": "INV-001",
        "invoice_date": "03/15/2025",
        "due_date": "04/14/2025",
        "line_items": [LineItem(description="Widget", quantity=10, unit_price=25.0, amount=250.0)],
        "subtotal": 250.0,
        "tax": 20.0,
        "total_amount": 270.0,
    }
    defaults.update(overrides)
    return InvoiceExtraction(**defaults)


def _good_receipt(**overrides):
    defaults = {
        "vendor_name": "Corner Store",
        "receipt_date": "03/25/2025",
        "line_items": [LineItem(description="Milk", quantity=1, unit_price=4.99, amount=4.99)],
        "subtotal": 4.99,
        "tax": 0.40,
        "total_amount": 5.39,
    }
    defaults.update(overrides)
    return ReceiptExtraction(**defaults)


def _good_contract(**overrides):
    defaults = {
        "parties": ["Acme Corp", "Smith LLC"],
        "effective_date": "April 1, 2025",
        "expiration_date": "March 31, 2026",
        "contract_value": 50000.0,
        "key_terms": ["Non-compete"],
        "summary": "Consulting agreement.",
    }
    defaults.update(overrides)
    return ContractExtraction(**defaults)


class TestInvoiceValidation:
    def test_valid_invoice_passes(self):
        result = validate(_good_invoice())
        assert result.is_valid
        assert not result.errors
        assert not result.warnings

    def test_empty_vendor_fails(self):
        result = validate(_good_invoice(vendor_name=""))
        assert not result.is_valid
        assert any("Vendor name" in e for e in result.errors)

    def test_whitespace_vendor_fails(self):
        result = validate(_good_invoice(vendor_name="   "))
        assert not result.is_valid

    def test_no_line_items_fails(self):
        result = validate(_good_invoice(line_items=[]))
        assert not result.is_valid
        assert any("No line items" in e for e in result.errors)

    def test_negative_total_fails(self):
        result = validate(_good_invoice(total_amount=-100))
        assert not result.is_valid

    def test_line_item_math_warning(self):
        bad_item = LineItem(description="X", quantity=2, unit_price=10.0, amount=25.0)
        result = validate(_good_invoice(line_items=[bad_item], subtotal=25.0, total_amount=25.0))
        assert result.is_valid  # warning not error
        assert any("amount 25.0 !=" in w for w in result.warnings)

    def test_subtotal_mismatch_warning(self):
        item = LineItem(description="X", quantity=1, unit_price=100.0, amount=100.0)
        result = validate(_good_invoice(line_items=[item], subtotal=200.0, tax=0, total_amount=200.0))
        assert any("subtotal" in w.lower() for w in result.warnings)

    def test_total_mismatch_warning(self):
        result = validate(_good_invoice(subtotal=250.0, tax=20.0, total_amount=999.0))
        assert any("total" in w.lower() for w in result.warnings)

    def test_unparseable_date_warning(self):
        result = validate(_good_invoice(invoice_date="not a date"))
        assert result.is_valid
        assert any("parse" in w.lower() for w in result.warnings)

    def test_due_before_invoice_warning(self):
        result = validate(_good_invoice(invoice_date="04/14/2025", due_date="03/15/2025"))
        assert any("before" in w.lower() for w in result.warnings)

    def test_rounding_tolerance(self):
        # 3 x 33.33 = 99.99, amount says 100.00. Within tolerance.
        item = LineItem(description="X", quantity=3, unit_price=33.33, amount=99.99)
        result = validate(_good_invoice(line_items=[item], subtotal=99.99, tax=0, total_amount=99.99))
        assert result.is_valid
        assert not result.warnings


class TestReceiptValidation:
    def test_valid_receipt_passes(self):
        result = validate(_good_receipt())
        assert result.is_valid

    def test_empty_vendor_fails(self):
        result = validate(_good_receipt(vendor_name=""))
        assert not result.is_valid

    def test_unparseable_date_warning(self):
        result = validate(_good_receipt(receipt_date="garbage"))
        assert result.is_valid
        assert len(result.warnings) > 0


class TestContractValidation:
    def test_valid_contract_passes(self):
        result = validate(_good_contract())
        assert result.is_valid

    def test_no_parties_fails(self):
        result = validate(_good_contract(parties=[]))
        assert not result.is_valid

    def test_negative_value_warning(self):
        result = validate(_good_contract(contract_value=-5000))
        assert result.is_valid
        assert any("Negative" in w for w in result.warnings)

    def test_expiration_before_effective_warning(self):
        result = validate(_good_contract(
            effective_date="01/01/2026", expiration_date="01/01/2025"
        ))
        assert any("before" in w.lower() for w in result.warnings)

    def test_unparseable_dates_warning(self):
        result = validate(_good_contract(effective_date="??", expiration_date="!!"))
        assert len(result.warnings) == 2


class TestGenericValidation:
    def test_dict_always_passes(self):
        result = validate({"summary": "some document", "entities": ["John"]})
        assert result.is_valid
        assert not result.errors
