"""Pytest fixtures for the Notification Service tests."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from notification_service.config import NotificationServiceSettings
from notification_service.services.template_engine import TemplateEngine


@pytest.fixture
def mock_settings() -> NotificationServiceSettings:
    """Create a mock NotificationServiceSettings instance for testing.

    Returns:
        A settings instance configured with test defaults.
    """
    return NotificationServiceSettings(
        aws_endpoint_url="http://localhost:4566",
        aws_region="us-east-1",
        dynamodb_table_name="cms-consents-test",
        notification_sent_topic_arn="arn:aws:sns:us-east-1:000000000000:notification-sent",
        notification_queue_url="http://localhost:4566/000000000000/notification-queue",
        from_email="test@consent.example.com",
        service_name="notification-service-test",
        service_port=8002,
        sms_sender_id="CMS-TEST",
    )


@pytest.fixture
def mock_dynamodb() -> AsyncMock:
    """Create a mock DynamoDBManager for testing.

    Returns:
        An AsyncMock mimicking the DynamoDBManager interface with a
        mock table property supporting put_item, get_item, and load.
    """
    db = AsyncMock()
    db.table = AsyncMock()
    db.table.put_item = AsyncMock(return_value={})
    db.table.get_item = AsyncMock(return_value={})
    db.table.load = AsyncMock()
    db.startup = AsyncMock()
    db.shutdown = AsyncMock()
    return db


@pytest.fixture
def mock_sns() -> AsyncMock:
    """Create a mock SNSPublisher for testing.

    Returns:
        An AsyncMock mimicking the SNSPublisher interface with publish_sms
        and publish_event methods.
    """
    sns = AsyncMock()
    sns.publish_sms = AsyncMock(return_value="sms-message-id-123")
    sns.publish_event = AsyncMock(return_value="event-message-id-123")
    sns.startup = AsyncMock()
    sns.shutdown = AsyncMock()
    return sns


@pytest.fixture
def mock_ses() -> AsyncMock:
    """Create a mock SESClient for testing.

    Returns:
        An AsyncMock mimicking the SESClient interface with a send_email method.
    """
    ses = AsyncMock()
    ses.send_email = AsyncMock(return_value="ses-message-id-456")
    ses.startup = AsyncMock()
    ses.shutdown = AsyncMock()
    return ses


@pytest.fixture
def template_engine() -> TemplateEngine:
    """Create a real TemplateEngine instance for testing.

    Returns:
        A TemplateEngine instance configured with the actual template files.
    """
    return TemplateEngine()


@pytest.fixture
def mock_template_engine() -> MagicMock:
    """Create a mock TemplateEngine for testing.

    Returns:
        A MagicMock mimicking the TemplateEngine interface with render methods
        returning predictable test content.
    """
    engine = MagicMock(spec=TemplateEngine)
    engine.render_sms.return_value = "Test SMS message content"
    engine.render_email_html.return_value = "<html><body>Test HTML email</body></html>"
    engine.render_email_text.return_value = "Test plain text email"
    return engine


@pytest.fixture
def sample_sms_event() -> dict:
    """Create a sample SMS SendNotification event for testing.

    Returns:
        A dictionary representing a SendNotification event for the SMS channel.
    """
    return {
        "version": "1.0",
        "event_id": "evt-001",
        "event_type": "SendNotification",
        "source": "consent-service",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correlation_id": "corr-001",
        "payload": {
            "consent_id": "consent-123",
            "channel": "SMS",
            "recipient": "+15551234567",
            "template_id": "consent_request",
            "template_vars": {
                "company_name": "TestCorp",
                "customer_name": "Jane Doe",
                "consent_url": "https://consent.example.com/grant/consent-123",
            },
        },
    }


@pytest.fixture
def sample_email_event() -> dict:
    """Create a sample EMAIL SendNotification event for testing.

    Returns:
        A dictionary representing a SendNotification event for the EMAIL channel.
    """
    return {
        "version": "1.0",
        "event_id": "evt-002",
        "event_type": "SendNotification",
        "source": "consent-service",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correlation_id": "corr-002",
        "payload": {
            "consent_id": "consent-456",
            "channel": "EMAIL",
            "recipient": "jane.doe@example.com",
            "template_id": "consent_request",
            "template_vars": {
                "company_name": "TestCorp",
                "customer_name": "Jane Doe",
                "consent_text": "We would like to use your data for marketing purposes.",
                "consent_url": "https://consent.example.com/grant/consent-456",
                "deny_url": "https://consent.example.com/deny/consent-456",
                "expires_at": "2026-09-30T23:59:59Z",
            },
        },
    }
