"""Health-check endpoints."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Request

logger = structlog.get_logger()

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Basic liveness probe."""
    return {"status": "healthy", "service": "consent-api"}


@router.get("/health/ready")
async def readiness_check(request: Request) -> dict[str, str]:
    """Readiness probe that verifies the DynamoDB connection is live."""
    try:
        dynamo_manager = request.app.state.dynamo_manager
        # Attempt a lightweight operation to confirm the table is reachable
        _ = dynamo_manager.table
        return {"status": "ready", "service": "consent-api"}
    except RuntimeError:
        logger.error("readiness_check_failed", reason="DynamoDB not initialised")
        return {"status": "not_ready", "service": "consent-api"}
    except Exception as exc:
        logger.error("readiness_check_failed", error=str(exc))
        return {"status": "not_ready", "service": "consent-api"}
