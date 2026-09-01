"""Shared pytest fixtures for the Consent API test suite."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from cms_shared.models.consent import (
    ConsentChannel,
    ConsentRecord,
    ConsentStatus,
    ConsentType,
    CreateConsentRequest,
)

from consent_api.config import ConsentApiSettings


@pytest.fixture
def settings() -> ConsentApiSettings:
    """Return a test-configured settings instance."""
    return ConsentApiSettings(
        aws_endpoint_url="http://localhost:4566",
        dynamodb_table_name="cms-consents-test",
    )


@pytest.fixture
def mock_dynamo_manager() -> MagicMock:
    """Return a mocked DynamoDBManager with an async table stub."""
    manager = MagicMock()
    manager.table = MagicMock()
    manager.startup = AsyncMock()
    manager.shutdown = AsyncMock()
    return manager


@pytest.fixture
def mock_sns_publisher() -> MagicMock:
    """Return a mocked SNSPublisher."""
    publisher = MagicMock()
    publisher.startup = AsyncMock()
    publisher.shutdown = AsyncMock()
    publisher.publish_event = AsyncMock(return_value="mock-message-id")
    return publisher


@pytest.fixture
def sample_consent_record() -> ConsentRecord:
    """Return a representative ConsentRecord for testing."""
    now = datetime.now(timezone.utc)
    return ConsentRecord(
        consent_id="test-consent-001",
        customer_id="customer-001",
        consent_type=ConsentType.MARKETING,
        channel=ConsentChannel.EMAIL,
        status=ConsentStatus.PENDING,
        message_template_id="default",
        customer_email="user@example.com",
        consent_text="Do you agree to receive marketing emails?",
        response_token="test-token-abc123",
        expires_at=now + timedelta(hours=72),
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def sample_create_request() -> CreateConsentRequest:
    """Return a sample CreateConsentRequest."""
    return CreateConsentRequest(
        customer_id="customer-001",
        consent_type=ConsentType.MARKETING,
        channel=ConsentChannel.EMAIL,
        customer_email="user@example.com",
        consent_text="Do you agree to receive marketing emails?",
    )


@pytest_asyncio.fixture
async def async_client(
    mock_dynamo_manager: MagicMock,
    mock_sns_publisher: MagicMock,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an httpx AsyncClient wired to the FastAPI app with mocked deps."""
    # Patch lifespan so it does not try to connect to real AWS services
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _test_lifespan(app: Any):
        app.state.settings = ConsentApiSettings(
            aws_endpoint_url="http://localhost:4566",
        )
        app.state.dynamo_manager = mock_dynamo_manager
        app.state.sns_publisher = mock_sns_publisher
        app.state.commands_consumer = MagicMock()
        yield

    with patch("consent_api.main.lifespan", _test_lifespan):
        from consent_api.main import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client
