"""SMS sending service using AWS SNS."""

import structlog

from cms_shared.aws.sns import SNSPublisher

from notification_service.config import NotificationServiceSettings

logger = structlog.get_logger(__name__)


class SMSSender:
    """Sends SMS messages via AWS SNS.

    Wraps the SNSPublisher to provide a focused interface for sending
    SMS notifications with structured logging.
    """

    def __init__(
        self, sns_publisher: SNSPublisher, settings: NotificationServiceSettings
    ) -> None:
        """Initialize the SMS sender.

        Args:
            sns_publisher: The SNS publisher client for sending messages.
            settings: Service configuration containing SMS sender ID and other options.
        """
        self._sns = sns_publisher
        self._settings = settings

    async def send_sms(self, phone_number: str, message: str) -> str:
        """Send an SMS message to the specified phone number.

        Args:
            phone_number: The recipient phone number in E.164 format.
            message: The text message content to send.

        Returns:
            The SNS message ID for the sent SMS.

        Raises:
            Exception: If the SMS fails to send via SNS.
        """
        log = logger.bind(phone_number=phone_number, sender_id=self._settings.sms_sender_id)
        await log.ainfo("Sending SMS message")

        message_id = await self._sns.publish_sms(phone_number, message)

        await log.ainfo("SMS message sent successfully", message_id=message_id)
        return message_id
