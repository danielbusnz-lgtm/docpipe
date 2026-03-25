import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    s3_bucket: str = os.getenv("DOCPIPE_S3_BUCKET", "docpipe-documents")
    dynamo_table: str = os.getenv("DOCPIPE_DYNAMO_TABLE", "docpipe-metadata")
    pg_url: str = os.getenv(
        "DOCPIPE_PG_URL",
        "postgresql://docpipe:docpipe@localhost:5432/docpipe",
    )
    bedrock_model_id: str = os.getenv(
        "DOCPIPE_BEDROCK_MODEL",
        "anthropic.claude-sonnet-4-20250514",
    )
    s3_endpoint_url: str | None = os.getenv("DOCPIPE_S3_ENDPOINT", None)
    dynamo_endpoint_url: str | None = os.getenv("DOCPIPE_DYNAMO_ENDPOINT", None)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
