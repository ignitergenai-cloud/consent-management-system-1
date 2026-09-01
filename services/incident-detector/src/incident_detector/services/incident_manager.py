"""Manages the full lifecycle of incidents (create, acknowledge, resolve)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from cms_shared.aws.dynamodb import DynamoDBManager
from cms_shared.aws.sns import SNSPublisher
from cms_shared.models.events import create_event
from cms_shared.models.incident import Incident, IncidentStatus
from cms_shared.utils.serialization import to_dynamodb_item, from_dynamodb_item

from incident_detector.config import IncidentDetectorSettings
from incident_detector.services.anomaly_detector import AnomalyResult

logger = structlog.get_logger(__name__)


class IncidentManager:
    """Persists incidents to DynamoDB and publishes lifecycle events to SNS.

    Parameters
    ----------
    dynamo:
        An initialised :class:`DynamoDBManager`.
    sns:
        An initialised :class:`SNSPublisher`.
    settings:
        Service-specific settings (table name, topic ARN, etc.).
    """

    def __init__(
        self,
        dynamo: DynamoDBManager,
        sns: SNSPublisher,
        settings: IncidentDetectorSettings,
    ) -> None:
        self._dynamo = dynamo
        self._sns = sns
        self._settings = settings

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_incident(self, anomaly: AnomalyResult) -> Incident:
        """Create a new incident from an :class:`AnomalyResult`.

        The incident is persisted to DynamoDB and an ``IncidentDetected``
        event is published to the configured SNS topic.
        """
        incident = Incident(
            severity=anomaly.severity,
            incident_type=anomaly.incident_type,
            title=anomaly.title,
            description=anomaly.description,
            metrics=anomaly.metrics,
            recommended_action=anomaly.recommended_action,
            affected_customer_count=anomaly.affected_customer_count,
        )

        # Persist to DynamoDB
        item = to_dynamodb_item(incident)
        item["PK"] = f"INCIDENT#{incident.incident_id}"
        item["SK"] = "METADATA"
        await self._dynamo.table.put_item(Item=item)

        logger.info(
            "incident_created",
            incident_id=incident.incident_id,
            severity=incident.severity.value,
            incident_type=incident.incident_type.value,
        )

        # Publish event
        event = create_event(
            event_type="IncidentDetected",
            source="incident-detector",
            payload=incident.model_dump(mode="json"),
        )
        await self._sns.publish_event(
            topic_arn=self._settings.incident_detected_topic_arn,
            event=event,
        )

        return incident

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_incident(self, incident_id: str) -> Incident:
        """Fetch a single incident by its ID.

        Raises :class:`KeyError` when not found.
        """
        response = await self._dynamo.table.get_item(
            Key={"PK": f"INCIDENT#{incident_id}", "SK": "METADATA"},
        )
        item = response.get("Item")
        if not item:
            raise KeyError(f"Incident {incident_id} not found")
        return from_dynamodb_item(item, Incident)

    async def list_incidents(
        self,
        status: IncidentStatus | None = None,
    ) -> list[Incident]:
        """Return all incidents, optionally filtered by *status*.

        Uses a DynamoDB scan which is acceptable for moderate incident
        volumes.
        """
        scan_kwargs: dict[str, Any] = {
            "FilterExpression": "begins_with(PK, :pk_prefix) AND SK = :sk",
            "ExpressionAttributeValues": {":pk_prefix": "INCIDENT#", ":sk": "METADATA"},
        }

        if status is not None:
            scan_kwargs["FilterExpression"] += " AND #st = :status"
            scan_kwargs["ExpressionAttributeNames"] = {"#st": "status"}
            scan_kwargs["ExpressionAttributeValues"][":status"] = status.value

        response = await self._dynamo.table.scan(**scan_kwargs)
        items = response.get("Items", [])
        return [from_dynamodb_item(item, Incident) for item in items]

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def acknowledge_incident(self, incident_id: str) -> Incident:
        """Transition an incident to :attr:`IncidentStatus.ACKNOWLEDGED`."""
        return await self._update_status(
            incident_id,
            IncidentStatus.ACKNOWLEDGED,
            acknowledged_at=datetime.now(timezone.utc),
        )

    async def resolve_incident(self, incident_id: str) -> Incident:
        """Transition an incident to :attr:`IncidentStatus.RESOLVED`."""
        return await self._update_status(
            incident_id,
            IncidentStatus.RESOLVED,
            resolved_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _update_status(
        self,
        incident_id: str,
        new_status: IncidentStatus,
        **extra_fields: Any,
    ) -> Incident:
        """Generic status-transition helper."""
        update_expr_parts = ["#st = :status"]
        attr_names: dict[str, str] = {"#st": "status"}
        attr_values: dict[str, Any] = {":status": new_status.value}

        for field_name, field_value in extra_fields.items():
            placeholder = f":{field_name}"
            update_expr_parts.append(f"{field_name} = {placeholder}")
            if isinstance(field_value, datetime):
                attr_values[placeholder] = field_value.isoformat()
            else:
                attr_values[placeholder] = field_value

        update_expr = "SET " + ", ".join(update_expr_parts)

        await self._dynamo.table.update_item(
            Key={"PK": f"INCIDENT#{incident_id}", "SK": "METADATA"},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=attr_names,
            ExpressionAttributeValues=attr_values,
        )

        logger.info(
            "incident_status_updated",
            incident_id=incident_id,
            new_status=new_status.value,
        )

        return await self.get_incident(incident_id)
