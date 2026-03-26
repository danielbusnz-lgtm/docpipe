"""API response shapes for FastAPI endpoints.

Separate from domain models so we can change the API surface
without touching extraction logic.
"""

from typing import Optional

from pydantic import BaseModel

from src.models.domain import DocumentType, ProcessingStatus


class DocumentUploadResponse(BaseModel):
    """Returned immediately after a PDF is uploaded."""

    document_id: str
    filename: str
    status: ProcessingStatus = ProcessingStatus.UPLOADED


class DocumentDetail(BaseModel):
    """Full document info including extraction results.

    extracted_data is a generic dict because it could be an
    InvoiceExtraction, ReceiptExtraction, or ContractExtraction
    depending on doc_type. Kept loose here to avoid coupling
    the API schema to every extraction model.
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
    """Paginated list for GET /documents."""

    documents: list[DocumentDetail]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    """Quick connectivity check for all three backends."""

    status: str = "ok"
    postgres: bool
    dynamodb: bool
    s3: bool
