"""Synchronous SQLAlchemy engine and FastAPI database dependency."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and close it when the request is complete."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
