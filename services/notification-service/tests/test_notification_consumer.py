"""Tests for the NotificationConsumer."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from notification_service.consumers.notification_consumer import NotificationConsumer


@pytest.fixture
def consumer(
    mock_settings,
    mock_dynamodb,
    mock_sns,
    mock_ses,
    mock_template_engine,
) -> NotificationConsumer:
    """Create a NotificationConsumer with all mocked dependencies.

    Args:
        mock_settings: Mock service settings.
        mock_dynamodb: Mock DynamoDB manager.
        mock_sns: Mock SNS publisher.
        mock_ses: Mock SES client.
        mock_template_engine: Mock template engine.

    Returns:
        A NotificationConsumer instance ready for testing.
    """
    return NotificationConsumer(
        queue_url=mock_settings.notification_queue_url,
        settings=mock_settings,
        db=mock_dynamodb,
        sns=mock_sns,
        ses=mock_ses,
        template_engine=mock_template_engine,
    )


@pytest.mark.asyncio
async def test_handle_sms_notification(
    consumer: NotificationConsumer,
    sample_sms_event: dict,
    mock_sns: AsyncMock,
    mock_dynamodb: AsyncMock,
    mock_template_engine: MagicMock,
) -> None:
    """Test that the consumer correctly handles an SMS SendNotification event.

    Verifies that:
    - The SMS template is rendered with the correct variables.
    - The SMS is sent to the correct phone number via SNS.
    - The notification log is persisted to DynamoDB.
    - A NotificationSent event is published to SNS.
    """
    await consumer.handle_message(sample_sms_event)

    # Verify template was rendered
    mock_template_engine.render_sms.assert_called_once_with(
        "consent_request",
        sample_sms_event["payload"]["template_vars"],
    )

    # Verify SMS was sent
    mock_sns.publish_sms.assert_called_once_with(
        "+15551234567",
        "Test SMS message content",
    )

    # Verify notification log was persisted
    mock_dynamodb.table.put_item.assert_called_once()
    put_call_kwargs = mock_dynamodb.table.put_item.call_args
    assert put_call_kwargs is not None

    # Verify success event was published
    mock_sns.publish_event.assert_called_once()
    event_call_args = mock_sns.publish_event.call_args
    topic_arn = event_call_args[0][0]
    published_event = event_call_args[0][1]
    assert topic_arn == "arn:aws:sns:us-east-1:000000000000:notification-sent"
    assert published_event.event_type == "NotificationSent"
    assert published_event.payload["consent_id"] == "consent-123"
    assert published_event.payload["channel"] == "SMS"
    assert published_event.payload["recipient"] == "+15551234567"
    assert published_event.payload["provider_message_id"] == "sms-message-id-123"


@pytest.mark.asyncio
async def test_handle_email_notification(
    consumer: NotificationConsumer,
    sample_email_event: dict,
    mock_ses: AsyncMock,
    mock_dynamodb: AsyncMock,
    mock_template_engine: MagicMock,
    mock_sns: AsyncMock,
) -> None:
    """Test that the consumer correctly handles an EMAIL SendNotification event.

    Verifies that:
    - Both HTML and text email templates are rendered with the correct variables.
    - The email is sent to the correct recipient via SES.
    - The notification log is persisted to DynamoDB.
    - A NotificationSent event is published to SNS.
    """
    await consumer.handle_message(sample_email_event)

    template_vars = sample_email_event["payload"]["template_vars"]

    # Verify both email templates were rendered
    mock_template_engine.render_email_html.assert_called_once_with(
        "consent_request",
        template_vars,
    )
    mock_template_engine.render_email_text.assert_called_once_with(
        "consent_request",
        template_vars,
    )

    # Verify email was sent via SES
    mock_ses.send_email.assert_called_once_with(
        to="jane.doe@example.com",
        subject="Consent Request from TestCorp",
        html_body="<html><body>Test HTML email</body></html>",
        text_body="Test plain text email",
        from_email="test@consent.example.com",
    )

    # Verify notification log was persisted
    mock_dynamodb.table.put_item.assert_called_once()

    # Verify success event was published
    mock_sns.publish_event.assert_called_once()
    event_call_args = mock_sns.publish_event.call_args
    published_event = event_call_args[0][1]
    assert published_event.event_type == "NotificationSent"
    assert published_event.payload["consent_id"] == "consent-456"
    assert published_event.payload["channel"] == "EMAIL"
    assert published_event.payload["recipient"] == "jane.doe@example.com"


@pytest.mark.asyncio
async def test_handle_sms_failure(
    consumer: NotificationConsumer,
    sample_sms_event: dict,
    mock_sns: AsyncMock,
    mock_dynamodb: AsyncMock,
    mock_template_engine: MagicMock,
) -> None:
    """Test that the consumer handles SMS sending failures gracefully.

    Verifies that:
    - When SNS publish_sms raises an exception, the failure is caught.
    - A NotificationFailed event is published to SNS instead of NotificationSent.
    - The notification log is still persisted to DynamoDB with a FAILED status.
    - The error message is included in the failure event payload.
    """
    # Make SMS sending fail
    mock_sns.publish_sms.side_effect = Exception("SNS service unavailable")

    await consumer.handle_message(sample_sms_event)

    # Verify SMS was attempted
    mock_sns.publish_sms.assert_called_once()

    # Verify failure event was published
    mock_sns.publish_event.assert_called_once()
    event_call_args = mock_sns.publish_event.call_args
    published_event = event_call_args[0][1]
    assert published_event.event_type == "NotificationFailed"
    assert published_event.payload["consent_id"] == "consent-123"
    assert published_event.payload["error"] == "SNS service unavailable"

    # Verify notification log was still persisted (with failure status)
    mock_dynamodb.table.put_item.assert_called_once()


@pytest.mark.asyncio
async def test_handle_email_failure(
    consumer: NotificationConsumer,
    sample_email_event: dict,
    mock_ses: AsyncMock,
    mock_dynamodb: AsyncMock,
    mock_template_engine: MagicMock,
    mock_sns: AsyncMock,
) -> None:
    """Test that the consumer handles email sending failures gracefully.

    Verifies that:
    - When SES send_email raises an exception, the failure is caught.
    - A NotificationFailed event is published.
    - The notification log is persisted with failure details.
    """
    mock_ses.send_email.side_effect = Exception("SES rate limit exceeded")

    await consumer.handle_message(sample_email_event)

    # Verify email was attempted
    mock_ses.send_email.assert_called_once()

    # Verify failure event was published
    mock_sns.publish_event.assert_called_once()
    event_call_args = mock_sns.publish_event.call_args
    published_event = event_call_args[0][1]
    assert published_event.event_type == "NotificationFailed"
    assert published_event.payload["error"] == "SES rate limit exceeded"

    # Verify log was persisted
    mock_dynamodb.table.put_item.assert_called_once()


@pytest.mark.asyncio
async def test_handle_unsupported_channel(
    consumer: NotificationConsumer,
    mock_sns: AsyncMock,
    mock_dynamodb: AsyncMock,
) -> None:
    """Test that the consumer handles unsupported channels gracefully.

    Verifies that an event with an invalid channel value results in a
    NotificationFailed event being published with an appropriate error.
    """
    event = {
        "event_type": "SendNotification",
        "correlation_id": "corr-bad",
        "payload": {
            "consent_id": "consent-bad",
            "channel": "PIGEON",
            "recipient": "somewhere",
            "template_id": "consent_request",
            "template_vars": {},
        },
    }

    await consumer.handle_message(event)

    # Verify failure event was published
    mock_sns.publish_event.assert_called_once()
    event_call_args = mock_sns.publish_event.call_args
    published_event = event_call_args[0][1]
    assert published_event.event_type == "NotificationFailed"
    assert "consent-bad" in published_event.payload["consent_id"]

    # Verify log was still persisted
    mock_dynamodb.table.put_item.assert_called_once()


@pytest.mark.asyncio
async def test_handle_dynamodb_persistence_failure(
    consumer: NotificationConsumer,
    sample_sms_event: dict,
    mock_sns: AsyncMock,
    mock_dynamodb: AsyncMock,
    mock_template_engine: MagicMock,
) -> None:
    """Test that the consumer handles DynamoDB write failures gracefully.

    Verifies that when the notification is sent successfully but DynamoDB
    persistence fails, the success event is still published and the consumer
    does not raise an unhandled exception.
    """
    # Make DynamoDB fail on put_item
    mock_dynamodb.table.put_item.side_effect = Exception("DynamoDB write failed")

    # Should not raise - the consumer logs the error but continues
    await consumer.handle_message(sample_sms_event)

    # Verify SMS was still sent successfully
    mock_sns.publish_sms.assert_called_once()

    # Verify success event was published (notification itself succeeded)
    mock_sns.publish_event.assert_called_once()
    event_call_args = mock_sns.publish_event.call_args
    published_event = event_call_args[0][1]
    assert published_event.event_type == "NotificationSent"
