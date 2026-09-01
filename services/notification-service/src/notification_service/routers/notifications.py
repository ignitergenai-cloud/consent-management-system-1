"""Notification query endpoints for the Notification Service."""

import structlog
from fastapi import APIRouter, Depends, HTTPException

from cms_shared.aws.dynamodb import DynamoDBManager
from cms_shared.models import NotificationLog
from cms_shared.utils import from_dynamodb_item

from notification_service.dependencies import get_db

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("/{notification_id}")
async def get_notification(
    notification_id: str,
    db: DynamoDBManager = Depends(get_db),
) -> dict:
    """Retrieve a notification log entry by its ID.

    Queries DynamoDB for the notification log with the given ID and returns
    the full notification details.

    Args:
        notification_id: The unique identifier of the notification to retrieve.
        db: The DynamoDB manager dependency.

    Returns:
        The notification log entry as a dictionary.

    Raises:
        HTTPException: 404 if the notification is not found, 500 on query errors.
    """
    log = logger.bind(notification_id=notification_id)
    await log.ainfo("Retrieving notification")

    try:
        response = await db.table.get_item(
            Key={
                "PK": f"NOTIFICATION#{notification_id}",
                "SK": f"NOTIFICATION#{notification_id}",
            }
        )
    except Exception as exc:
        await log.aerror("Failed to query DynamoDB", error=str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve notification: {exc}",
        )

    item = response.get("Item")
    if not item:
        await log.awarn("Notification not found")
        raise HTTPException(
            status_code=404,
            detail=f"Notification {notification_id} not found",
        )

    try:
        notification = from_dynamodb_item(item, NotificationLog)
        await log.ainfo("Notification retrieved successfully")
        return notification.model_dump(mode="json")
    except Exception as exc:
        await log.aerror("Failed to deserialize notification", error=str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to deserialize notification: {exc}",
        )
