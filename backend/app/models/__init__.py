"""SQLAlchemy ORM models for the execution-trace database.

These tables provide durable, queryable observability: every agent run, every
emitted event, and every per-node state snapshot is persisted for replay and
audit. They are intentionally separate from the CRM mock data (JSON), which is
read-only reference data.
"""

from app.models.base import Base
from app.models.trace import AgentEventRecord, AgentSession, AgentStateSnapshot

__all__ = ["Base", "AgentSession", "AgentEventRecord", "AgentStateSnapshot"]
