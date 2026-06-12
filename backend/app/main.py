"""FastAPI application factory and ASGI entrypoint.

Wires configuration, structured logging, CORS, the versioned API router, the
health route, and global exception handlers. Kept deliberately small — all real
work lives in services and the agent.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.v1 import api_v1_router
from app.api.v1.routes import health
from app.config import get_settings
from app.models.base import init_db
from app.observability.logging import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize logging and the database on startup."""
    configure_logging()
    init_db()
    get_logger(__name__).info("startup_complete", app=get_settings().app_name)
    yield


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Returns:
        A fully-wired :class:`FastAPI` instance.
    """
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI Customer Support Agent for e-commerce refunds.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
    register_exception_handlers(app)
    return app


app = create_app()
