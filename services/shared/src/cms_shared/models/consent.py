"""Consent models."""

import secrets
from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class ConsentStatus(str, Enum):
    """Status of a consent request."""

    PENDING = "PENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    GRANTED = "GRANTED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    FAILED = "FAILED"


class ConsentChannel(str, Enum):
    """Channel through which consent is requested."""

    SMS = "SMS"
    EMAIL = "EMAIL"


class ConsentType(str, Enum):
    """Type of consent being requested."""

    MARKETING = "MARKETING"
    DATA_PROCESSING = "DATA_PROCESSING"
    THIRD_PARTY_SHARING = "THIRD_PARTY_SHARING"
    TERMS_OF_SERVICE = "TERMS_OF_SERVICE"
    PRIVACY_POLICY = "PRIVACY_POLICY"


class ConsentRecord(BaseModel):
    """Full consent record."""

    consent_id: str = Field(default_factory=lambda: str(uuid4()))
    customer_id: str
    consent_type: ConsentType
    channel: ConsentChannel
    status: ConsentStatus = ConsentStatus.PENDING
    message_template_id: str
    customer_phone: str | None = None
    customer_email: str | None = None
    consent_text: str
    response_token: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    granted_at: datetime | None = None
    denied_at: datetime | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    metadata: dict = Field(default_factory=dict)


class CreateConsentRequest(BaseModel):
    """Request to create a new consent."""

    customer_id: str
    consent_type: ConsentType
    channel: ConsentChannel
    customer_phone: str | None = None
    customer_email: str | None = None
    consent_text: str
    message_template_id: str = "default"
    expires_in_hours: int = 72
    metadata: dict = Field(default_factory=dict)


class CreateConsentResponse(BaseModel):
    """Response after creating a consent."""

    consent_id: str
    status: ConsentStatus
    response_url: str
    expires_at: datetime
    created_at: datetime


class ListConsentsQuery(BaseModel):
    """Query parameters for listing consents."""

    status: ConsentStatus | None = None
    channel: ConsentChannel | None = None
    customer_id: str | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
    page_size: int = Field(default=20, le=100)
    next_token: str | None = None


class PaginatedConsentsResponse(BaseModel):
    """Paginated response for consent listings."""

    items: list[ConsentRecord]
    count: int
    next_token: str | None = None


class ConsentResponseRequest(BaseModel):
    """Request to record a consent response."""

    granted: bool
    ip_address: str | None = None
    user_agent: str | None = None


class ConsentAnalytics(BaseModel):
    """Analytics summary for consents."""

    total_consents: int
    by_status: dict[str, int]
    by_channel: dict[str, int]
    by_type: dict[str, int]
    grant_rate: float
    avg_response_time_hours: float
    period_start: datetime
    period_end: datetime
