from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings

# One engine created once for the application
# pool_pre_ping=True helps recover from stale connections
# We use psycopg as the driver (SQLAlchemy 2.0 + psycopg3)
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    # Set statement timeout to prevent long-running queries from blocking the DB.
    # timezone=UTC: timestamptz values are returned in the session zone, so without it responses
    # would carry the server's local offset instead of UTC.
    connect_args={"options": "-c statement_timeout=30000 -c timezone=UTC"},  # 30 seconds
)

# SessionLocal is the factory for creating new Session objects
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a SQLAlchemy session per request.
    Ensures the session is always closed after the request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
