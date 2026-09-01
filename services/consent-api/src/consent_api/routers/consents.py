"""CRUD endpoints for consent records."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from cms_shared.models.consent import (
    ConsentChannel,
    ConsentRecord,
    ConsentStatus,
    CreateConsentRequest,
    CreateConsentResponse,
    ListConsentsQuery,
    PaginatedConsentsResponse,
)

from consent_api.dependencies import get_consent_service
from consent_api.services.command_handler import get_pause_reason, is_paused
from consent_api.services.consent_service import ConsentService

logger = structlog.get_logger()

router = APIRouter()


@router.post("/consents", response_model=CreateConsentResponse, status_code=201)
async def create_consent(
    request: CreateConsentRequest,
    service: ConsentService = Depends(get_consent_service),
) -> CreateConsentResponse:
    """Create a new consent request."""
    if is_paused():
        raise HTTPException(
            status_code=503,
            detail=f"Consent collection is currently paused: {get_pause_reason()}",
        )
    return await service.create_consent(request)


@router.get("/consents", response_model=PaginatedConsentsResponse)
async def list_consents(
    status: ConsentStatus | None = Query(None),
    channel: ConsentChannel | None = Query(None),
    customer_id: str | None = Query(None),
    page_size: int = Query(20, le=100),
    next_token: str | None = Query(None),
    service: ConsentService = Depends(get_consent_service),
) -> PaginatedConsentsResponse:
    """List consents with optional filters."""
    query = ListConsentsQuery(
        status=status,
        channel=channel,
        customer_id=customer_id,
        page_size=page_size,
        next_token=next_token,
    )
    return await service.list_consents(query)


@router.get("/consents/{consent_id}", response_model=ConsentRecord)
async def get_consent(
    consent_id: str,
    service: ConsentService = Depends(get_consent_service),
) -> ConsentRecord:
    """Retrieve a single consent record by ID."""
    return await service.get_consent(consent_id)


@router.patch("/consents/{consent_id}", response_model=ConsentRecord)
async def update_consent(
    consent_id: str,
    updates: dict[str, Any],
    service: ConsentService = Depends(get_consent_service),
) -> ConsentRecord:
    """Apply partial updates to a consent record."""
    return await service.update_consent(consent_id, updates)


@router.delete("/consents/{consent_id}", response_model=ConsentRecord)
async def revoke_consent(
    consent_id: str,
    service: ConsentService = Depends(get_consent_service),
) -> ConsentRecord:
    """Revoke (soft-delete) a consent record."""
    return await service.revoke_consent(consent_id)


@router.post(
    "/consents/bulk",
    response_model=list[CreateConsentResponse],
    status_code=201,
)
async def bulk_create_consents(
    requests: list[CreateConsentRequest],
    service: ConsentService = Depends(get_consent_service),
) -> list[CreateConsentResponse]:
    """Create multiple consent requests in a single call."""
    if is_paused():
        raise HTTPException(
            status_code=503,
            detail=f"Consent collection is currently paused: {get_pause_reason()}",
        )
    return await service.bulk_create(requests)


@router.get("/consents/{consent_id}/history")
async def get_consent_history(
    consent_id: str,
    service: ConsentService = Depends(get_consent_service),
) -> list[dict[str, Any]]:
    """Retrieve the full audit trail for a consent record."""
    return await service.get_history(consent_id)
