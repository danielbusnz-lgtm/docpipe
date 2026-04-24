"""Process a document end to end.

This is the glue that calls each service in order:
classify → extract → validate → store. Each step updates
the document's status in DynamoDB so callers can poll progress.
"""

import logging
import os

from pypdf import PdfReader

from src.db import dynamo
from src.models.domain import DocumentType
from src.services import classifier, extractor, storage, validator
from src.services.s3 import download_to_temp

logger = logging.getLogger(__name__)


def _extract_text(s3_client, bucket: str, s3_key: str) -> str:
    """Download PDF from S3 and extract text with pypdf."""
    tmp_path = download_to_temp(s3_client, bucket, s3_key)
    try:
        reader = PdfReader(str(tmp_path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    finally:
        os.unlink(tmp_path)  # always clean up the temp file
    return text


def process_document(
    document_id: str,
    s3_client,
    anthropic_client,
    dynamo_table,
    db_session,
    bucket: str,
):
    """Run the full pipeline on one document.

    Args:
        document_id: The document to process.
        s3_client: boto3 S3 client.
        anthropic_client: anthropic.Anthropic client.
        dynamo_table: boto3 DynamoDB Table resource.
        db_session: SQLAlchemy session.
        bucket: S3 bucket name.
    """
    try:
        # get the document metadata
        doc = dynamo.get_document(dynamo_table, document_id)
        if not doc:
            logger.error("Document %s not found in DynamoDB", document_id)
            return
        s3_key = doc["s3_key"]

        # --- step 1: classify ---
        dynamo.update_status(dynamo_table, document_id, "classifying")

        text = _extract_text(s3_client, bucket, s3_key)
        doc_type_str, confidence = classifier.classify(text)
        doc_type = DocumentType(doc_type_str) if doc_type_str != "unknown" else DocumentType.UNKNOWN

        dynamo.update_status(
            dynamo_table, document_id, "extracting",
            doc_type=doc_type.value,
            classification_confidence=confidence,
        )
        logger.info("Classified %s as %s (%.1f%%)", document_id, doc_type.value, confidence * 100)

        # --- step 2: extract ---
        if doc_type in (DocumentType.UNKNOWN, DocumentType.OTHER):
            # skip Claude extraction for unknown/other, nothing useful to extract
            dynamo.update_status(dynamo_table, document_id, "completed")
            logger.info("Skipping extraction for %s (type=%s)", document_id, doc_type.value)
            return

        extraction = extractor.extract(anthropic_client, text, doc_type)

        # --- step 3: validate ---
        dynamo.update_status(dynamo_table, document_id, "validating")

        result = validator.validate(extraction)
        if not result.is_valid:
            dynamo.update_status(
                dynamo_table, document_id, "failed",
                error_message=f"Validation errors: {'; '.join(result.errors)}",
            )
            logger.warning("Validation failed for %s: %s", document_id, result.errors)
            return

        if result.warnings:
            logger.info("Validation warnings for %s: %s", document_id, result.warnings)

        # --- step 4: store ---
        import uuid
        storage.store(db_session, uuid.UUID(document_id), doc_type, extraction)
        db_session.commit()

        dynamo.update_status(dynamo_table, document_id, "completed")
        logger.info("Document %s processed successfully", document_id)

    except Exception as exc:
        logger.exception("Pipeline failed for %s", document_id)
        try:
            dynamo.update_status(
                dynamo_table, document_id, "failed",
                error_message=str(exc)[:500],
            )
        except Exception:
            logger.exception("Failed to update status for %s", document_id)
        raise
