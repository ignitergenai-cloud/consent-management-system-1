"""Health-check endpoints for the Incident Detector service."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/health", tags=["health"])
logger = structlog.get_logger(__name__)


@router.get("")
async def health() -> dict:
    """Basic liveness probe -- always returns 200 if the process is up."""
    return {"status": "healthy", "service": "incident-detector"}


@router.get("/ready")
async def readiness(request: Request) -> JSONResponse:
    """Readiness probe that verifies the DynamoDB connection.

    Returns 200 when the table is reachable, 503 otherwise.
    """
    dynamo = request.app.state.dynamo_manager
    try:
        # A lightweight operation to verify the table is accessible.
        await dynamo.table.table_status  # type: ignore[misc]
        return JSONResponse(
            content={"status": "ready", "service": "incident-detector"},
            status_code=200,
        )
    except Exception as exc:
        logger.error("readiness_check_failed", error=str(exc))
        return JSONResponse(
            content={
                "status": "not_ready",
                "service": "incident-detector",
                "detail": str(exc),
            },
            status_code=503,
        )
