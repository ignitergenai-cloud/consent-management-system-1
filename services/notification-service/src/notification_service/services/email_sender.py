"""Email sending service using AWS SES."""

import structlog

from cms_shared.aws.ses import SESClient

from notification_service.config import NotificationServiceSettings

logger = structlog.get_logger(__name__)


class EmailSender:
    """Sends email messages via AWS SES.

    Wraps the SESClient to provide a focused interface for sending
    email notifications with structured logging, using the configured
    from-email address.
    """

    def __init__(
        self, ses_client: SESClient, settings: NotificationServiceSettings
    ) -> None:
        """Initialize the email sender.

        Args:
            ses_client: The SES client for sending emails.
            settings: Service configuration containing the from-email address.
        """
        self._ses = ses_client
        self._settings = settings

    async def send_email(
        self, to: str, subject: str, html_body: str, text_body: str
    ) -> str:
        """Send an email to the specified recipient.

        Args:
            to: The recipient email address.
            subject: The email subject line.
            html_body: The HTML version of the email body.
            text_body: The plain text version of the email body.

        Returns:
            The SES message ID for the sent email.

        Raises:
            Exception: If the email fails to send via SES.
        """
        log = logger.bind(to=to, subject=subject, from_email=self._settings.from_email)
        await log.ainfo("Sending email message")

        message_id = await self._ses.send_email(
            to=to,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            from_email=self._settings.from_email,
        )

        await log.ainfo("Email sent successfully", message_id=message_id)
        return message_id
