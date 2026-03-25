"""Postgres connection and session management."""

import logging
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(settings.pg_url, pool_pre_ping=True)
SessionFactory = sessionmaker(bind=engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Commit on success, rollback on error, always close."""
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Database session error")
        raise
    finally:
        session.close()
