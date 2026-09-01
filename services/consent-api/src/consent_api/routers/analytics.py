"""Analytics endpoints for consent metrics."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query

from cms_shared.models.consent import ConsentAnalytics

from consent_api.dependencies import get_consent_service
from consent_api.services.consent_service import ConsentService

logger = structlog.get_logger()

router = APIRouter()


@router.get("/analytics/consents", response_model=ConsentAnalytics)
async def get_consent_analytics(
    from_date: str | None = Query(None, description="ISO-format start date"),
    to_date: str | None = Query(None, description="ISO-format end date"),
    service: ConsentService = Depends(get_consent_service),
) -> ConsentAnalytics:
    """Return aggregated consent analytics with optional date range filters."""
    return await service.get_analytics(from_date=from_date, to_date=to_date)
