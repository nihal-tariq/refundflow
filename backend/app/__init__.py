"""RefundFlow AI — production-grade agentic refund adjudication backend.

The package is organized in clean-architecture layers:

* ``api``           — FastAPI transport (no business logic).
* ``agents``        — LangGraph workflow, nodes, and state.
* ``tools``         — deterministic, independently-testable agent tools.
* ``services``      — business logic / orchestration.
* ``repositories``  — data access (CRM JSON + trace SQLite DB).
* ``models``        — SQLAlchemy ORM models.
* ``schemas``       — Pydantic request/response contracts.
* ``observability`` — structured logging + the SSE event bus.
* ``config``        — typed application settings.
"""

__version__ = "1.0.0"
