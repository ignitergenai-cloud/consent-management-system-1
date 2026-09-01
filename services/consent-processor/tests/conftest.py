"""Shared pytest fixtures for the Consent Processor test suite."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from cms_shared.models.consent import (
    ConsentChannel,
    ConsentRecord,
    ConsentStatus,
    ConsentType,
)
from cms_shared.utils.serialization import to_dynamodb_item

from consent_processor.config import ConsentProcessorSettings
from consent_processor.services.consent_workflow import ConsentWorkflow
from consent_processor.services.expiry_checker import ExpiryChecker
from consent_processor.services.notification_orchestrator import NotificationOrchestrator


# ── Settings ────────────────────────────────────────────────────────────


@pytest.fixture
def settings() -> ConsentProcessorSettings:
    """Return test settings with sensible defaults."""
    return ConsentProcessorSettings(
        aws_endpoint_url="http://localhost:4566",
        aws_region="us-east-1",
        dynamodb_table_name="cms-consents-test",
        consent_expiry_check_interval=5,
        max_notification_retries=3,
    )


# ── Mock AWS clients ───────────────────────────────────────────────────


@pytest.fixture
def mock_dynamodb_table() -> MagicMock:
    """Return a mock DynamoDB table with async methods."""
    table = MagicMock()
    table.get_item = AsyncMock(return_value={"Item": None})
    table.put_item = AsyncMock(return_value={})
    table.update_item = AsyncMock(return_value={"Attributes": {}})
    table.scan = AsyncMock(return_value={"Items": []})
    table.query = AsyncMock(return_value={"Items": []})
    return table


@pytest.fixture
def mock_db(mock_dynamodb_table: MagicMock) -> MagicMock:
    """Return a mock DynamoDBManager whose .table returns the mock table."""
    db = MagicMock()
    type(db).table = property(lambda self: mock_dynamodb_table)
    db.startup = AsyncMock()
    db.shutdown = AsyncMock()
    return db


@pytest.fixture
def mock_sns() -> MagicMock:
    """Return a mock SNSPublisher."""
    sns = MagicMock()
    sns.publish_event = AsyncMock(return_value="mock-message-id")
    sns.publish_sms = AsyncMock(return_value="mock-sms-id")
    sns.startup = AsyncMock()
    sns.shutdown = AsyncMock()
    return sns


# ── Domain services ────────────────────────────────────────────────────


@pytest.fixture
def notification_orchestrator(mock_sns: MagicMock, settings: ConsentProcessorSettings) -> NotificationOrchestrator:
    """Return a NotificationOrchestrator wired to mock dependencies."""
    return NotificationOrchestrator(sns=mock_sns, settings=settings)


@pytest.fixture
def mock_notification_orchestrator() -> MagicMock:
    """Return a fully-mocked NotificationOrchestrator."""
    orch = MagicMock(spec=NotificationOrchestrator)
    orch.request_notification = AsyncMock(return_value="mock-message-id")
    orch.handle_notification_result = AsyncMock(return_value={
        "consent_id": "test-id",
        "status": "sent",
        "retry_count": 0,
        "error_message": None,
    })
    return orch


@pytest.fixture
def workflow(
    mock_db: MagicMock,
    mock_sns: MagicMock,
    mock_notification_orchestrator: MagicMock,
    settings: ConsentProcessorSettings,
) -> ConsentWorkflow:
    """Return a ConsentWorkflow wired to mock dependencies."""
    return ConsentWorkflow(
        db=mock_db,
        sns=mock_sns,
        notification_orchestrator=mock_notification_orchestrator,
        settings=settings,
    )


@pytest.fixture
def expiry_checker(
    mock_db: MagicMock,
    mock_sns: MagicMock,
    settings: ConsentProcessorSettings,
) -> ExpiryChecker:
    """Return an ExpiryChecker wired to mock dependencies."""
    return ExpiryChecker(db=mock_db, sns=mock_sns, settings=settings)


# ── Sample data ─────────────────────────────────────────────────────────


@pytest.fixture
def sample_consent() -> ConsentRecord:
    """Return a sample ConsentRecord in PENDING status."""
    return ConsentRecord(
        consent_id="test-consent-001",
        customer_id="customer-123",
        consent_type=ConsentType.MARKETING,
        channel=ConsentChannel.EMAIL,
        status=ConsentStatus.PENDING,
        message_template_id="default",
        customer_email="customer@example.com",
        consent_text="I agree to receive marketing emails.",
        expires_at=datetime.utcnow() + timedelta(hours=72),
    )


@pytest.fixture
def sample_consent_sms() -> ConsentRecord:
    """Return a sample ConsentRecord using the SMS channel."""
    return ConsentRecord(
        consent_id="test-consent-002",
        customer_id="customer-456",
        consent_type=ConsentType.DATA_PROCESSING,
        channel=ConsentChannel.SMS,
        status=ConsentStatus.PENDING,
        message_template_id="sms-default",
        customer_phone="+15555555555",
        consent_text="I agree to data processing.",
        expires_at=datetime.utcnow() + timedelta(hours=48),
    )


@pytest.fixture
def expired_consent() -> ConsentRecord:
    """Return a ConsentRecord whose expiry date is in the past."""
    return ConsentRecord(
        consent_id="test-consent-expired",
        customer_id="customer-789",
        consent_type=ConsentType.PRIVACY_POLICY,
        channel=ConsentChannel.EMAIL,
        status=ConsentStatus.PENDING,
        message_template_id="default",
        customer_email="expired@example.com",
        consent_text="Privacy policy consent.",
        expires_at=datetime.utcnow() - timedelta(hours=1),
    )


def make_dynamodb_consent_item(consent: ConsentRecord) -> dict:
    """Convert a ConsentRecord to a DynamoDB item dict with PK/SK.

    Useful for stubbing ``table.get_item`` return values in tests.
    """
    item = to_dynamodb_item(consent)
    item["PK"] = f"CONSENT#{consent.consent_id}"
    item["SK"] = f"CONSENT#{consent.consent_id}"
    return item
