"""Configuration for the Notification Service."""

from cms_shared.config import Settings as BaseSettings


class NotificationServiceSettings(BaseSettings):
    """Configuration for the Notification Service.

    Extends the shared CMS settings with notification-specific configuration
    such as the service name, port, SMS sender ID, and template directory.
    """

    service_name: str = "notification-service"
    service_port: int = 8002
    sms_sender_id: str = "CMS"
    email_template_dir: str = "notification_service/templates"
