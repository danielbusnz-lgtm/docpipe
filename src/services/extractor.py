"""Claude extraction service.

Send classified document text to Claude via the Anthropic API and
get back structured data. Each document type has its own prompt
and Pydantic model. Uses structured output (JSON schema) so the
response is guaranteed to parse.
"""

import json
import logging
from typing import Union

from anthropic import APIError
from pydantic import BaseModel, ValidationError

from src.config import settings
from src.models.domain import (
    ContractExtraction,
    DocumentType,
    InvoiceExtraction,
    ReceiptExtraction,
)

logger = logging.getLogger(__name__)

ExtractionResult = Union[InvoiceExtraction, ReceiptExtraction, ContractExtraction, dict]


class ExtractionError(Exception):
    """Extraction failed after retries."""

    def __init__(self, message: str, raw_response: str | None = None):
        super().__init__(message)
        self.raw_response = raw_response


# --- Prompts ---

SYSTEM_PROMPT = (
    "You are a document data extraction specialist. You extract structured "
    "data from raw text that was obtained by running text extraction or OCR "
    "on PDF documents.\n\n"
    "The text may contain OCR artifacts, merged words, irregular spacing, "
    "and formatting noise. Extract accurate data despite these issues.\n\n"
    "When a field cannot be determined from the text, use null.\n"
    "For dates, preserve the original format from the document.\n"
    "For monetary amounts, use numeric values without currency symbols."
)

USER_PROMPTS = {
    DocumentType.INVOICE: (
        "Extract all structured data from this invoice document.\n\n"
        "Pay special attention to:\n"
        "- The vendor/seller name (company issuing the invoice)\n"
        "- Invoice number and dates (invoice date, due date)\n"
        "- Each line item with description, quantity, unit price, and amount\n"
        "- Subtotal, tax, and total amount\n"
        "- Currency (default to USD if not specified)\n"
        "- Payment terms (e.g. Net 30, Due on receipt)\n\n"
        "DOCUMENT TEXT:\n{text}"
    ),
    DocumentType.RECEIPT: (
        "Extract all structured data from this receipt document.\n\n"
        "Pay special attention to:\n"
        "- The vendor/store name\n"
        "- Receipt/transaction date\n"
        "- Each line item with description, quantity, and amount\n"
        "- Subtotal, tax, and total amount\n"
        "- Payment method (cash, credit card type, etc.)\n\n"
        "DOCUMENT TEXT:\n{text}"
    ),
    DocumentType.CONTRACT: (
        "Extract all structured data from this contract document.\n\n"
        "Pay special attention to:\n"
        "- All parties involved (full legal names)\n"
        "- Effective date and expiration date\n"
        "- Contract value or total compensation\n"
        "- Key terms and conditions (summarize each as a short phrase)\n"
        "- A 2-3 sentence summary of what the contract covers\n\n"
        "DOCUMENT TEXT:\n{text}"
    ),
}

GENERIC_USER_PROMPT = (
    "Extract whatever structured information you can find from this document.\n\n"
    "Look for:\n"
    "- Any names, organizations, or parties mentioned\n"
    "- Any dates\n"
    "- Any monetary amounts\n"
    "- A brief summary of the document's purpose\n\n"
    "Return a JSON object with keys: entities, dates, amounts, summary.\n\n"
    "DOCUMENT TEXT:\n{text}"
)

DOC_TYPE_TO_MODEL: dict[DocumentType, type[BaseModel] | None] = {
    DocumentType.INVOICE: InvoiceExtraction,
    DocumentType.RECEIPT: ReceiptExtraction,
    DocumentType.CONTRACT: ContractExtraction,
    DocumentType.OTHER: None,
    DocumentType.UNKNOWN: None,
}


# --- Internal helpers ---

_UNSUPPORTED_KEYS = {"exclusiveMinimum", "exclusiveMaximum", "minimum", "maximum"}


def _clean_schema(schema: dict) -> dict:
    """Make a Pydantic JSON schema compatible with Anthropic's structured output.

    Adds additionalProperties: false on all objects and strips
    validation keywords that Anthropic doesn't support.
    """
    if schema.get("type") == "object":
        schema["additionalProperties"] = False
    for key in _UNSUPPORTED_KEYS:
        schema.pop(key, None)
    for key in ("properties", "$defs"):
        if key in schema:
            for prop in schema[key].values():
                if isinstance(prop, dict):
                    _clean_schema(prop)
    if "items" in schema and isinstance(schema["items"], dict):
        _clean_schema(schema["items"])
    return schema


def _truncate_text(text: str, max_chars: int = 180_000) -> str:
    """Keep text within Claude's context window."""
    if len(text) > max_chars:
        logger.warning("Truncating text from %d to %d chars", len(text), max_chars)
        return text[:max_chars]
    return text


def _call_anthropic(client, model: str, system: str, user_msg: str,
                    model_class: type[BaseModel] | None) -> ExtractionResult:
    """Call the Anthropic API and return parsed extraction result.

    Uses messages.create() with output_config for typed documents
    (guaranteed JSON schema output), falls back to plain messages
    for generic/unknown types.
    """
    if model_class is not None:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            temperature=0.0,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": _clean_schema(model_class.model_json_schema()),
                }
            },
        )
        usage = response.usage
        logger.info(
            "Anthropic: model=%s input_tokens=%s output_tokens=%s",
            model, usage.input_tokens, usage.output_tokens,
        )
        data = json.loads(response.content[0].text)
        return model_class.model_validate(data)
    else:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            temperature=0.0,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        usage = response.usage
        logger.info(
            "Anthropic: model=%s input_tokens=%s output_tokens=%s",
            model, usage.input_tokens, usage.output_tokens,
        )
        return json.loads(response.content[0].text)


# --- Public API ---

def extract(
    client,
    text: str,
    doc_type: DocumentType,
    model: str = settings.anthropic_model,
    max_retries: int = 1,
) -> ExtractionResult:
    """Extract structured data from document text using Claude.

    Routes to the correct prompt and Pydantic model based on doc_type.
    Returns a validated Pydantic model for invoice/receipt/contract,
    or a plain dict for other/unknown types.

    Args:
        client: An anthropic.Anthropic client.
        text: Raw text extracted from the document.
        doc_type: Classified document type.
        model: Anthropic model identifier.
        max_retries: How many times to retry on failure.

    Raises:
        ExtractionError: If extraction fails after all retries.
    """
    text = _truncate_text(text)

    if len(text.strip()) < 50:
        raise ExtractionError("Document text too short for extraction")

    model_class = DOC_TYPE_TO_MODEL.get(doc_type)
    user_template = USER_PROMPTS.get(doc_type, GENERIC_USER_PROMPT)
    user_msg = user_template.format(text=text)

    last_error = None
    for attempt in range(1 + max_retries):
        try:
            result = _call_anthropic(client, model, SYSTEM_PROMPT, user_msg, model_class)
            logger.info("Extraction succeeded: doc_type=%s attempt=%d", doc_type.value, attempt + 1)
            return result
        except (APIError, json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            logger.warning("Extraction attempt %d failed: %s", attempt + 1, exc)

    raise ExtractionError(
        f"Extraction failed after {1 + max_retries} attempts: {last_error}",
        raw_response=str(last_error),
    )
