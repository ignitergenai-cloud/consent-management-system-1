"""SQS consumer for processing notification commands."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from cms_shared.aws.dynamodb import DynamoDBManager
from cms_shared.aws.ses import SESClient
from cms_shared.aws.sns import SNSPublisher
from cms_shared.aws.sqs import SQSConsumer
from cms_shared.models.consent import ConsentChannel
from cms_shared.models.events import create_event
from cms_shared.models.notification import NotificationLog, NotificationStatus
from cms_shared.utils.serialization import to_dynamodb_item

from notification_service.services.email_sender import EmailSender
from notification_service.services.sms_sender import SMSSender
from notification_service.services.template_engine import TemplateEngine

logger = structlog.get_logger(__name__)


class NotificationConsumer(SQSConsumer):
    """Consumes SendNotification commands from SQS and dispatches them.

    Listens on the notification queue for ``SendNotification`` events, renders
    the appropriate template, sends via SMS or Email, logs the result to
    DynamoDB, and publishes a status event back to SNS.
    """

    def __init__(
        self,
        queue_url: str,
        settings: Any,
        db: DynamoDBManager,
        sns: SNSPublisher,
        ses: SESClient,
        template_engine: TemplateEngine,
    ) -> None:
        """Initialize the notification consumer.

        Args:
            queue_url: The SQS queue URL to consume from.
            settings: Service configuration.
            db: DynamoDB manager for persisting notification logs.
            sns: SNS publisher for sending SMS and status events.
            ses: SES client for sending emails.
            template_engine: Jinja2 template engine for rendering messages.
        """
        super().__init__(queue_url=queue_url, settings=settings)
        self._db = db
        self._sns = sns
        self._ses = ses
        self._template_engine = template_engine
        self._sms_sender = SMSSender(sns, settings)
        self._email_sender = EmailSender(ses, settings)

    async def handle_message(self, event: dict) -> None:
        """Process a single notification command event.

        Parses the event payload, renders the template for the appropriate
        channel, sends the notification, persists a log entry, and publishes
        a status event indicating success or failure.

        Args:
            event: The parsed event dict (SNS envelope already unwrapped by
                the base ``SQSConsumer``).
        """
        event_type = event.get("event_type", "")
        payload = event.get("payload", {})
        correlation_id = event.get("correlation_id")
        consent_id = payload.get("consent_id", "unknown")

        log = logger.bind(
            event_type=event_type,
            consent_id=consent_id,
            correlation_id=correlation_id,
        )

        if event_type != "SendNotification":
            await log.awarning("Ignoring unrecognised event type")
            return

        await log.ainfo("Processing SendNotification command")

        channel_str = payload.get("channel", "")
        recipient = payload.get("recipient", "")
        template_id = payload.get("template_id", "consent_request")
        template_vars = payload.get("template_vars", {})

        try:
            channel = ConsentChannel(channel_str)
        except ValueError:
            await log.aerror("Invalid notification channel", channel=channel_str)
            await self._publish_status_event(
                consent_id=consent_id,
                status="NotificationFailed",
                correlation_id=correlation_id,
                error=f"Invalid channel: {channel_str}",
                retry_count=payload.get("retry_count", 0),
            )
            return

        # Attempt to send the notification
        notification_log = NotificationLog(
            consent_id=consent_id,
            channel=channel,
            recipient=recipient,
            template_id=template_id,
            template_vars=template_vars,
            status=NotificationStatus.SENDING,
        )

        try:
            provider_message_id = await self._dispatch(
                channel=channel,
                recipient=recipient,
                template_id=template_id,
                template_vars=template_vars,
            )

            notification_log.status = NotificationStatus.SENT
            notification_log.provider_message_id = provider_message_id
            notification_log.sent_at = datetime.now(timezone.utc)

            await log.ainfo(
                "Notification sent successfully",
                provider_message_id=provider_message_id,
            )

            await self._save_notification_log(notification_log)
            await self._publish_status_event(
                consent_id=consent_id,
                status="NotificationSent",
                correlation_id=correlation_id,
                notification_id=notification_log.notification_id,
                provider_message_id=provider_message_id,
            )

        except Exception as exc:
            notification_log.status = NotificationStatus.FAILED
            notification_log.failed_at = datetime.now(timezone.utc)
            notification_log.error_message = str(exc)

            await log.aerror("Notification sending failed", error=str(exc))

            await self._save_notification_log(notification_log)
            await self._publish_status_event(
                consent_id=consent_id,
                status="NotificationFailed",
                correlation_id=correlation_id,
                error=str(exc),
                notification_id=notification_log.notification_id,
                retry_count=payload.get("retry_count", 0),
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _dispatch(
        self,
        channel: ConsentChannel,
        recipient: str,
        template_id: str,
        template_vars: dict,
    ) -> str:
        """Render and send the notification via the appropriate channel.

        Args:
            channel: SMS or EMAIL.
            recipient: Phone number or email address.
            template_id: Template identifier to render.
            template_vars: Variables to inject into the template.

        Returns:
            The provider message ID from SNS/SES.
        """
        if channel == ConsentChannel.SMS:
            message = self._template_engine.render_sms(template_id, template_vars)
            return await self._sms_sender.send_sms(recipient, message)

        if channel == ConsentChannel.EMAIL:
            html_body = self._template_engine.render_email_html(template_id, template_vars)
            text_body = self._template_engine.render_email_text(template_id, template_vars)
            subject = f"Consent Request - {template_vars.get('company_name', 'CMS')}"
            return await self._email_sender.send_email(
                to=recipient,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )

        raise ValueError(f"Unsupported notification channel: {channel}")

    async def _save_notification_log(self, notification_log: NotificationLog) -> None:
        """Persist a notification log entry to DynamoDB.

        Args:
            notification_log: The notification log record to persist.
        """
        item = to_dynamodb_item(notification_log)
        item["PK"] = f"NOTIFICATION#{notification_log.notification_id}"
        item["SK"] = "METADATA"
        item["GSI1PK"] = f"CONSENT#{notification_log.consent_id}"
        item["GSI1SK"] = notification_log.created_at.isoformat()
        item["GSI2PK"] = f"NOTIF_STATUS#{notification_log.status.value}"
        item["GSI2SK"] = notification_log.created_at.isoformat()

        await self._db.table.put_item(Item=item)
        logger.info(
            "Notification log saved",
            notification_id=notification_log.notification_id,
            status=notification_log.status.value,
        )

    async def _publish_status_event(
        self,
        consent_id: str,
        status: str,
        correlation_id: str | None = None,
        **extra: Any,
    ) -> None:
        """Publish a notification status event to the SNS status topic.

        Args:
            consent_id: The related consent ID.
            status: ``"NotificationSent"`` or ``"NotificationFailed"``.
            correlation_id: Optional correlation ID to thread through.
            **extra: Additional payload fields (e.g. error, notification_id).
        """
        event_payload = {"consent_id": consent_id, **extra}
        event = create_event(
            event_type=status,
            source="notification-service",
            payload=event_payload,
            correlation_id=correlation_id,
        )
        await self._sns.publish_event(
            self._settings.notification_sent_topic_arn,
            event,
        )
