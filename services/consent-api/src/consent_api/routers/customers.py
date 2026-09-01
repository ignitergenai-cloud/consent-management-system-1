"""Customer-scoped consent endpoints."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query

from cms_shared.models.consent import PaginatedConsentsResponse

from consent_api.dependencies import get_consent_repository
from consent_api.repositories.consent_repository import ConsentRepository

logger = structlog.get_logger()

router = APIRouter()


@router.get(
    "/customers/{customer_id}/consents",
    response_model=PaginatedConsentsResponse,
)
async def list_customer_consents(
    customer_id: str,
    page_size: int = Query(20, le=100),
    next_token: str | None = Query(None),
    repo: ConsentRepository = Depends(get_consent_repository),
) -> PaginatedConsentsResponse:
    """List all consents belonging to a specific customer."""
    return await repo.list_by_customer(
        customer_id=customer_id,
        page_size=page_size,
        next_token=next_token,
    )
