"""Validate extraction results before saving to Postgres.

Checks that LLM-extracted data is internally consistent: line items
add up, dates make sense, required fields aren't empty. Returns
errors (block saving) and warnings (save but flag) separately so
the pipeline can decide what to do.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

from src.models.domain import (
    ContractExtraction,
    InvoiceExtraction,
    ReceiptExtraction,
)

logger = logging.getLogger(__name__)

DATE_FORMATS = ["%m/%d/%Y", "%B %d, %Y", "%d-%b-%Y", "%Y-%m-%d",
                "%m/%d/%y", "%b %d, %Y", "%d %B %Y"]

# how much rounding error we tolerate on dollar amounts
LINE_ITEM_TOLERANCE = 0.05
TOTAL_TOLERANCE = 0.50


@dataclass
class ValidationResult:
    """Outcome of validating an extraction."""

    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.is_valid = False

    def add_warning(self, msg: str):
        self.warnings.append(msg)


def _try_parse_date(date_str: str) -> datetime | None:
    """Try parsing a date string against common formats."""
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _validate_line_items(extraction, result: ValidationResult):
    """Check line item math for invoices and receipts."""
    if not extraction.line_items:
        result.add_error("No line items found")
        return

    for i, item in enumerate(extraction.line_items):
        if item.quantity <= 0:
            result.add_warning(f"Line {i+1}: negative or zero quantity ({item.quantity})")
        if item.unit_price < 0:
            result.add_warning(f"Line {i+1}: negative unit price ({item.unit_price})")

        expected = round(item.quantity * item.unit_price, 2)
        if abs(item.amount - expected) > LINE_ITEM_TOLERANCE:
            result.add_warning(
                f"Line {i+1}: amount {item.amount} != "
                f"qty {item.quantity} x price {item.unit_price} = {expected}"
            )

    # check line items sum to subtotal
    line_sum = round(sum(item.amount for item in extraction.line_items), 2)
    if extraction.subtotal is not None:
        if abs(line_sum - extraction.subtotal) > TOTAL_TOLERANCE:
            result.add_warning(
                f"Line items sum {line_sum} != subtotal {extraction.subtotal}"
            )


def _validate_totals(extraction, result: ValidationResult):
    """Check subtotal + tax = total for invoices and receipts."""
    if extraction.total_amount <= 0:
        result.add_error(f"Total amount must be positive, got {extraction.total_amount}")
        return

    if extraction.subtotal is not None and extraction.tax is not None:
        expected_total = round(extraction.subtotal + extraction.tax, 2)
        if abs(extraction.total_amount - expected_total) > TOTAL_TOLERANCE:
            result.add_warning(
                f"subtotal {extraction.subtotal} + tax {extraction.tax} = "
                f"{expected_total}, but total is {extraction.total_amount}"
            )


def validate_invoice(extraction: InvoiceExtraction) -> ValidationResult:
    """Check an extracted invoice for consistency."""
    result = ValidationResult()

    if not extraction.vendor_name or not extraction.vendor_name.strip():
        result.add_error("Vendor name is empty")

    _validate_line_items(extraction, result)
    _validate_totals(extraction, result)

    # date checks
    if extraction.invoice_date:
        parsed = _try_parse_date(extraction.invoice_date)
        if parsed is None:
            result.add_warning(f"Could not parse invoice date: {extraction.invoice_date}")

    if extraction.due_date:
        parsed_due = _try_parse_date(extraction.due_date)
        if parsed_due is None:
            result.add_warning(f"Could not parse due date: {extraction.due_date}")
        elif extraction.invoice_date:
            parsed_inv = _try_parse_date(extraction.invoice_date)
            if parsed_inv and parsed_due < parsed_inv:
                result.add_warning("Due date is before invoice date")

    return result


def validate_receipt(extraction: ReceiptExtraction) -> ValidationResult:
    """Check an extracted receipt for consistency."""
    result = ValidationResult()

    if not extraction.vendor_name or not extraction.vendor_name.strip():
        result.add_error("Vendor name is empty")

    _validate_line_items(extraction, result)
    _validate_totals(extraction, result)

    if extraction.receipt_date:
        if _try_parse_date(extraction.receipt_date) is None:
            result.add_warning(f"Could not parse receipt date: {extraction.receipt_date}")

    return result


def validate_contract(extraction: ContractExtraction) -> ValidationResult:
    """Check an extracted contract for consistency."""
    result = ValidationResult()

    if not extraction.parties:
        result.add_error("No parties listed")

    if extraction.contract_value is not None and extraction.contract_value < 0:
        result.add_warning(f"Negative contract value: {extraction.contract_value}")

    # date checks
    eff = exp = None
    if extraction.effective_date:
        eff = _try_parse_date(extraction.effective_date)
        if eff is None:
            result.add_warning(f"Could not parse effective date: {extraction.effective_date}")

    if extraction.expiration_date:
        exp = _try_parse_date(extraction.expiration_date)
        if exp is None:
            result.add_warning(f"Could not parse expiration date: {extraction.expiration_date}")

    if eff and exp and exp < eff:
        result.add_warning("Expiration date is before effective date")

    return result


def validate(extraction) -> ValidationResult:
    """Route to the correct validator based on extraction type.

    Accepts InvoiceExtraction, ReceiptExtraction, ContractExtraction,
    or a plain dict (generic extraction, always passes).
    """
    if isinstance(extraction, InvoiceExtraction):
        result = validate_invoice(extraction)
    elif isinstance(extraction, ReceiptExtraction):
        result = validate_receipt(extraction)
    elif isinstance(extraction, ContractExtraction):
        result = validate_contract(extraction)
    elif isinstance(extraction, dict):
        return ValidationResult()  # generic extractions always pass
    else:
        result = ValidationResult()
        result.add_error(f"Unknown extraction type: {type(extraction)}")

    if result.errors:
        logger.warning("Validation failed: %s", result.errors)
    if result.warnings:
        logger.info("Validation warnings: %s", result.warnings)

    return result
