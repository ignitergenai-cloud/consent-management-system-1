"""Service-specific settings for the Consent API."""

from cms_shared.config import Settings as BaseSettings


class ConsentApiSettings(BaseSettings):
    """Consent API configuration extending shared settings."""

    service_name: str = "consent-api"
    service_port: int = 8000
    base_url: str = "http://localhost:8000"
    response_base_url: str = "http://localhost:8000/api/v1/consents/respond"
    internal_commands_queue_url: str = (
        "http://localhost:4566/000000000000/cms-internal-commands-queue"
    )
