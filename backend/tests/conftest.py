"""Shared pytest fixtures.

Configures an in-memory database and a fixed 'today' so policy/date logic is
deterministic regardless of when the suite runs.
"""

from __future__ import annotations

import os
from datetime import date

import pytest

# Use an isolated in-memory DB for tests before any app import.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_refundflow.db")

REFERENCE_TODAY = date(2026, 6, 12)


@pytest.fixture(scope="session")
def reference_today() -> date:
    """The fixed reference date the mock dataset was authored against."""
    return REFERENCE_TODAY


@pytest.fixture()
def db_session():
    """Yield a throwaway DB session against fresh tables."""
    from app.models.base import Base, SessionLocal, _engine

    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
