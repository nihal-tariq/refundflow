"""Customer profile routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.dependencies import get_customer_repository
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer import CustomerProfile

router = APIRouter(prefix="/customer", tags=["customers"])


@router.get(
    "/{customer_id}",
    response_model=CustomerProfile,
    summary="Fetch a customer profile",
)
def get_customer(
    customer_id: str,
    repo: CustomerRepository = Depends(get_customer_repository),
) -> CustomerProfile:
    """Return the CRM profile for ``customer_id``.

    Args:
        customer_id: The CRM customer id.
        repo: Injected customer repository.

    Raises:
        HTTPException: 404 if the customer does not exist.
    """
    profile = repo.get(customer_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{customer_id}' not found",
        )
    return profile


@router.get(
    "",
    response_model=list[CustomerProfile],
    summary="List all demo customers",
)
def list_customers(
    repo: CustomerRepository = Depends(get_customer_repository),
) -> list[CustomerProfile]:
    """Return all demo customer profiles (used by the UID picker)."""
    return repo.list_all()
