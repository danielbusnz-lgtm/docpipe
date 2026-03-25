"""DynamoDB CRUD operations for document metadata.

Handle the lifecycle tracking of documents as they move through the
processing pipeline. DynamoDB stores metadata and status, while
Postgres stores the actual extracted data.

Typical usage example:

    client = boto3.resource("dynamodb")
    table = client.Table("inkvault-metadata")
    put_document(table, document_id="abc-123", filename="invoice.pdf", s3_key="docs/invoice.pdf")
    update_status(table, document_id="abc-123", status="completed")
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
    """Create a new document metadata record.

    Args:
        table: A boto3 DynamoDB Table resource.
        document_id: Unique identifier for the document.
        filename: Original name of the uploaded file.
        s3_key: Object key in the S3 bucket.

    Returns:
        The item that was written to DynamoDB.
    """
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
    """Fetch a document metadata record by ID.

    Args:
        table: A boto3 DynamoDB Table resource.
        document_id: Unique identifier for the document.

    Returns:
        The document metadata dict, or None if not found.
    """
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
    """Update a document's processing status and optional fields.

    Args:
        table: A boto3 DynamoDB Table resource.
        document_id: Unique identifier for the document.
        status: New processing status.
        doc_type: Classified document type, if determined.
        classification_confidence: Classifier confidence score.
        error_message: Error details if processing failed.
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
    """List documents filtered by processing status.

    Uses the status-created_at-index GSI for efficient queries.

    Args:
        table: A boto3 DynamoDB Table resource.
        status: Processing status to filter by.
        limit: Maximum number of results to return.

    Returns:
        List of document metadata dicts, sorted by created_at descending.
    """
    response = table.query(
        IndexName="status-created_at-index",
        KeyConditionExpression=Key("status").eq(status),
        Limit=limit,
        ScanIndexForward=False,
    )
    return response.get("Items", [])


def delete_document(table, document_id: str) -> None:
    """Delete a document metadata record.

    Args:
        table: A boto3 DynamoDB Table resource.
        document_id: Unique identifier for the document.
    """
    table.delete_item(Key={"document_id": document_id})
    logger.info("Deleted document record: %s", document_id)
