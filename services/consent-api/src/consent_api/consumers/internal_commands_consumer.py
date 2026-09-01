"""SQS consumer for internal system commands."""

from __future__ import annotations

from typing import Any

import structlog

from cms_shared.aws.sqs import SQSConsumer

from consent_api.services.command_handler import CommandHandler

logger = structlog.get_logger()


class InternalCommandsConsumer(SQSConsumer):
    """Listens on the internal-commands queue and dispatches to the command handler.

    Recognised event types:
    - ``PauseConsentCollection`` -- pause consent creation for a given scope.
    - ``ResumeConsentCollection`` -- resume consent creation.
    """

    def __init__(self, queue_url: str, settings: Any, **kwargs: Any) -> None:
        super().__init__(queue_url=queue_url, settings=settings, **kwargs)
        self._handler = CommandHandler()

    async def handle_message(self, event: dict[str, Any]) -> None:
        """Route an incoming event to the appropriate command handler method."""
        event_type = event.get("event_type", "")
        payload = event.get("payload", {})

        logger.info(
            "internal_command_received",
            event_type=event_type,
            payload_keys=list(payload.keys()),
        )

        if event_type == "PauseConsentCollection":
            scope = payload.get("scope", "all")
            reason = payload.get("reason", "No reason provided")
            await self._handler.handle_pause(scope=scope, reason=reason)

        elif event_type == "ResumeConsentCollection":
            await self._handler.handle_resume()

        else:
            logger.warning("unknown_internal_command", event_type=event_type)
