"""FastAPI dependency injection.

Create boto3 clients and database sessions once, share them
across requests. FastAPI's Depends() system handles the lifecycle.
"""

from collections.abc import Generator
from typing import Annotated

import anthropic
import boto3
from fastapi import Depends
from sqlalchemy.orm import Session

from src.config import settings
from src.db.session import SessionFactory


def get_db() -> Generator[Session, None, None]:
    """Yield a Postgres session, rollback on error, always close."""
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_s3_client():
    """Create an S3 client. Uses endpoint URL for LocalStack in dev."""
    kwargs = {"region_name": settings.aws_region}
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    return boto3.client("s3", **kwargs)


def get_dynamo_table():
    """Get the DynamoDB table resource."""
    kwargs = {"region_name": settings.aws_region}
    if settings.dynamo_endpoint_url:
        kwargs["endpoint_url"] = settings.dynamo_endpoint_url
    resource = boto3.resource("dynamodb", **kwargs)
    return resource.Table(settings.dynamo_table)


def get_anthropic_client():
    """Create an Anthropic client for Claude extraction."""
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


# type aliases for cleaner endpoint signatures
DbSession = Annotated[Session, Depends(get_db)]
