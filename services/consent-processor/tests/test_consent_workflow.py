"""Tests for the ConsentWorkflow state machine and event handlers."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from cms_shared.models.consent import (
    ConsentChannel,
    ConsentRecord,
    ConsentStatus,
    ConsentType,
)
from cms_shared.utils.serialization import to_dynamodb_item

from consent_processor.services.consent_workflow import ConsentWorkflow

# Re-use fixtures from conftest (workflow, mock_db, mock_sns, etc.)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db_item(consent: ConsentRecord) -> dict:
    """Build a DynamoDB item dict suitable for stubbing table.get_item."""
    item = to_dynamodb_item(consent)
    item["PK"] = f"CONSENT#{consent.consent_id}"
    item["SK"] = f"CONSENT#{consent.consent_id}"
    return item


def _consent(
    status: ConsentStatus = ConsentStatus.PENDING,
    consent_id: str = "c-001",
    **overrides,
) -> ConsentRecord:
    """Create a minimal ConsentRecord with sensible defaults."""
    defaults = dict(
        consent_id=consent_id,
        customer_id="cust-1",
        consent_type=ConsentType.MARKETING,
        channel=ConsentChannel.EMAIL,
        status=status,
        message_template_id="default",
        customer_email="user@example.com",
        consent_text="I consent.",
        expires_at=datetime.utcnow() + timedelta(hours=72),
    )
    defaults.update(overrides)
    return ConsentRecord(**defaults)


# ---------------------------------------------------------------------------
# Valid transitions
# ---------------------------------------------------------------------------


class TestValidTransitions:
    """Verify that every legal status transition succeeds."""

    CASES = [
        (ConsentStatus.PENDING, ConsentStatus.SENT),
        (ConsentStatus.PENDING, ConsentStatus.FAILED),
        (ConsentStatus.PENDING, ConsentStatus.EXPIRED),
        (ConsentStatus.SENT, ConsentStatus.DELIVERED),
        (ConsentStatus.SENT, ConsentStatus.FAILED),
        (ConsentStatus.SENT, ConsentStatus.EXPIRED),
        (ConsentStatus.DELIVERED, ConsentStatus.GRANTED),
        (ConsentStatus.DELIVERED, ConsentStatus.DENIED),
        (ConsentStatus.DELIVERED, ConsentStatus.EXPIRED),
        (ConsentStatus.GRANTED, ConsentStatus.REVOKED),
        (ConsentStatus.FAILED, ConsentStatus.PENDING),
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("from_status,to_status", CASES)
    async def test_valid_transition(
        self,
        from_status: ConsentStatus,
        to_status: ConsentStatus,
        workflow: ConsentWorkflow,
        mock_dynamodb_table: MagicMock,
    ) -> None:
        """The transition should succeed and update DynamoDB."""
        consent = _consent(status=from_status)
        db_item = _make_db_item(consent)

        mock_dynamodb_table.get_item = AsyncMock(return_value={"Item": db_item})

        # update_item should return the updated attributes
        updated_item = dict(db_item)
        updated_item["status"] = to_status.value
        mock_dynamodb_table.update_item = AsyncMock(
            return_value={"Attributes": updated_item}
        )

        result = await workflow.transition(consent.consent_id, to_status)

        assert result.status == to_status
        mock_dynamodb_table.update_item.assert_called_once()


# ---------------------------------------------------------------------------
# Invalid transitions
# ---------------------------------------------------------------------------


class TestInvalidTransitions:
    """Verify that illegal status transitions are rejected."""

    CASES = [
        (ConsentStatus.DENIED, ConsentStatus.GRANTED),
        (ConsentStatus.EXPIRED, ConsentStatus.SENT),
        (ConsentStatus.REVOKED, ConsentStatus.GRANTED),
        (ConsentStatus.GRANTED, ConsentStatus.DENIED),
        (ConsentStatus.PENDING, ConsentStatus.GRANTED),
        (ConsentStatus.SENT, ConsentStatus.PENDING),
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("from_status,to_status", CASES)
    async def test_invalid_transition_raises(
        self,
        from_status: ConsentStatus,
        to_status: ConsentStatus,
        workflow: ConsentWorkflow,
        mock_dynamodb_table: MagicMock,
    ) -> None:
        """A ValueError should be raised for disallowed transitions."""
        consent = _consent(status=from_status)
        db_item = _make_db_item(consent)
        mock_dynamodb_table.get_item = AsyncMock(return_value={"Item": db_item})

        with pytest.raises(ValueError, match="Invalid transition"):
            await workflow.transition(consent.consent_id, to_status)

        mock_dynamodb_table.update_item.assert_not_called()


# ---------------------------------------------------------------------------
# Missing consent
# ---------------------------------------------------------------------------


class TestMissingConsent:
    """Verify behaviour when the consent record does not exist."""

    @pytest.mark.asyncio
    async def test_transition_missing_consent(
        self,
        workflow: ConsentWorkflow,
        mock_dynamodb_table: MagicMock,
    ) -> None:
        """A ValueError should be raised when the consent is not found."""
        mock_dynamodb_table.get_item = AsyncMock(return_value={})

        with pytest.raises(ValueError, match="not found"):
            await workflow.transition("nonexistent", ConsentStatus.SENT)


# ---------------------------------------------------------------------------
# process_consent_requested
# ---------------------------------------------------------------------------


class TestProcessConsentRequested:
    """Verify the ConsentRequested event handler."""

    @pytest.mark.asyncio
    async def test_calls_notification_orchestrator(
        self,
        workflow: ConsentWorkflow,
        mock_dynamodb_table: MagicMock,
        mock_notification_orchestrator: MagicMock,
    ) -> None:
        """The handler should fetch the consent and request a notification."""
        consent = _consent()
        db_item = _make_db_item(consent)
        mock_dynamodb_table.get_item = AsyncMock(return_value={"Item": db_item})

        event = {
            "event_type": "ConsentRequested",
            "source": "consent-api",
            "correlation_id": "corr-001",
            "payload": {"consent_id": consent.consent_id},
        }

        await workflow.process_consent_requested(event)

        mock_notification_orchestrator.request_notification.assert_called_once()
        call_args = mock_notification_orchestrator.request_notification.call_args
        assert call_args[0][0].consent_id == consent.consent_id

    @pytest.mark.asyncio
    async def test_missing_consent_raises(
        self,
        workflow: ConsentWorkflow,
        mock_dynamodb_table: MagicMock,
    ) -> None:
        """Processing should propagate the error when the consent is missing."""
        mock_dynamodb_table.get_item = AsyncMock(return_value={})

        event = {
            "event_type": "ConsentRequested",
            "payload": {"consent_id": "missing"},
        }

        with pytest.raises(ValueError, match="not found"):
            await workflow.process_consent_requested(event)


# ---------------------------------------------------------------------------
# process_notification_sent
# ---------------------------------------------------------------------------


class TestProcessNotificationSent:
    """Verify the NotificationSent event handler."""

    @pytest.mark.asyncio
    async def test_transitions_to_sent(
        self,
        workflow: ConsentWorkflow,
        mock_dynamodb_table: MagicMock,
    ) -> None:
        """A PENDING consent should move to SENT."""
        consent = _consent(status=ConsentStatus.PENDING)
        db_item = _make_db_item(consent)
        mock_dynamodb_table.get_item = AsyncMock(return_value={"Item": db_item})

        updated = dict(db_item)
        updated["status"] = ConsentStatus.SENT.value
        mock_dynamodb_table.update_item = AsyncMock(
            return_value={"Attributes": updated}
        )

        event = {
            "event_type": "NotificationSent",
            "payload": {"consent_id": consent.consent_id},
        }

        await workflow.process_notification_sent(event)

        mock_dynamodb_table.update_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_transition_logged_not_raised(
        self,
        workflow: ConsentWorkflow,
        mock_dynamodb_table: MagicMock,
    ) -> None:
        """If the consent is not in PENDING the error is logged, not raised."""
        consent = _consent(status=ConsentStatus.GRANTED)
        db_item = _make_db_item(consent)
        mock_dynamodb_table.get_item = AsyncMock(return_value={"Item": db_item})

        event = {
            "event_type": "NotificationSent",
            "payload": {"consent_id": consent.consent_id},
        }

        # Should not raise -- the handler catches ValueError and logs a warning
        await workflow.process_notification_sent(event)
        mock_dynamodb_table.update_item.assert_not_called()


# ---------------------------------------------------------------------------
# process_notification_failed
# ---------------------------------------------------------------------------


class TestProcessNotificationFailed:
    """Verify the NotificationFailed event handler with retry logic."""

    @pytest.mark.asyncio
    async def test_retries_when_below_max(
        self,
        workflow: ConsentWorkflow,
        mock_dynamodb_table: MagicMock,
        mock_notification_orchestrator: MagicMock,
        settings,
    ) -> None:
        """When retry_count < max, the consent should be retried."""
        consent = _consent(status=ConsentStatus.PENDING)
        db_item = _make_db_item(consent)

        # First call for transition to FAILED, subsequent calls return the item
        mock_dynamodb_table.get_item = AsyncMock(return_value={"Item": db_item})

        failed_item = dict(db_item)
        failed_item["status"] = ConsentStatus.FAILED.value

        pending_item = dict(db_item)
        pending_item["status"] = ConsentStatus.PENDING.value

        mock_dynamodb_table.update_item = AsyncMock(
            side_effect=[
                {"Attributes": failed_item},   # PENDING -> FAILED
                {"Attributes": pending_item},   # FAILED -> PENDING
            ]
        )

        event = {
            "event_type": "NotificationFailed",
            "payload": {
                "consent_id": consent.consent_id,
                "retry_count": 0,
            },
        }

        await workflow.process_notification_failed(event)

        # Should have called request_notification with retry_count=1
        mock_notification_orchestrator.request_notification.assert_called_once()
        call_kwargs = mock_notification_orchestrator.request_notification.call_args
        assert call_kwargs[1]["retry_count"] == 1 or call_kwargs.kwargs.get("retry_count") == 1

    @pytest.mark.asyncio
    async def test_fails_permanently_at_max_retries(
        self,
        workflow: ConsentWorkflow,
        mock_dynamodb_table: MagicMock,
        mock_notification_orchestrator: MagicMock,
        settings,
    ) -> None:
        """When retry_count >= max, the consent should transition to FAILED."""
        consent = _consent(status=ConsentStatus.PENDING)
        db_item = _make_db_item(consent)
        mock_dynamodb_table.get_item = AsyncMock(return_value={"Item": db_item})

        failed_item = dict(db_item)
        failed_item["status"] = ConsentStatus.FAILED.value
        mock_dynamodb_table.update_item = AsyncMock(
            return_value={"Attributes": failed_item}
        )

        event = {
            "event_type": "NotificationFailed",
            "payload": {
                "consent_id": consent.consent_id,
                "retry_count": settings.max_notification_retries,  # at max
            },
        }

        await workflow.process_notification_failed(event)

        mock_dynamodb_table.update_item.assert_called_once()
        mock_notification_orchestrator.request_notification.assert_not_called()
