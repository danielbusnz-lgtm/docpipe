"""DynamoDB CRUD for document metadata and processing status.

Status tracking lives here instead of Postgres because Lambda
updates it 5+ times per document and DynamoDB handles that better
without connection pooling overhead.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)


def put_document(
    table,
    document_id: str,
    filename: str,
    s3_key: str,
) -> dict:
    """Create a new record with status 'uploaded'. Returns the item dict."""
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "document_id": document_id,
        "filename": filename,
        "s3_key": s3_key,
        "status": "uploaded",
        "created_at": now,
        "updated_at": now,
    }
    table.put_item(Item=item)
    logger.info("Created document record: %s", document_id)
    return item


def get_document(table, document_id: str) -> Optional[dict]:
    """Return the metadata dict for a document, or None if missing."""
    response = table.get_item(Key={"document_id": document_id})
    return response.get("Item")


def update_status(
    table,
    document_id: str,
    status: str,
    doc_type: Optional[str] = None,
    classification_confidence: Optional[float] = None,
    error_message: Optional[str] = None,
) -> None:
    """Move a document to a new status. Optionally set doc_type, confidence, or error.

    Uses #s alias for 'status' because it's a DynamoDB reserved word.
    """
    now = datetime.now(timezone.utc).isoformat()

    update_expr = "SET #s = :status, updated_at = :now"
    attr_names = {"#s": "status"}
    attr_values = {":status": status, ":now": now}

    if doc_type is not None:
        update_expr += ", doc_type = :doc_type"
        attr_values[":doc_type"] = doc_type

    if classification_confidence is not None:
        update_expr += ", classification_confidence = :confidence"
        attr_values[":confidence"] = str(classification_confidence)

    if error_message is not None:
        update_expr += ", error_message = :error"
        attr_values[":error"] = error_message

    table.update_item(
        Key={"document_id": document_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=attr_names,
        ExpressionAttributeValues=attr_values,
    )
    logger.info("Updated document %s status to %s", document_id, status)


def query_by_status(
    table,
    status: str,
    limit: int = 20,
) -> list[dict]:
    """Query the GSI for documents with a given status, newest first."""
    response = table.query(
        IndexName="status-created_at-index",
        KeyConditionExpression=Key("status").eq(status),
        Limit=limit,
        ScanIndexForward=False,
    )
    return response.get("Items", [])


def delete_document(table, document_id: str) -> None:
    """Remove a document metadata record.
    """
    table.delete_item(Key={"document_id": document_id})
    logger.info("Deleted document record: %s", document_id)
