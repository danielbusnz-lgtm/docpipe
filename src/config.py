import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    s3_bucket: str = os.getenv("INKVAULT_S3_BUCKET", "inkvault-documents")
    dynamo_table: str = os.getenv("INKVAULT_DYNAMO_TABLE", "inkvault-metadata")
    pg_url: str = os.getenv(
        "INKVAULT_PG_URL",
        "postgresql://inkvault:inkvault@localhost:5432/inkvault",
    )
    bedrock_model_id: str = os.getenv(
        "INKVAULT_BEDROCK_MODEL",
        "anthropic.claude-sonnet-4-20250514",
    )
    s3_endpoint_url: str | None = os.getenv("INKVAULT_S3_ENDPOINT", None)
    dynamo_endpoint_url: str | None = os.getenv("INKVAULT_DYNAMO_ENDPOINT", None)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
