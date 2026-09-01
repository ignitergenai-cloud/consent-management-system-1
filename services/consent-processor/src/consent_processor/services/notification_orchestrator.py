"""Notification orchestration for consent requests.

Builds and publishes notification command events so that the notification
service picks them up and delivers SMS or email messages to customers.
"""

from __future__ import annotations

import structlog

from cms_shared.aws.sns import SNSPublisher
from cms_shared.models.consent import ConsentChannel, ConsentRecord
from cms_shared.models.events import create_event

from consent_processor.config import ConsentProcessorSettings

logger = structlog.get_logger()


class NotificationOrchestrator:
    """Orchestrates notification sending with retry logic.

    Determines the correct recipient and channel for a consent record,
    assembles template variables, and publishes a ``SendNotification``
    command event to the notification SNS topic.
    """

    def __init__(self, sns: SNSPublisher, settings: ConsentProcessorSettings) -> None:
        self._sns = sns
        self._settings = settings

    async def request_notification(self, consent: ConsentRecord, retry_count: int = 0) -> str:
        """Create and publish a SendNotification command event.

        Args:
            consent: The consent record that requires a notification.
            retry_count: How many times this notification has already been
                attempted.  Passed through so the notification service and
                downstream consumers can enforce retry limits.

        Returns:
            The SNS message ID of the published event.
        """
        if consent.channel == ConsentChannel.SMS:
            recipient = consent.customer_phone or ""
        else:
            recipient = consent.customer_email or ""

        if not recipient:
            logger.error(
                "notification_recipient_missing",
                consent_id=consent.consent_id,
                channel=consent.channel.value,
            )
            raise ValueError(
                f"No recipient for channel {consent.channel.value} on consent {consent.consent_id}"
            )

        template_vars = {
            "customer_id": consent.customer_id,
            "consent_id": consent.consent_id,
            "consent_text": consent.consent_text,
            "consent_type": consent.consent_type.value,
            "response_token": consent.response_token,
            "expires_at": consent.expires_at.isoformat(),
            "company_name": "Consent Management System",
        }

        payload = {
            "consent_id": consent.consent_id,
            "channel": consent.channel.value,
            "recipient": recipient,
            "template_id": consent.message_template_id,
            "template_vars": template_vars,
            "retry_count": retry_count,
        }

        event = create_event(
            event_type="SendNotification",
            source="consent-processor",
            payload=payload,
        )

        message_id = await self._sns.publish_event(
            topic_arn=self._settings.notification_sent_topic_arn,
            event=event,
        )

        logger.info(
            "notification_requested",
            consent_id=consent.consent_id,
            channel=consent.channel.value,
            recipient=recipient,
            retry_count=retry_count,
            message_id=message_id,
        )

        return message_id

    async def handle_notification_result(self, event: dict) -> dict:
        """Parse a notification result event into a structured dictionary.

        Args:
            event: The raw event dict from the notification status queue.

        Returns:
            A dictionary with ``consent_id``, ``status``, ``retry_count``,
            and ``error_message`` keys.
        """
        payload = event.get("payload", {})
        result = {
            "consent_id": payload.get("consent_id", ""),
            "status": payload.get("status", ""),
            "retry_count": payload.get("retry_count", 0),
            "error_message": payload.get("error_message"),
        }

        logger.info(
            "notification_result_received",
            consent_id=result["consent_id"],
            status=result["status"],
            retry_count=result["retry_count"],
        )

        return result
