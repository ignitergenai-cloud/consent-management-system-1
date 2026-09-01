"""SQS consumer for consent lifecycle events.

Listens on the consent-created queue and routes incoming events to the
appropriate :class:`ConsentWorkflow` handler based on ``event_type``.
"""

from __future__ import annotations

import structlog

from cms_shared.aws.sqs import SQSConsumer

from consent_processor.config import ConsentProcessorSettings
from consent_processor.services.consent_workflow import ConsentWorkflow

logger = structlog.get_logger()


class ConsentEventsConsumer(SQSConsumer):
    """Routes consent domain events to workflow handlers.

    Subscribes to the SQS queue that receives ``ConsentCreated`` /
    ``ConsentRequested`` events (published by the consent-api service)
    and delegates processing to the :class:`ConsentWorkflow`.
    """

    def __init__(self, settings: ConsentProcessorSettings, workflow: ConsentWorkflow) -> None:
        super().__init__(
            queue_url=settings.consent_created_queue_url,
            settings=settings,
        )
        self._workflow = workflow

    async def handle_message(self, event: dict) -> None:
        """Route consent events to appropriate workflow handlers.

        Recognised event types:

        * ``ConsentRequested`` / ``ConsentCreated`` -- triggers notification
          dispatch via the workflow.
        * ``ConsentGranted`` / ``ConsentDenied`` -- logged for observability
          (state changes are handled by the consent-api).

        Args:
            event: The parsed event dict (SNS envelope already unwrapped by
                the base :class:`SQSConsumer`).
        """
        event_type = event.get("event_type", "")
        consent_id = event.get("payload", {}).get("consent_id", "unknown")

        logger.info(
            "consent_event_received",
            event_type=event_type,
            consent_id=consent_id,
        )

        if event_type in ("ConsentRequested", "ConsentCreated"):
            await self._workflow.process_consent_requested(event)
        elif event_type == "ConsentGranted":
            logger.info("consent_granted_received", consent_id=consent_id)
        elif event_type == "ConsentDenied":
            logger.info("consent_denied_received", consent_id=consent_id)
        else:
            logger.warning("unknown_event_type", event_type=event_type, consent_id=consent_id)
