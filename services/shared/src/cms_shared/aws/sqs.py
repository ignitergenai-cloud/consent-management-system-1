"""SQS async consumer base class."""

import asyncio
import json
from contextlib import AsyncExitStack

import aioboto3
import structlog

logger = structlog.get_logger()


class SQSConsumer:
    """Async SQS consumer with long-polling."""

    def __init__(
        self,
        queue_url: str,
        settings,
        max_messages: int = 10,
        wait_seconds: int = 20,
        visibility_timeout: int = 30,
    ) -> None:
        self._queue_url = queue_url
        self._settings = settings
        self._max_messages = max_messages
        self._wait_seconds = wait_seconds
        self._visibility_timeout = visibility_timeout
        self._session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key,
            aws_secret_access_key=settings.aws_secret_key,
            region_name=settings.aws_region,
        )
        self._exit_stack: AsyncExitStack | None = None
        self._client = None
        self._running = False

    async def startup(self) -> None:
        """Initialize SQS client."""
        self._exit_stack = AsyncExitStack()
        self._client = await self._exit_stack.enter_async_context(
            self._session.client(
                "sqs",
                endpoint_url=self._settings.aws_endpoint_url,
            )
        )
        logger.info("SQS consumer started", queue_url=self._queue_url)

    async def shutdown(self) -> None:
        """Close SQS connections."""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._client = None
        logger.info("SQS consumer shut down")

    async def start(self) -> None:
        """Start the long-polling consumer loop."""
        if self._client is None:
            raise RuntimeError("SQS consumer not started. Call startup() first.")

        self._running = True
        logger.info("SQS consumer polling started", queue_url=self._queue_url)

        while self._running:
            try:
                response = await self._client.receive_message(
                    QueueUrl=self._queue_url,
                    MaxNumberOfMessages=self._max_messages,
                    WaitTimeSeconds=self._wait_seconds,
                    VisibilityTimeout=self._visibility_timeout,
                )

                messages = response.get("Messages", [])
                for message in messages:
                    try:
                        body = json.loads(message["Body"])

                        # Unwrap SNS envelope if present
                        if "Message" in body and "TopicArn" in body:
                            event = json.loads(body["Message"])
                        else:
                            event = body

                        await self.handle_message(event)

                        # Delete message after successful processing
                        await self._client.delete_message(
                            QueueUrl=self._queue_url,
                            ReceiptHandle=message["ReceiptHandle"],
                        )
                    except Exception:
                        logger.exception(
                            "Error processing SQS message",
                            queue_url=self._queue_url,
                            message_id=message.get("MessageId"),
                        )
            except asyncio.CancelledError:
                logger.info("SQS consumer cancelled", queue_url=self._queue_url)
                break
            except Exception:
                logger.exception(
                    "Error polling SQS",
                    queue_url=self._queue_url,
                )
                await asyncio.sleep(5)

    async def handle_message(self, event: dict) -> None:
        """Handle a single message. Override in subclasses.

        Args:
            event: The parsed message event dict.
        """
        raise NotImplementedError("Subclasses must implement handle_message()")

    async def stop(self) -> None:
        """Stop the consumer loop."""
        self._running = False
        logger.info("SQS consumer stopping", queue_url=self._queue_url)
