"""Health check endpoints for the Notification Service."""

import structlog
from fastapi import APIRouter, Depends, Response

from cms_shared.aws.dynamodb import DynamoDBManager

from notification_service import __version__
from notification_service.dependencies import get_db, get_settings

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("/health")
async def health_check() -> dict:
    """Return basic health status of the notification service.

    Returns:
        A dictionary containing the service status, name, and version.
    """
    return {
        "status": "healthy",
        "service": "notification-service",
        "version": __version__,
    }


@router.get("/health/ready")
async def readiness_check(
    response: Response,
    db: DynamoDBManager = Depends(get_db),
) -> dict:
    """Check if the service is ready to handle requests.

    Verifies DynamoDB connectivity by describing the table. Returns a 503
    status code if the database is not reachable.

    Args:
        response: The FastAPI response object for setting status codes.
        db: The DynamoDB manager dependency.

    Returns:
        A dictionary with the readiness status.
    """
    try:
        # Check DynamoDB connectivity by describing the table
        await db.table.load()
        return {"status": "ready"}
    except Exception as exc:
        logger.error("Readiness check failed", error=str(exc))
        response.status_code = 503
        return {"status": "not ready", "error": str(exc)}
