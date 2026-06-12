"""API-level tests exercising the FastAPI app via TestClient."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_health_ok() -> None:
    """The health endpoint reports an ok status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_customer() -> None:
    """A known customer is returned with the expected tier."""
    response = client.get("/api/v1/customer/CUST-001")
    assert response.status_code == 200
    assert response.json()["tier"] == "vip"


def test_get_customer_404() -> None:
    """An unknown customer yields a 404."""
    assert client.get("/api/v1/customer/CUST-999").status_code == 404


def test_refund_request_approved() -> None:
    """The happy-path refund request returns an APPROVED decision."""
    response = client.post(
        "/api/v1/refund-request",
        json={
            "customer_id": "CUST-001",
            "order_id": "ORD-1001",
            "reason": "defective unit",
            "evidence_provided": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "APPROVED"
    assert body["session_id"].startswith("sess-")
    assert len(body["reasoning_log"]) >= 5


def test_trace_available_after_run() -> None:
    """A completed run is retrievable as a full trace for replay."""
    run = client.post(
        "/api/v1/refund-request",
        json={"customer_id": "CUST-004", "order_id": "ORD-1004", "reason": "changed mind"},
    ).json()
    trace = client.get(f"/api/v1/logs/{run['session_id']}")
    assert trace.status_code == 200
    assert trace.json()["session"]["final_decision"] == "DENIED"
    assert len(trace.json()["events"]) > 0
