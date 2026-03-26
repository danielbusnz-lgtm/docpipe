"""Bedrock Claude extraction service.

Send classified document text to Claude via the Converse API and
get back structured data. Each document type has its own prompt
and Pydantic model. Uses Bedrock structured output (JSON schema)
so the response is guaranteed to parse.
"""

import json
import logging
from typing import Union

from botocore.exceptions import ClientError
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
    """Bedrock extraction failed after retries."""

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

def _truncate_text(text: str, max_chars: int = 180_000) -> str:
    """Keep text within Bedrock's context window."""
    if len(text) > max_chars:
        logger.warning("Truncating text from %d to %d chars", len(text), max_chars)
        return text[:max_chars]
    return text


def _build_output_config(model_class: type[BaseModel]) -> dict:
    """Build Bedrock outputConfig from a Pydantic model's JSON schema."""
    schema = model_class.model_json_schema()
    return {
        "textFormat": {
            "type": "json_schema",
            "structure": {
                "jsonSchema": {
                    "schema": json.dumps(schema),
                    "name": model_class.__name__,
                    "description": f"Structured extraction for {model_class.__name__}",
                }
            }
        }
    }


def _call_bedrock(client, model_id: str, system: str, user_msg: str,
                  output_config: dict | None) -> dict:
    """Make the Converse API call and return the raw response."""
    kwargs = {
        "modelId": model_id,
        "system": [{"text": system}],
        "messages": [{"role": "user", "content": [{"text": user_msg}]}],
        "inferenceConfig": {"maxTokens": 4096, "temperature": 0.0},
    }
    if output_config:
        kwargs["outputConfig"] = output_config

    response = client.converse(**kwargs)

    usage = response.get("usage", {})
    logger.info(
        "Bedrock: model=%s input_tokens=%s output_tokens=%s",
        model_id, usage.get("inputTokens", "?"), usage.get("outputTokens", "?"),
    )
    return response


def _parse_response(response: dict, model_class: type[BaseModel] | None) -> ExtractionResult:
    """Extract JSON from Converse response and validate against Pydantic model."""
    content = response["output"]["message"]["content"]
    text = content[0]["text"]
    data = json.loads(text)

    if model_class is None:
        return data

    return model_class.model_validate(data)


# --- Public API ---

def extract(
    client,
    text: str,
    doc_type: DocumentType,
    model_id: str = settings.bedrock_model_id,
    max_retries: int = 1,
) -> ExtractionResult:
    """Extract structured data from document text using Bedrock Claude.

    Routes to the correct prompt and Pydantic model based on doc_type.
    Returns a validated Pydantic model for invoice/receipt/contract,
    or a plain dict for other/unknown types.

    Args:
        client: A boto3 bedrock-runtime client.
        text: Raw text extracted from the document.
        doc_type: Classified document type.
        model_id: Bedrock model identifier.
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
    output_config = _build_output_config(model_class) if model_class else None

    last_error = None
    for attempt in range(1 + max_retries):
        try:
            response = _call_bedrock(client, model_id, SYSTEM_PROMPT, user_msg, output_config)
            result = _parse_response(response, model_class)
            logger.info("Extraction succeeded: doc_type=%s attempt=%d", doc_type.value, attempt + 1)
            return result
        except (ClientError, json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            logger.warning("Extraction attempt %d failed: %s", attempt + 1, exc)

    raise ExtractionError(
        f"Extraction failed after {1 + max_retries} attempts: {last_error}",
        raw_response=str(last_error),
    )
