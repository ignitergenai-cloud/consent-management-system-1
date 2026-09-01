"""Bridge status and event log endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from incident_bridge.dependencies import get_bridge_status, get_event_log
from incident_bridge.services.bridge_event_log import BridgeEventLog

router = APIRouter()


@router.get("/status")
async def bridge_status(status: dict = Depends(get_bridge_status)) -> dict:
    """Return the current bridge status.

    Returns:
        A dictionary containing:
        - consumers_running: whether both SQS consumer tasks are active
        - mims_topic: the MIMS inbound SNS topic ARN
        - total_events_processed: count of events in the bridge log
    """
    return status


@router.get("/events")
async def bridge_events(
    event_log: BridgeEventLog = Depends(get_event_log),
    limit: int = Query(default=50, ge=1, le=100, description="Number of recent events to return"),
) -> dict:
    """Return recent bridge events.

    Args:
        event_log: The in-memory bridge event log.
        limit: Maximum number of events to return (1-100, default 50).

    Returns:
        A dictionary with the list of recent events and the total count.
    """
    events = event_log.get_recent(limit=limit)
    return {
        "events": events,
        "total_count": event_log.total_count,
        "returned_count": len(events),
    }
