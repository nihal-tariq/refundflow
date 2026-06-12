"""Aggregates all v1 route modules under a single router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import customers, events, logs, refund

api_v1_router = APIRouter()
api_v1_router.include_router(refund.router)
api_v1_router.include_router(customers.router)
api_v1_router.include_router(logs.router)
api_v1_router.include_router(events.router)
