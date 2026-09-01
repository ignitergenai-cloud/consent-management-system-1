"""SES email sender helper."""

from contextlib import AsyncExitStack

import aioboto3
import structlog

logger = structlog.get_logger()


class SESClient:
    """Async SES email client."""

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
        """Initialize SES client."""
        self._exit_stack = AsyncExitStack()
        self._client = await self._exit_stack.enter_async_context(
            self._session.client(
                "ses",
                endpoint_url=self._settings.aws_endpoint_url,
            )
        )
        logger.info("SES client started")

    async def shutdown(self) -> None:
        """Close SES connections."""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._client = None
        logger.info("SES client shut down")

    async def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: str,
        from_email: str | None = None,
    ) -> str:
        """Send an email via SES.

        Args:
            to: Recipient email address.
            subject: Email subject.
            html_body: HTML email body.
            text_body: Plain text email body.
            from_email: Sender email (defaults to settings.ses_from_email).

        Returns:
            The SES message ID.
        """
        if self._client is None:
            raise RuntimeError("SES client not started. Call startup() first.")

        sender = from_email or self._settings.ses_from_email
        response = await self._client.send_email(
            Source=sender,
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": html_body, "Charset": "UTF-8"},
                    "Text": {"Data": text_body, "Charset": "UTF-8"},
                },
            },
        )
        message_id = response["MessageId"]
        logger.info("Email sent via SES", to=to, message_id=message_id)
        return message_id
