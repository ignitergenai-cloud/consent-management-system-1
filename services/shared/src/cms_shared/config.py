"""Configuration for Consent Management System microservices."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Shared configuration for all CMS microservices."""

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    # AWS
    aws_endpoint_url: str | None = None
    aws_region: str = "us-east-1"
    aws_access_key: str | None = None
    aws_secret_key: str | None = None

    # DynamoDB
    dynamodb_table_name: str = "cms-consents"

    # SNS topic ARNs
    consent_created_topic_arn: str = (
        "arn:aws:sns:us-east-1:000000000000:consent-created"
    )
    consent_granted_topic_arn: str = (
        "arn:aws:sns:us-east-1:000000000000:consent-granted"
    )
    consent_denied_topic_arn: str = (
        "arn:aws:sns:us-east-1:000000000000:consent-denied"
    )
    consent_expired_topic_arn: str = (
        "arn:aws:sns:us-east-1:000000000000:consent-expired"
    )
    consent_revoked_topic_arn: str = (
        "arn:aws:sns:us-east-1:000000000000:consent-revoked"
    )
    notification_sent_topic_arn: str = (
        "arn:aws:sns:us-east-1:000000000000:notification-sent"
    )
    incident_detected_topic_arn: str = (
        "arn:aws:sns:us-east-1:000000000000:incident-detected"
    )

    # SQS queue URLs
    consent_created_queue_url: str = (
        "http://localhost:4566/000000000000/consent-created-queue"
    )
    consent_granted_queue_url: str = (
        "http://localhost:4566/000000000000/consent-granted-queue"
    )
    consent_denied_queue_url: str = (
        "http://localhost:4566/000000000000/consent-denied-queue"
    )
    consent_expired_queue_url: str = (
        "http://localhost:4566/000000000000/consent-expired-queue"
    )
    consent_revoked_queue_url: str = (
        "http://localhost:4566/000000000000/consent-revoked-queue"
    )
    notification_queue_url: str = (
        "http://localhost:4566/000000000000/notification-queue"
    )
    incident_queue_url: str = (
        "http://localhost:4566/000000000000/incident-queue"
    )

    # S3
    consent_documents_bucket: str = "cms-consent-documents"

    # SES
    from_email: str = "noreply@consent.example.com"

    # Incident detection
    failure_rate_threshold: float = 0.1
    detection_interval_seconds: int = 60
    detection_window_minutes: int = 5

    # Service URLs
    consent_api_url: str = "http://localhost:8001"
    notification_service_url: str = "http://localhost:8002"
