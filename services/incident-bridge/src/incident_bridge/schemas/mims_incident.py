"""Pydantic model representing a MIMS-formatted incident."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MIMSIncident(BaseModel):
    """Schema for an incident in the external MIMS system format.

    This model defines the structure expected by the MIMS API when creating
    or updating incidents.  It is produced by :class:`EventTransformer` from
    internal CMS events and serialised before publishing to the MIMS inbound
    SNS topic.
    """

    source_system: str = Field(
        ..., description="Originating system identifier (e.g. 'consent-management-system')"
    )
    incident_id: str = Field(..., description="Unique incident identifier from the CMS")
    priority: str = Field(
        ..., description="MIMS priority code (P1-P4) mapped from CMS severity"
    )
    category: str = Field(..., description="Top-level MIMS incident category")
    subcategory: str = Field(default="", description="MIMS incident subcategory")
    title: str = Field(..., description="Short summary of the incident")
    description: str = Field(default="", description="Detailed incident description")
    affected_users: int = Field(
        default=0, ge=0, description="Estimated number of users affected"
    )
    detected_at: str = Field(
        ..., description="ISO-8601 timestamp of when the incident was detected"
    )
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary key/value metrics associated with the incident",
    )
    recommended_action: str = Field(
        default="", description="Recommended remediation action"
    )
    correlation_id: str = Field(
        default="", description="Correlation identifier for distributed tracing"
    )
