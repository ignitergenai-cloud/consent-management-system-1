"""Configuration for the Incident Bridge service."""

from cms_shared.config import Settings as BaseSettings


class IncidentBridgeSettings(BaseSettings):
    """Configuration for the Incident Bridge service.

    Extends the shared CMS settings with incident-bridge-specific configuration
    such as the MIMS system name, bridge queue URLs, and SNS topic ARNs.
    """

    service_name: str = "incident-bridge"
    service_port: int = 8004
    mims_system_name: str = "EXTERNAL-MIMS"
    max_event_log_size: int = 100

    # SQS queues for bridge consumers
    sqs_incident_bridge_queue: str = (
        "http://localhost:4566/000000000000/cms-incident-bridge-queue"
    )
    sqs_incident_commands_queue: str = (
        "http://localhost:4566/000000000000/cms-incident-commands-queue"
    )

    # SNS topics for outbound publishing
    sns_mims_inbound_topic: str = (
        "arn:aws:sns:us-east-1:000000000000:mims-inbound-incidents"
    )
    sns_internal_commands_topic: str = (
        "arn:aws:sns:us-east-1:000000000000:cms-internal-commands"
    )
