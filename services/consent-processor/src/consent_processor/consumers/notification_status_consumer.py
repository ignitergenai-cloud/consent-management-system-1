"""SQS consumer for notification delivery status events.

Listens on the notification-status queue and delegates incoming
``NotificationSent`` / ``NotificationFailed`` events to the
:class:`ConsentWorkflow` so that consent records can be transitioned
accordingly.
"""

from __future__ import annotations

import structlog

from cms_shared.aws.sqs import SQSConsumer

from consent_processor.config import ConsentProcessorSettings
from consent_processor.services.consent_workflow import ConsentWorkflow

logger = structlog.get_logger()


class NotificationStatusConsumer(SQSConsumer):
    """Routes notification status events to the consent workflow.

    Subscribes to the SQS queue that receives delivery-status updates
    from the notification service and delegates each event to the
    appropriate :class:`ConsentWorkflow` handler.
    """

    def __init__(self, settings: ConsentProcessorSettings, workflow: ConsentWorkflow) -> None:
        super().__init__(
            queue_url=settings.notification_status_queue_url,
            settings=settings,
        )
        self._workflow = workflow

    async def handle_message(self, event: dict) -> None:
        """Route notification status events to workflow handlers.

        Recognised event types:

        * ``NotificationSent`` -- the notification was successfully
          dispatched; the consent is transitioned to SENT.
        * ``NotificationFailed`` -- delivery failed; the workflow decides
          whether to retry or mark the consent as FAILED.

        Args:
            event: The parsed event dict (SNS envelope already unwrapped).
        """
        event_type = event.get("event_type", "")
        consent_id = event.get("payload", {}).get("consent_id", "unknown")

        logger.info(
            "notification_status_received",
            event_type=event_type,
            consent_id=consent_id,
        )

        if event_type == "NotificationSent":
            await self._workflow.process_notification_sent(event)
        elif event_type == "NotificationFailed":
            await self._workflow.process_notification_failed(event)
        else:
            logger.warning(
                "unknown_notification_event",
                event_type=event_type,
                consent_id=consent_id,
            )
