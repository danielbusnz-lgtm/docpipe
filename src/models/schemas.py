"""API request and response schemas.

Define the shapes for data entering and leaving the FastAPI endpoints.
These are separate from domain models to keep API concerns decoupled
from core extraction logic.
"""

from typing import Optional

from pydantic import BaseModel, Field

from src.models.domain import DocumentType, ProcessingStatus


class DocumentUploadResponse(BaseModel):
    """Return after a successful document upload.

    Attributes:
        document_id: Unique identifier assigned to the uploaded document.
        filename: Original name of the uploaded file.
        status: Initial processing status, always UPLOADED.
    """

    document_id: str
    filename: str
    status: ProcessingStatus = ProcessingStatus.UPLOADED


class DocumentDetail(BaseModel):
    """Full detail for a single document including extraction results.

    Attributes:
        document_id: Unique identifier for the document.
        filename: Original name of the uploaded file.
        s3_key: Object key in the S3 bucket.
        doc_type: Classified document type, if determined.
        status: Current position in the processing pipeline.
        classification_confidence: Classifier's confidence score (0.0 to 1.0).
        created_at: ISO timestamp of when the document was uploaded.
        updated_at: ISO timestamp of the last status change.
        error_message: Error details if processing failed.
        extracted_data: Structured extraction results from Bedrock Claude.
    """

    document_id: str
    filename: str
    s3_key: str
    doc_type: Optional[DocumentType] = None
    status: ProcessingStatus
    classification_confidence: Optional[float] = None
    created_at: str
    updated_at: str
    error_message: Optional[str] = None
    extracted_data: Optional[dict] = None


class DocumentListResponse(BaseModel):
    """Paginated list of documents.

    Attributes:
        documents: List of document details for the current page.
        total: Total number of documents matching the query.
        limit: Maximum number of documents per page.
        offset: Number of documents skipped from the start.
    """

    documents: list[DocumentDetail]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    """Health check response for service dependencies.

    Attributes:
        status: Overall health status.
        postgres: Whether the PostgreSQL connection is alive.
        dynamodb: Whether the DynamoDB table is accessible.
        s3: Whether the S3 bucket is reachable.
    """

    status: str = "ok"
    postgres: bool
    dynamodb: bool
    s3: bool
