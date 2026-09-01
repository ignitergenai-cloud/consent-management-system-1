"""Pydantic model representing a command originating from the MIMS system."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MIMSCommand(BaseModel):
    """Schema for an inbound command received from the external MIMS system.

    MIMS may instruct the CMS to pause or resume consent collection when an
    incident is being investigated or has been resolved.
    """

    command_type: str = Field(
        ..., description="Type of command: PAUSE or RESUME"
    )
    incident_id: str = Field(
        ..., description="MIMS incident identifier this command relates to"
    )
    scope: str = Field(
        default="", description="Scope of the command (e.g. 'all', a region, or a service)"
    )
    reason: str = Field(
        default="", description="Human-readable reason for the command"
    )
    resume_condition: str = Field(
        default="",
        description="Condition that must be met before consent collection resumes",
    )
