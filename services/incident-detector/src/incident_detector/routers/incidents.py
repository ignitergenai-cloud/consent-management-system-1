"""CRUD endpoints for managing incidents."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from cms_shared.models.incident import Incident, IncidentStatus

from incident_detector.dependencies import get_incident_manager
from incident_detector.services.incident_manager import IncidentManager

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("")
async def list_incidents(
    status: Optional[IncidentStatus] = Query(default=None),
    manager: IncidentManager = Depends(get_incident_manager),
) -> list[dict]:
    """List all incidents, optionally filtered by status."""
    incidents = await manager.list_incidents(status=status)
    return [inc.model_dump(mode="json") for inc in incidents]


@router.get("/{incident_id}")
async def get_incident(
    incident_id: str,
    manager: IncidentManager = Depends(get_incident_manager),
) -> dict:
    """Retrieve a single incident by its ID."""
    incident = await manager.get_incident(incident_id)
    return incident.model_dump(mode="json")


@router.post("/{incident_id}/acknowledge")
async def acknowledge_incident(
    incident_id: str,
    manager: IncidentManager = Depends(get_incident_manager),
) -> dict:
    """Acknowledge an incident, transitioning it to ACKNOWLEDGED status."""
    incident = await manager.acknowledge_incident(incident_id)
    return incident.model_dump(mode="json")


@router.post("/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    manager: IncidentManager = Depends(get_incident_manager),
) -> dict:
    """Resolve an incident, transitioning it to RESOLVED status."""
    incident = await manager.resolve_incident(incident_id)
    return incident.model_dump(mode="json")
