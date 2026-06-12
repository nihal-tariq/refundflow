"""Health-check route."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["system"])


@router.get("/health", summary="Liveness and dependency status")
def health() -> dict:
    """Return service liveness and key dependency flags.

    Returns:
        A dict with status, version, and whether the LLM layer is active.
    """
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "llm_enabled": settings.llm_enabled,
        "llm_provider": settings.llm_provider,
    }
