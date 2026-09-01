"""Translates MIMS commands into CMS internal command events."""

from __future__ import annotations

from typing import Any

import structlog

from cms_shared.aws.sns import SNSPublisher
from cms_shared.models.events import create_event

from incident_bridge.services.event_transformer import EventTransformer

logger = structlog.get_logger(__name__)


class CommandTranslator:
    """Translates inbound MIMS commands and publishes them as CMS events.

    Uses :class:`EventTransformer` to map MIMS command payloads to the
    internal CMS event format, then publishes them to the internal commands
    SNS topic for consumption by the consent-api service.

    Args:
        sns_publisher: An initialised :class:`SNSPublisher`.
        internal_commands_topic_arn: The ARN of the internal commands SNS
            topic.
        transformer: The :class:`EventTransformer` used to convert MIMS
            commands into CMS payloads.
    """

    def __init__(
        self,
        sns_publisher: SNSPublisher,
        internal_commands_topic_arn: str,
        transformer: EventTransformer,
    ) -> None:
        self._sns = sns_publisher
        self._topic_arn = internal_commands_topic_arn
        self._transformer = transformer

    async def translate_and_publish(self, mims_command: dict[str, Any]) -> str | None:
        """Translate a MIMS command and publish the resulting CMS event.

        The MIMS ``command_type`` is mapped to a CMS event type via
        :meth:`EventTransformer.get_cms_event_type`.  If the command type is
        not recognised, a warning is logged and ``None`` is returned.

        Args:
            mims_command: Dictionary with at least ``command_type`` and
                ``incident_id``.

        Returns:
            The SNS message ID on success, or ``None`` if the command type
            is unknown.
        """
        event_type = self._transformer.get_cms_event_type(mims_command)

        if event_type == "UnknownCommand":
            logger.warning(
                "skipping_unknown_mims_command",
                command_type=mims_command.get("command_type"),
                incident_id=mims_command.get("incident_id"),
            )
            return None

        payload = self._transformer.mims_to_cms_command(mims_command)

        event = create_event(
            event_type=event_type,
            source="incident-bridge",
            payload=payload,
        )

        message_id = await self._sns.publish_event(self._topic_arn, event)

        logger.info(
            "cms_command_published",
            event_type=event_type,
            incident_id=mims_command.get("incident_id"),
            message_id=message_id,
        )
        return message_id
