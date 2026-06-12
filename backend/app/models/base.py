"""SQLAlchemy declarative base and engine/session factory.

A single declarative ``Base`` is shared by all ORM models. The engine and
session factory are created from :class:`Settings` so tests can point at an
in-memory database. ``get_db`` is the FastAPI dependency yielding a scoped
session with guaranteed cleanup.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""


_settings = get_settings()

# ``check_same_thread`` is required for SQLite under FastAPI's threadpool.
_engine = create_engine(
    _settings.database_url,
    connect_args={"check_same_thread": False}
    if _settings.database_url.startswith("sqlite")
    else {},
    future=True,
)

SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create all tables. Idempotent; called once at application startup."""
    # Import side-effect ensures models are registered on ``Base.metadata``.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=_engine)


def get_db() -> Iterator[Session]:
    """Yield a database session and guarantee it is closed.

    Used as a FastAPI dependency so request handlers receive a fresh, properly
    torn-down session.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
