"""Incident models."""

from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class IncidentSeverity(str, Enum):
    """Incident severity levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentType(str, Enum):
    """Types of incidents."""

    MASS_CONSENT_FAILURE = "MASS_CONSENT_FAILURE"
    NOTIFICATION_SERVICE_DOWN = "NOTIFICATION_SERVICE_DOWN"
    HIGH_ERROR_RATE = "HIGH_ERROR_RATE"
    THROUGHPUT_DROP = "THROUGHPUT_DROP"
    DATA_BREACH = "DATA_BREACH"
    SYSTEM_OUTAGE = "SYSTEM_OUTAGE"


class IncidentStatus(str, Enum):
    """Incident lifecycle status."""

    DETECTED = "DETECTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    INVESTIGATING = "INVESTIGATING"
    MITIGATING = "MITIGATING"
    RESOLVED = "RESOLVED"


class Incident(BaseModel):
    """Incident record."""

    incident_id: str = Field(default_factory=lambda: str(uuid4()))
    severity: IncidentSeverity
    incident_type: IncidentType
    status: IncidentStatus = IncidentStatus.DETECTED
    title: str
    description: str
    affected_customer_count: int = 0
    metrics: dict = Field(default_factory=dict)
    recommended_action: str | None = None
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    mims_incident_id: str | None = None
