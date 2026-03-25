"""PostgreSQL connection and session management.

Provide the SQLAlchemy engine and session factory used by the rest of
the application. All database access goes through sessions created here.

Typical usage example:

    with get_session() as session:
        session.execute(select(Document))
"""

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
    """Yield a SQLAlchemy session and handle cleanup.

    Commit on success, rollback on error, close when done.

    Yields:
        A SQLAlchemy Session bound to the configured Postgres database.
    """
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
