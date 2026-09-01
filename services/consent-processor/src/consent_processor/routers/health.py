"""Health-check endpoints for the Consent Processor service."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Request

from consent_processor import __version__

logger = structlog.get_logger()

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Basic liveness probe.

    Returns a simple JSON object confirming the service is running.
    """
    return {
        "status": "healthy",
        "service": "consent-processor",
        "version": __version__,
    }


@router.get("/health/ready")
async def readiness_check(request: Request) -> dict[str, str]:
    """Readiness probe that verifies the DynamoDB connection is live.

    Attempts to access the DynamoDB table reference from the application
    state.  If the table has not been initialised (e.g. startup is still
    in progress) the response indicates the service is not ready.
    """
    try:
        dynamo_manager = request.app.state.db
        # Access the table property to confirm the manager has been started
        _ = dynamo_manager.table
        return {"status": "ready", "service": "consent-processor"}
    except RuntimeError:
        logger.error("readiness_check_failed", reason="DynamoDB not initialised")
        return {"status": "not_ready", "service": "consent-processor"}
    except Exception as exc:
        logger.error("readiness_check_failed", error=str(exc))
        return {"status": "not_ready", "service": "consent-processor"}
