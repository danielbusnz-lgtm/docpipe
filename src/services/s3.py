"""S3 file operations. Upload, download, presigned URLs."""

import logging
import tempfile
from pathlib import Path

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def upload_file(client, bucket: str, file_bytes: bytes, filename: str, document_id: str) -> str:
    """Store a file in S3 under documents/{document_id}/{filename}. Return the key."""
    s3_key = f"documents/{document_id}/{filename}"
    client.put_object(Bucket=bucket, Key=s3_key, Body=file_bytes)
    logger.info("Uploaded %s to s3://%s/%s", filename, bucket, s3_key)
    return s3_key


def download_to_temp(client, bucket: str, s3_key: str) -> Path:
    """Pull a file from S3 into a temp file. Caller must clean up."""
    suffix = Path(s3_key).suffix or ".pdf"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    client.download_fileobj(bucket, s3_key, tmp)
    tmp.close()
    logger.info("Downloaded s3://%s/%s to %s", bucket, s3_key, tmp.name)
    return Path(tmp.name)


def generate_presigned_url(client, bucket: str, s3_key: str, expiration: int = 3600) -> str | None:
    """Create a temporary download link. Returns None on failure."""
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
