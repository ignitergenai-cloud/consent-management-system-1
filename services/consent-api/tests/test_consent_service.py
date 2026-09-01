"""Tests for ConsentService business logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from cms_shared.models.consent import (
    ConsentChannel,
    ConsentRecord,
    ConsentResponseRequest,
    ConsentStatus,
    ConsentType,
    CreateConsentRequest,
    ListConsentsQuery,
    PaginatedConsentsResponse,
)

from consent_api.config import ConsentApiSettings
from consent_api.repositories.consent_repository import ConsentRepository
from consent_api.services.consent_service import ConsentService


@pytest.fixture
def mock_repo() -> AsyncMock:
    """Return a mocked ConsentRepository."""
    repo = AsyncMock(spec=ConsentRepository)
    return repo


@pytest.fixture
def mock_sns() -> AsyncMock:
    """Return a mocked SNSPublisher."""
    sns = AsyncMock()
    sns.publish_event = AsyncMock(return_value="msg-id")
    return sns


@pytest.fixture
def service(mock_repo: AsyncMock, mock_sns: AsyncMock) -> ConsentService:
    """Return a ConsentService wired with mocks."""
    settings = ConsentApiSettings(aws_endpoint_url="http://localhost:4566")
    return ConsentService(repository=mock_repo, sns_publisher=mock_sns, settings=settings)


@pytest.fixture
def sample_record() -> ConsentRecord:
    """Return a sample ConsentRecord."""
    now = datetime.now(timezone.utc)
    return ConsentRecord(
        consent_id="consent-001",
        customer_id="customer-001",
        consent_type=ConsentType.MARKETING,
        channel=ConsentChannel.EMAIL,
        status=ConsentStatus.PENDING,
        message_template_id="default",
        customer_email="user@example.com",
        consent_text="Do you agree?",
        response_token="token-xyz",
        expires_at=now + timedelta(hours=72),
        created_at=now,
        updated_at=now,
    )


# ------------------------------------------------------------------
# create_consent
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_consent_email(
    service: ConsentService,
    mock_repo: AsyncMock,
    mock_sns: AsyncMock,
) -> None:
    """Creating an EMAIL consent persists, records history, and publishes event."""
    request = CreateConsentRequest(
        customer_id="cust-001",
        consent_type=ConsentType.MARKETING,
        channel=ConsentChannel.EMAIL,
        customer_email="user@example.com",
        consent_text="Do you agree?",
    )

    mock_repo.create_consent.return_value = MagicMock()
    mock_repo.add_history_entry.return_value = None

    result = await service.create_consent(request)

    assert result.consent_id is not None
    assert result.status == ConsentStatus.PENDING
    assert result.response_url.startswith(service._settings.response_base_url)

    mock_repo.create_consent.assert_awaited_once()
    mock_repo.add_history_entry.assert_awaited_once()
    mock_sns.publish_event.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_consent_sms_missing_phone(service: ConsentService) -> None:
    """SMS consent without phone raises ValueError."""
    request = CreateConsentRequest(
        customer_id="cust-001",
        consent_type=ConsentType.MARKETING,
        channel=ConsentChannel.SMS,
        consent_text="Do you agree?",
    )

    with pytest.raises(ValueError, match="customer_phone is required"):
        await service.create_consent(request)


@pytest.mark.asyncio
async def test_create_consent_email_missing_email(service: ConsentService) -> None:
    """EMAIL consent without email raises ValueError."""
    request = CreateConsentRequest(
        customer_id="cust-001",
        consent_type=ConsentType.MARKETING,
        channel=ConsentChannel.EMAIL,
        consent_text="Do you agree?",
    )

    with pytest.raises(ValueError, match="customer_email is required"):
        await service.create_consent(request)


# ------------------------------------------------------------------
# get_consent / list_consents
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_consent(
    service: ConsentService,
    mock_repo: AsyncMock,
    sample_record: ConsentRecord,
) -> None:
    """get_consent delegates to the repository."""
    mock_repo.get_consent.return_value = sample_record
    result = await service.get_consent("consent-001")
    assert result.consent_id == "consent-001"
    mock_repo.get_consent.assert_awaited_once_with("consent-001")


@pytest.mark.asyncio
async def test_list_consents(
    service: ConsentService, mock_repo: AsyncMock
) -> None:
    """list_consents passes query through to the repository."""
    mock_repo.list_consents.return_value = PaginatedConsentsResponse(
        items=[], count=0, next_token=None
    )
    query = ListConsentsQuery(page_size=10)
    result = await service.list_consents(query)
    assert result.count == 0
    mock_repo.list_consents.assert_awaited_once_with(query)


# ------------------------------------------------------------------
# revoke_consent
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_consent(
    service: ConsentService,
    mock_repo: AsyncMock,
    mock_sns: AsyncMock,
    sample_record: ConsentRecord,
) -> None:
    """Revoking a consent updates status, records history, publishes event."""
    revoked = sample_record.model_copy(update={"status": ConsentStatus.REVOKED})
    mock_repo.update_consent.return_value = revoked
    mock_repo.add_history_entry.return_value = None

    result = await service.revoke_consent("consent-001")

    assert result.status == ConsentStatus.REVOKED
    mock_repo.update_consent.assert_awaited_once()
    mock_repo.add_history_entry.assert_awaited_once()
    mock_sns.publish_event.assert_awaited_once()


# ------------------------------------------------------------------
# respond_to_consent
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_respond_grant(
    service: ConsentService,
    mock_repo: AsyncMock,
    mock_sns: AsyncMock,
    sample_record: ConsentRecord,
) -> None:
    """Granting consent updates status and publishes ConsentGranted event."""
    mock_repo.get_consent_by_token.return_value = sample_record
    granted = sample_record.model_copy(update={"status": ConsentStatus.GRANTED})
    mock_repo.update_consent.return_value = granted
    mock_repo.add_history_entry.return_value = None

    response = ConsentResponseRequest(
        granted=True, ip_address="1.2.3.4", user_agent="TestAgent"
    )
    result = await service.respond_to_consent("token-xyz", response)

    assert result.status == ConsentStatus.GRANTED
    mock_sns.publish_event.assert_awaited_once()
    # Verify topic ARN used was the granted one
    call_args = mock_sns.publish_event.call_args
    assert "consent-granted" in call_args[0][0]


@pytest.mark.asyncio
async def test_respond_deny(
    service: ConsentService,
    mock_repo: AsyncMock,
    mock_sns: AsyncMock,
    sample_record: ConsentRecord,
) -> None:
    """Denying consent updates status and publishes ConsentDenied event."""
    mock_repo.get_consent_by_token.return_value = sample_record
    denied = sample_record.model_copy(update={"status": ConsentStatus.DENIED})
    mock_repo.update_consent.return_value = denied
    mock_repo.add_history_entry.return_value = None

    response = ConsentResponseRequest(granted=False)
    result = await service.respond_to_consent("token-xyz", response)

    assert result.status == ConsentStatus.DENIED
    call_args = mock_sns.publish_event.call_args
    assert "consent-denied" in call_args[0][0]


@pytest.mark.asyncio
async def test_respond_already_granted(
    service: ConsentService,
    mock_repo: AsyncMock,
    sample_record: ConsentRecord,
) -> None:
    """Responding to an already-granted consent raises ValueError."""
    already = sample_record.model_copy(update={"status": ConsentStatus.GRANTED})
    mock_repo.get_consent_by_token.return_value = already

    response = ConsentResponseRequest(granted=True)
    with pytest.raises(ValueError, match="already been responded to"):
        await service.respond_to_consent("token-xyz", response)


@pytest.mark.asyncio
async def test_respond_expired(
    service: ConsentService,
    mock_repo: AsyncMock,
    sample_record: ConsentRecord,
) -> None:
    """Responding to an expired consent raises ValueError."""
    expired = sample_record.model_copy(
        update={"expires_at": datetime.now(timezone.utc) - timedelta(hours=1)}
    )
    mock_repo.get_consent_by_token.return_value = expired
    mock_repo.update_consent.return_value = expired

    response = ConsentResponseRequest(granted=True)
    with pytest.raises(ValueError, match="expired"):
        await service.respond_to_consent("token-xyz", response)


# ------------------------------------------------------------------
# bulk_create
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_create(
    service: ConsentService,
    mock_repo: AsyncMock,
    mock_sns: AsyncMock,
) -> None:
    """bulk_create processes each request and returns all responses."""
    mock_repo.create_consent.return_value = MagicMock()
    mock_repo.add_history_entry.return_value = None

    requests = [
        CreateConsentRequest(
            customer_id=f"cust-{i}",
            consent_type=ConsentType.MARKETING,
            channel=ConsentChannel.EMAIL,
            customer_email=f"user{i}@example.com",
            consent_text="Agree?",
        )
        for i in range(3)
    ]

    results = await service.bulk_create(requests)
    assert len(results) == 3
    assert mock_repo.create_consent.await_count == 3


# ------------------------------------------------------------------
# history / analytics
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_history(
    service: ConsentService, mock_repo: AsyncMock
) -> None:
    """get_history delegates to the repository."""
    mock_repo.get_history.return_value = [{"action": "CREATED"}]
    result = await service.get_history("consent-001")
    assert len(result) == 1
    mock_repo.get_history.assert_awaited_once_with("consent-001")


@pytest.mark.asyncio
async def test_get_analytics(
    service: ConsentService, mock_repo: AsyncMock
) -> None:
    """get_analytics returns a populated ConsentAnalytics model."""
    mock_repo.get_analytics.return_value = {
        "total": 100,
        "by_status": {"GRANTED": 60, "DENIED": 20, "PENDING": 20},
        "by_channel": {"EMAIL": 70, "SMS": 30},
        "by_type": {"MARKETING": 100},
        "granted_count": 60,
        "total_response_time": 120.0,
        "response_count": 60,
    }

    result = await service.get_analytics()
    assert result.total_consents == 100
    assert result.grant_rate == 60.0
    assert result.avg_response_time_hours == 2.0
