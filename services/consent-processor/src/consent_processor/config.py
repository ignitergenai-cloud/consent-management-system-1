"""Service-specific settings for the Consent Processor."""

from cms_shared.config import Settings as BaseSettings


class ConsentProcessorSettings(BaseSettings):
    """Configuration for the Consent Processor Service.

    Extends the shared CMS settings with processor-specific configuration
    such as the service name, port, expiry check interval, retry limits,
    and the notification status queue URL.
    """

    service_name: str = "consent-processor"
    service_port: int = 8001
    consent_expiry_check_interval: int = 300  # seconds
    max_notification_retries: int = 3
    notification_status_queue_url: str = (
        "http://localhost:4566/000000000000/notification-status-queue"
    )
