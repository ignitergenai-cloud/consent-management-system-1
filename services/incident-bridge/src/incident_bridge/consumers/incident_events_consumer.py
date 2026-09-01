"""SQS consumer for CMS incident events destined for MIMS."""

from __future__ import annotations

from typing import Any

import structlog

from cms_shared.aws.sqs import SQSConsumer

from incident_bridge.config import IncidentBridgeSettings
from incident_bridge.services.bridge_event_log import BridgeEventLog
from incident_bridge.services.event_transformer import EventTransformer
from incident_bridge.services.mims_publisher import MIMSPublisher

logger = structlog.get_logger(__name__)

# CMS event types handled by this consumer
_INCIDENT_DETECTED = "IncidentDetected"
_INCIDENT_ACKNOWLEDGED = "IncidentAcknowledged"
_INCIDENT_RESOLVED = "IncidentResolved"


class IncidentEventsConsumer(SQSConsumer):
    """Consumes CMS incident events and forwards them to MIMS.

    Listens on the incident-bridge SQS queue for ``IncidentDetected``,
    ``IncidentAcknowledged``, and ``IncidentResolved`` events.  Each event
    is transformed into MIMS format via :class:`EventTransformer` and then
    published to the MIMS inbound SNS topic via :class:`MIMSPublisher`.

    Args:
        queue_url: The SQS queue URL to poll.
        settings: The incident-bridge configuration.
        event_transformer: Transformer for CMS-to-MIMS conversion.
        mims_publisher: Publisher targeting the MIMS inbound topic.
        bridge_event_log: Shared in-memory event log.
    """

    def __init__(
        self,
        queue_url: str,
        settings: IncidentBridgeSettings,
        event_transformer: EventTransformer,
        mims_publisher: MIMSPublisher,
        bridge_event_log: BridgeEventLog,
    ) -> None:
        super().__init__(queue_url=queue_url, settings=settings)
        self._transformer = event_transformer
        self._mims_publisher = mims_publisher
        self._event_log = bridge_event_log

    async def handle_message(self, event: dict[str, Any]) -> None:
        """Process a single CMS incident event.

        Dispatches to the appropriate MIMS publish method based on the
        ``event_type`` field.  Unknown event types are logged and skipped.

        Args:
            event: The deserialised CMS event envelope dictionary.
        """
        event_type: str = event.get("event_type", "")
        payload: dict[str, Any] = event.get("payload", {})
        incident_id: str = payload.get("incident_id", "")

        logger.info(
            "incident_event_received",
            event_type=event_type,
            incident_id=incident_id,
        )

        if event_type == _INCIDENT_DETECTED:
            mims_event = self._transformer.cms_to_mims(event)
            message_id = await self._mims_publisher.publish_incident(mims_event)

            self._event_log.record(
                direction="outbound",
                event_type="MIMSIncidentCreated",
                incident_id=incident_id,
                status="published",
                details={"source_event": event_type, "message_id": message_id},
            )

        elif event_type == _INCIDENT_ACKNOWLEDGED:
            mims_event = self._transformer.cms_to_mims(event)
            message_id = await self._mims_publisher.publish_acknowledgement(mims_event)

            self._event_log.record(
                direction="outbound",
                event_type="MIMSIncidentAcknowledged",
                incident_id=incident_id,
                status="published",
                details={"source_event": event_type, "message_id": message_id},
            )

        elif event_type == _INCIDENT_RESOLVED:
            mims_event = self._transformer.cms_to_mims(event)
            message_id = await self._mims_publisher.publish_resolution(mims_event)

            self._event_log.record(
                direction="outbound",
                event_type="MIMSIncidentResolved",
                incident_id=incident_id,
                status="published",
                details={"source_event": event_type, "message_id": message_id},
            )

        else:
            logger.warning(
                "unknown_incident_event_type",
                event_type=event_type,
                incident_id=incident_id,
            )
