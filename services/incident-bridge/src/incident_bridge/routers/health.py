"""Health-check endpoints for the Incident Bridge service."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Request

logger = structlog.get_logger()

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Basic liveness probe.

    Returns:
        A dictionary indicating the service is healthy.
    """
    return {"status": "healthy", "service": "incident-bridge"}


@router.get("/health/ready")
async def readiness_check(request: Request) -> dict[str, str]:
    """Readiness probe that verifies consumer tasks are running.

    Returns:
        A dictionary indicating whether the service is ready to
        process events.
    """
    try:
        incident_task = getattr(request.app.state, "incident_consumer_task", None)
        commands_task = getattr(request.app.state, "commands_consumer_task", None)

        if incident_task and not incident_task.done() and commands_task and not commands_task.done():
            return {"status": "ready", "service": "incident-bridge"}

        return {"status": "not_ready", "service": "incident-bridge"}
    except Exception as exc:
        logger.error("readiness_check_failed", error=str(exc))
        return {"status": "not_ready", "service": "incident-bridge"}
