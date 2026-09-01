"""Notification models."""

from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from cms_shared.models.consent import ConsentChannel


class NotificationStatus(str, Enum):
    """Notification delivery status."""

    QUEUED = "QUEUED"
    SENDING = "SENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    BOUNCED = "BOUNCED"


class NotificationLog(BaseModel):
    """Notification log entry."""

    notification_id: str = Field(default_factory=lambda: str(uuid4()))
    consent_id: str
    channel: ConsentChannel
    recipient: str
    template_id: str
    template_vars: dict = Field(default_factory=dict)
    status: NotificationStatus = NotificationStatus.QUEUED
    provider_message_id: str | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    failed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
