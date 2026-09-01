"""Tests for consent CRUD endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from cms_shared.models.consent import (
    ConsentChannel,
    ConsentRecord,
    ConsentStatus,
    ConsentType,
    CreateConsentResponse,
    PaginatedConsentsResponse,
)


@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient) -> None:
    """GET /api/v1/health returns healthy status."""
    resp = await async_client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "consent-api"


@pytest.mark.asyncio
async def test_create_consent(
    async_client: AsyncClient,
    sample_consent_record: ConsentRecord,
) -> None:
    """POST /api/v1/consents creates a consent and returns 201."""
    now = datetime.now(timezone.utc)
    mock_response = CreateConsentResponse(
        consent_id="new-id",
        status=ConsentStatus.PENDING,
        response_url="http://localhost:8000/api/v1/consents/respond/token",
        expires_at=now + timedelta(hours=72),
        created_at=now,
    )

    with patch(
        "consent_api.routers.consents.get_consent_service"
    ) as mock_dep:
        mock_service = AsyncMock()
        mock_service.create_consent.return_value = mock_response
        mock_dep.return_value = mock_service

        resp = await async_client.post(
            "/api/v1/consents",
            json={
                "customer_id": "cust-001",
                "consent_type": "MARKETING",
                "channel": "EMAIL",
                "customer_email": "test@example.com",
                "consent_text": "Do you agree?",
            },
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["consent_id"] == "new-id"
    assert data["status"] == "PENDING"


@pytest.mark.asyncio
async def test_list_consents(async_client: AsyncClient) -> None:
    """GET /api/v1/consents returns paginated list."""
    mock_result = PaginatedConsentsResponse(items=[], count=0, next_token=None)

    with patch(
        "consent_api.routers.consents.get_consent_service"
    ) as mock_dep:
        mock_service = AsyncMock()
        mock_service.list_consents.return_value = mock_result
        mock_dep.return_value = mock_service

        resp = await async_client.get("/api/v1/consents")

    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_get_consent(
    async_client: AsyncClient,
    sample_consent_record: ConsentRecord,
) -> None:
    """GET /api/v1/consents/{id} returns the consent record."""
    with patch(
        "consent_api.routers.consents.get_consent_service"
    ) as mock_dep:
        mock_service = AsyncMock()
        mock_service.get_consent.return_value = sample_consent_record
        mock_dep.return_value = mock_service

        resp = await async_client.get(
            f"/api/v1/consents/{sample_consent_record.consent_id}"
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["consent_id"] == sample_consent_record.consent_id


@pytest.mark.asyncio
async def test_revoke_consent(
    async_client: AsyncClient,
    sample_consent_record: ConsentRecord,
) -> None:
    """DELETE /api/v1/consents/{id} revokes the consent."""
    revoked = sample_consent_record.model_copy(
        update={"status": ConsentStatus.REVOKED}
    )

    with patch(
        "consent_api.routers.consents.get_consent_service"
    ) as mock_dep:
        mock_service = AsyncMock()
        mock_service.revoke_consent.return_value = revoked
        mock_dep.return_value = mock_service

        resp = await async_client.delete(
            f"/api/v1/consents/{sample_consent_record.consent_id}"
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "REVOKED"


@pytest.mark.asyncio
async def test_get_consent_history(async_client: AsyncClient) -> None:
    """GET /api/v1/consents/{id}/history returns audit trail."""
    history_entries = [
        {"action": "CREATED", "timestamp": "2025-01-01T00:00:00"},
        {"action": "GRANTED", "timestamp": "2025-01-01T01:00:00"},
    ]

    with patch(
        "consent_api.routers.consents.get_consent_service"
    ) as mock_dep:
        mock_service = AsyncMock()
        mock_service.get_history.return_value = history_entries
        mock_dep.return_value = mock_service

        resp = await async_client.get("/api/v1/consents/test-id/history")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["action"] == "CREATED"


@pytest.mark.asyncio
async def test_create_consent_paused(async_client: AsyncClient) -> None:
    """POST /api/v1/consents returns 503 when collection is paused."""
    with patch("consent_api.routers.consents.is_paused", return_value=True), patch(
        "consent_api.routers.consents.get_pause_reason",
        return_value="Incident detected",
    ):
        resp = await async_client.post(
            "/api/v1/consents",
            json={
                "customer_id": "cust-001",
                "consent_type": "MARKETING",
                "channel": "EMAIL",
                "customer_email": "test@example.com",
                "consent_text": "Do you agree?",
            },
        )

    assert resp.status_code == 503
    assert "paused" in resp.json()["detail"].lower()
