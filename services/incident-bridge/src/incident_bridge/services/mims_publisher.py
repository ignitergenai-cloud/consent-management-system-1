"""Publisher that forwards transformed incidents to the MIMS inbound SNS topic."""

from __future__ import annotations

from typing import Any

import structlog

from cms_shared.aws.sns import SNSPublisher
from cms_shared.models.events import create_event

logger = structlog.get_logger(__name__)


class MIMSPublisher:
    """Publishes CMS incident events to the external MIMS system via SNS.

    Each ``publish_*`` method wraps the payload in an :class:`EventEnvelope`,
    publishes it to the configured MIMS inbound SNS topic, and logs the
    action via *structlog*.

    Args:
        sns_publisher: An initialised :class:`SNSPublisher`.
        mims_topic_arn: The ARN of the MIMS inbound SNS topic.
    """

    def __init__(self, sns_publisher: SNSPublisher, mims_topic_arn: str) -> None:
        self._sns = sns_publisher
        self._topic_arn = mims_topic_arn

    # ------------------------------------------------------------------
    # Publishing helpers
    # ------------------------------------------------------------------

    async def publish_incident(self, mims_event: dict[str, Any]) -> str:
        """Publish a new incident to MIMS.

        Creates a ``MIMSIncidentCreated`` event envelope and sends it to the
        MIMS inbound topic.

        Args:
            mims_event: The MIMS-formatted incident dictionary.

        Returns:
            The SNS message ID of the published event.
        """
        event = create_event(
            event_type="MIMSIncidentCreated",
            source="incident-bridge",
            payload=mims_event,
            correlation_id=mims_event.get("correlation_id"),
        )
        message_id = await self._sns.publish_event(self._topic_arn, event)

        logger.info(
            "mims_incident_published",
            event_type="MIMSIncidentCreated",
            incident_id=mims_event.get("incident_id"),
            message_id=message_id,
        )
        return message_id

    async def publish_acknowledgement(self, mims_event: dict[str, Any]) -> str:
        """Publish an incident acknowledgement to MIMS.

        Creates a ``MIMSIncidentAcknowledged`` event envelope and sends it
        to the MIMS inbound topic.

        Args:
            mims_event: The MIMS-formatted incident dictionary.

        Returns:
            The SNS message ID of the published event.
        """
        event = create_event(
            event_type="MIMSIncidentAcknowledged",
            source="incident-bridge",
            payload=mims_event,
            correlation_id=mims_event.get("correlation_id"),
        )
        message_id = await self._sns.publish_event(self._topic_arn, event)

        logger.info(
            "mims_acknowledgement_published",
            event_type="MIMSIncidentAcknowledged",
            incident_id=mims_event.get("incident_id"),
            message_id=message_id,
        )
        return message_id

    async def publish_resolution(self, mims_event: dict[str, Any]) -> str:
        """Publish an incident resolution to MIMS.

        Creates a ``MIMSIncidentResolved`` event envelope and sends it to the
        MIMS inbound topic.

        Args:
            mims_event: The MIMS-formatted incident dictionary.

        Returns:
            The SNS message ID of the published event.
        """
        event = create_event(
            event_type="MIMSIncidentResolved",
            source="incident-bridge",
            payload=mims_event,
            correlation_id=mims_event.get("correlation_id"),
        )
        message_id = await self._sns.publish_event(self._topic_arn, event)

        logger.info(
            "mims_resolution_published",
            event_type="MIMSIncidentResolved",
            incident_id=mims_event.get("incident_id"),
            message_id=message_id,
        )
        return message_id
