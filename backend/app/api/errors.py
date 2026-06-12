"""Global exception handlers producing consistent, logged error responses.

Registering these centrally means routes and services can raise domain errors
(or let unexpected ones bubble) and the client always receives a uniform JSON
envelope, while the failure is logged with full context.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.observability.logging import get_logger
from app.tools.customer_lookup import CustomerLookupError
from app.tools.order_lookup import OrderLookupError

_logger = get_logger(__name__)


def _error_body(code: str, message: str, detail: object | None = None) -> dict:
    """Build the canonical error response envelope."""
    body = {"error": {"code": code, "message": message}}
    if detail is not None:
        body["error"]["detail"] = detail
    return body


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all global exception handlers to the FastAPI app."""

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Return 422 for request validation failures."""
        _logger.warning("validation_error", path=request.url.path, errors=exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body("validation_error", "Invalid request", exc.errors()),
        )

    @app.exception_handler(CustomerLookupError)
    async def _customer_handler(
        request: Request, exc: CustomerLookupError
    ) -> JSONResponse:
        """Return 404 for unresolved customers."""
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_error_body("customer_not_found", str(exc)),
        )

    @app.exception_handler(OrderLookupError)
    async def _order_handler(request: Request, exc: OrderLookupError) -> JSONResponse:
        """Return 404 for unresolved orders."""
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_error_body("order_not_found", str(exc)),
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        """Return 500 for unexpected errors, logging the full context."""
        _logger.error(
            "unhandled_exception",
            path=request.url.path,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("internal_error", "An unexpected error occurred"),
        )
