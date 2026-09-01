"""SNS publisher helper."""

import json
from contextlib import AsyncExitStack

import aioboto3
import structlog

from cms_shared.models.events import EventEnvelope

logger = structlog.get_logger()


class SNSPublisher:
    """Async SNS publisher."""

    def __init__(self, settings) -> None:
        self._settings = settings
        self._session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key,
            aws_secret_access_key=settings.aws_secret_key,
            region_name=settings.aws_region,
        )
        self._exit_stack: AsyncExitStack | None = None
        self._client = None

    async def startup(self) -> None:
        """Initialize SNS client."""
        self._exit_stack = AsyncExitStack()
        self._client = await self._exit_stack.enter_async_context(
            self._session.client(
                "sns",
                endpoint_url=self._settings.aws_endpoint_url,
            )
        )
        logger.info("SNS publisher started")

    async def shutdown(self) -> None:
        """Close SNS connections."""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._client = None
        logger.info("SNS publisher shut down")

    async def publish_event(self, topic_arn: str, event: EventEnvelope) -> str:
        """Publish an event to an SNS topic.

        Args:
            topic_arn: The ARN of the SNS topic.
            event: The event envelope to publish.

        Returns:
            The SNS message ID.
        """
        if self._client is None:
            raise RuntimeError("SNS publisher not started. Call startup() first.")

        message = event.model_dump_json()
        response = await self._client.publish(
            TopicArn=topic_arn,
            Message=message,
            MessageAttributes={
                "event_type": {
                    "DataType": "String",
                    "StringValue": event.event_type,
                },
                "source": {
                    "DataType": "String",
                    "StringValue": event.source,
                },
            },
        )
        message_id = response["MessageId"]
        logger.info(
            "Event published to SNS",
            topic_arn=topic_arn,
            event_type=event.event_type,
            message_id=message_id,
        )
        return message_id

    async def publish_sms(self, phone_number: str, message: str) -> str:
        """Publish an SMS message via SNS.

        Args:
            phone_number: The phone number to send to.
            message: The SMS message text.

        Returns:
            The SNS message ID.
        """
        if self._client is None:
            raise RuntimeError("SNS publisher not started. Call startup() first.")

        response = await self._client.publish(
            PhoneNumber=phone_number,
            Message=message,
        )
        message_id = response["MessageId"]
        logger.info(
            "SMS published via SNS",
            phone_number=phone_number,
            message_id=message_id,
        )
        return message_id
