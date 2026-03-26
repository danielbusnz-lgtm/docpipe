"""API endpoints for document processing."""

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile

from src.api.deps import (
    DbSession,
    get_bedrock_client,
    get_dynamo_table,
    get_s3_client,
)
from src.config import settings
from src.db import dynamo
from src.models.schemas import (
    DocumentDetail,
    DocumentListResponse,
    DocumentUploadResponse,
    HealthResponse,
)
from src.pipeline.processor import process_document
from src.services.s3 import generate_presigned_url, upload_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["documents"])


@router.post("/documents", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    s3_client=Depends(get_s3_client),
    dynamo_table=Depends(get_dynamo_table),
    bedrock_client=Depends(get_bedrock_client),
    db: DbSession = None,
):
    """Upload a PDF and start processing in the background."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    document_id = str(uuid.uuid4())
    content = await file.read()

    # save to S3
    s3_key = upload_file(s3_client, settings.s3_bucket, content, file.filename, document_id)

    # create DynamoDB record
    dynamo.put_document(dynamo_table, document_id, file.filename, s3_key)

    # process in the background so the upload returns immediately
    background_tasks.add_task(
        process_document,
        document_id=document_id,
        s3_client=s3_client,
        bedrock_client=bedrock_client,
        dynamo_table=dynamo_table,
        db_session=db,
        bucket=settings.s3_bucket,
    )

    return DocumentUploadResponse(document_id=document_id, filename=file.filename)


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    dynamo_table=Depends(get_dynamo_table),
):
    """List documents, optionally filtered by processing status."""
    if status:
        items = dynamo.query_by_status(dynamo_table, status, limit=limit)
    else:
        # scan for all documents (not ideal at scale, but works for demo)
        response = dynamo_table.scan(Limit=limit)
        items = response.get("Items", [])

    documents = [
        DocumentDetail(
            document_id=item["document_id"],
            filename=item.get("filename", ""),
            s3_key=item.get("s3_key", ""),
            doc_type=item.get("doc_type"),
            status=item.get("status", "uploaded"),
            classification_confidence=float(item["classification_confidence"])
                if item.get("classification_confidence") else None,
            created_at=item.get("created_at", ""),
            updated_at=item.get("updated_at", ""),
            error_message=item.get("error_message"),
        )
        for item in items
    ]

    return DocumentListResponse(
        documents=documents, total=len(documents), limit=limit, offset=offset,
    )


@router.get("/documents/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: str,
    dynamo_table=Depends(get_dynamo_table),
):
    """Get full detail for a single document."""
    item = dynamo.get_document(dynamo_table, document_id)
    if not item:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentDetail(
        document_id=item["document_id"],
        filename=item.get("filename", ""),
        s3_key=item.get("s3_key", ""),
        doc_type=item.get("doc_type"),
        status=item.get("status", "uploaded"),
        classification_confidence=float(item["classification_confidence"])
            if item.get("classification_confidence") else None,
        created_at=item.get("created_at", ""),
        updated_at=item.get("updated_at", ""),
        error_message=item.get("error_message"),
    )


@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: str,
    s3_client=Depends(get_s3_client),
    dynamo_table=Depends(get_dynamo_table),
):
    """Get a presigned download URL for the original PDF."""
    item = dynamo.get_document(dynamo_table, document_id)
    if not item:
        raise HTTPException(status_code=404, detail="Document not found")

    url = generate_presigned_url(s3_client, settings.s3_bucket, item["s3_key"])
    if not url:
        raise HTTPException(status_code=500, detail="Failed to generate download URL")

    return {"download_url": url}


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    dynamo_table=Depends(get_dynamo_table),
):
    """Delete a document's metadata."""
    item = dynamo.get_document(dynamo_table, document_id)
    if not item:
        raise HTTPException(status_code=404, detail="Document not found")

    dynamo.delete_document(dynamo_table, document_id)
    return {"deleted": document_id}


@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: DbSession = None,
    s3_client=Depends(get_s3_client),
    dynamo_table=Depends(get_dynamo_table),
):
    """Check connectivity to all backends."""
    pg_ok = s3_ok = dynamo_ok = False

    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        pg_ok = True
    except Exception:
        pass

    try:
        s3_client.head_bucket(Bucket=settings.s3_bucket)
        s3_ok = True
    except Exception:
        pass

    try:
        dynamo_table.table_status
        dynamo_ok = True
    except Exception:
        pass

    return HealthResponse(postgres=pg_ok, dynamodb=dynamo_ok, s3=s3_ok)
