"""S3 file operations for document storage.

Handle uploading, downloading, and generating presigned URLs for
PDF documents stored in S3. All functions accept an S3 client as
a parameter for testability with LocalStack.

Typical usage example:

    import boto3
    s3_client = boto3.client("s3")
    s3_key = upload_file(s3_client, "docpipe-documents", file_bytes, "invoice.pdf")
    local_path = download_to_temp(s3_client, "docpipe-documents", s3_key)
"""

import logging
import tempfile
from pathlib import Path

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def upload_file(
    client,
    bucket: str,
    file_bytes: bytes,
    filename: str,
    document_id: str,
) -> str:
    """Upload a PDF to S3.

    Args:
        client: A boto3 S3 client.
        bucket: Name of the S3 bucket.
        file_bytes: Raw file content.
        filename: Original filename for the S3 key.
        document_id: Unique document ID used as the key prefix.

    Returns:
        The S3 object key where the file was stored.
    """
    s3_key = f"documents/{document_id}/{filename}"
    client.put_object(Bucket=bucket, Key=s3_key, Body=file_bytes)
    logger.info("Uploaded %s to s3://%s/%s", filename, bucket, s3_key)
    return s3_key


def download_to_temp(
    client,
    bucket: str,
    s3_key: str,
) -> Path:
    """Download a file from S3 to a temporary local path.

    The caller is responsible for cleaning up the temp file.

    Args:
        client: A boto3 S3 client.
        bucket: Name of the S3 bucket.
        s3_key: Object key in the bucket.

    Returns:
        Path to the downloaded temporary file.
    """
    suffix = Path(s3_key).suffix or ".pdf"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    client.download_fileobj(bucket, s3_key, tmp)
    tmp.close()
    logger.info("Downloaded s3://%s/%s to %s", bucket, s3_key, tmp.name)
    return Path(tmp.name)


def generate_presigned_url(
    client,
    bucket: str,
    s3_key: str,
    expiration: int = 3600,
) -> str | None:
    """Generate a temporary download URL for an S3 object.

    Args:
        client: A boto3 S3 client.
        bucket: Name of the S3 bucket.
        s3_key: Object key in the bucket.
        expiration: URL lifetime in seconds. Defaults to 1 hour.

    Returns:
        The presigned URL string, or None if generation failed.
    """
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": s3_key},
            ExpiresIn=expiration,
        )
    except ClientError:
        logger.exception("Failed to generate presigned URL for %s", s3_key)
        return None
    return url
