"""SQS consumer for inbound commands from the MIMS system."""

from __future__ import annotations

from typing import Any

import structlog

from cms_shared.aws.sqs import SQSConsumer

from incident_bridge.config import IncidentBridgeSettings
from incident_bridge.schemas.mims_command import MIMSCommand
from incident_bridge.services.bridge_event_log import BridgeEventLog
from incident_bridge.services.command_translator import CommandTranslator

logger = structlog.get_logger(__name__)


class MIMSCommandsConsumer(SQSConsumer):
    """Consumes MIMS commands and translates them to CMS internal events.

    Listens on the incident-commands SQS queue for ``PAUSE`` and ``RESUME``
    commands from the external MIMS system.  Each command is validated,
    translated to the corresponding CMS event type, and published to the
    internal commands SNS topic via :class:`CommandTranslator`.

    Args:
        queue_url: The SQS queue URL to poll.
        settings: The incident-bridge configuration.
        command_translator: Translator for MIMS-to-CMS command conversion.
        bridge_event_log: Shared in-memory event log.
    """

    def __init__(
        self,
        queue_url: str,
        settings: IncidentBridgeSettings,
        command_translator: CommandTranslator,
        bridge_event_log: BridgeEventLog,
    ) -> None:
        super().__init__(queue_url=queue_url, settings=settings)
        self._translator = command_translator
        self._event_log = bridge_event_log

    async def handle_message(self, event: dict[str, Any]) -> None:
        """Process a single MIMS command message.

        The raw message payload is validated against :class:`MIMSCommand`,
        then forwarded to the :class:`CommandTranslator` for translation
        and publication.

        Args:
            event: The deserialised message dictionary.  If the message
                arrived via an SNS envelope the base class will have
                already unwrapped it.
        """
        # The event may be an EventEnvelope wrapping the command in its
        # payload, or it may be the command dict itself.
        command_data: dict[str, Any] = event.get("payload", event)

        try:
            mims_command = MIMSCommand(**command_data)
        except Exception:
            logger.error(
                "invalid_mims_command",
                raw_data=command_data,
            )
            return

        logger.info(
            "mims_command_received",
            command_type=mims_command.command_type,
            incident_id=mims_command.incident_id,
        )

        result = await self._translator.translate_and_publish(
            mims_command.model_dump()
        )

        if result is not None:
            self._event_log.record(
                direction="inbound",
                event_type=mims_command.command_type,
                incident_id=mims_command.incident_id,
                status="translated",
                details={"message_id": result},
            )
            logger.info(
                "mims_command_processed",
                command_type=mims_command.command_type,
                incident_id=mims_command.incident_id,
                message_id=result,
            )
        else:
            self._event_log.record(
                direction="inbound",
                event_type=mims_command.command_type,
                incident_id=mims_command.incident_id,
                status="skipped",
                details={"reason": "unknown_command_type"},
            )
            logger.warning(
                "mims_command_not_processed",
                command_type=mims_command.command_type,
                incident_id=mims_command.incident_id,
                reason="unknown_command_type",
            )
