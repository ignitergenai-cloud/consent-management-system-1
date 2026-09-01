"""Consent state machine and workflow orchestration.

Implements every valid consent status transition, enforces the transition
rules, persists changes to DynamoDB, publishes domain events to SNS, and
coordinates with the :class:`NotificationOrchestrator` to trigger (or
retry) customer notifications.
"""

from __future__ import annotations

from datetime import datetime

import structlog

from cms_shared.aws.dynamodb import DynamoDBManager
from cms_shared.aws.sns import SNSPublisher
from cms_shared.models.consent import ConsentRecord, ConsentStatus
from cms_shared.models.events import create_event
from cms_shared.utils.serialization import from_dynamodb_item

from consent_processor.config import ConsentProcessorSettings
from consent_processor.services.notification_orchestrator import NotificationOrchestrator

logger = structlog.get_logger()


class ConsentWorkflow:
    """Manages consent state transitions and workflow orchestration.

    The class owns the canonical set of allowed transitions between
    :class:`ConsentStatus` values.  Every public method that mutates a
    consent record goes through :meth:`transition`, which validates the
    move, updates DynamoDB, and returns the refreshed record.
    """

    VALID_TRANSITIONS: dict[ConsentStatus, list[ConsentStatus]] = {
        ConsentStatus.PENDING: [ConsentStatus.SENT, ConsentStatus.FAILED, ConsentStatus.EXPIRED],
        ConsentStatus.SENT: [ConsentStatus.DELIVERED, ConsentStatus.FAILED, ConsentStatus.EXPIRED],
        ConsentStatus.DELIVERED: [ConsentStatus.GRANTED, ConsentStatus.DENIED, ConsentStatus.EXPIRED],
        ConsentStatus.GRANTED: [ConsentStatus.REVOKED],
        ConsentStatus.DENIED: [],
        ConsentStatus.EXPIRED: [],
        ConsentStatus.REVOKED: [],
        ConsentStatus.FAILED: [ConsentStatus.PENDING],  # retry
    }

    def __init__(
        self,
        db: DynamoDBManager,
        sns: SNSPublisher,
        notification_orchestrator: NotificationOrchestrator,
        settings: ConsentProcessorSettings,
    ) -> None:
        self._db = db
        self._sns = sns
        self._notification_orchestrator = notification_orchestrator
        self._settings = settings

    # ------------------------------------------------------------------
    # Core helpers
    # ------------------------------------------------------------------

    async def _get_consent(self, consent_id: str) -> ConsentRecord:
        """Fetch a consent record from DynamoDB by its ID.

        Args:
            consent_id: The unique consent identifier.

        Returns:
            The deserialised :class:`ConsentRecord`.

        Raises:
            ValueError: If the record does not exist.
        """
        key = {"PK": f"CONSENT#{consent_id}", "SK": f"CONSENT#{consent_id}"}
        response = await self._db.table.get_item(Key=key)
        item = response.get("Item")
        if not item:
            raise ValueError(f"Consent record not found: {consent_id}")
        return from_dynamodb_item(item, ConsentRecord)

    async def _update_status(
        self,
        consent_id: str,
        new_status: ConsentStatus,
        extra_attrs: dict | None = None,
    ) -> dict:
        """Persist a status change (and optional extra attributes) to DynamoDB.

        Args:
            consent_id: The consent to update.
            new_status: The target status.
            extra_attrs: Optional mapping of additional attribute names to
                values that should be set alongside the status change
                (e.g. ``granted_at``).

        Returns:
            The DynamoDB ``Attributes`` dict from the update response.
        """
        key = {"PK": f"CONSENT#{consent_id}", "SK": f"CONSENT#{consent_id}"}
        now = datetime.utcnow().isoformat()

        update_expr_parts = ["#st = :new_status", "#ua = :updated_at"]
        expr_names: dict[str, str] = {"#st": "status", "#ua": "updated_at"}
        expr_values: dict[str, str] = {
            ":new_status": new_status.value,
            ":updated_at": now,
        }

        if extra_attrs:
            for idx, (attr_name, attr_value) in enumerate(extra_attrs.items()):
                placeholder_name = f"#ea{idx}"
                placeholder_value = f":ea{idx}"
                update_expr_parts.append(f"{placeholder_name} = {placeholder_value}")
                expr_names[placeholder_name] = attr_name
                expr_values[placeholder_value] = attr_value

        update_expression = "SET " + ", ".join(update_expr_parts)

        response = await self._db.table.update_item(
            Key=key,
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
            ReturnValues="ALL_NEW",
        )
        return response.get("Attributes", {})

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    async def transition(self, consent_id: str, new_status: ConsentStatus) -> ConsentRecord:
        """Validate and perform a consent status transition.

        Args:
            consent_id: The consent to transition.
            new_status: The desired target status.

        Returns:
            The updated :class:`ConsentRecord` reflecting the new status.

        Raises:
            ValueError: If the consent does not exist or the transition is
                not permitted by :attr:`VALID_TRANSITIONS`.
        """
        consent = await self._get_consent(consent_id)
        current_status = consent.status

        allowed = self.VALID_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition from {current_status.value} to {new_status.value} "
                f"for consent {consent_id}"
            )

        extra_attrs: dict[str, str] = {}
        now_iso = datetime.utcnow().isoformat()
        if new_status == ConsentStatus.GRANTED:
            extra_attrs["granted_at"] = now_iso
        elif new_status == ConsentStatus.DENIED:
            extra_attrs["denied_at"] = now_iso

        updated_item = await self._update_status(consent_id, new_status, extra_attrs or None)
        updated_consent = from_dynamodb_item(updated_item, ConsentRecord)

        logger.info(
            "consent_transitioned",
            consent_id=consent_id,
            from_status=current_status.value,
            to_status=new_status.value,
        )

        return updated_consent

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def process_consent_requested(self, event: dict) -> None:
        """Handle a ConsentRequested / ConsentCreated event.

        Fetches the consent record from DynamoDB and asks the
        :class:`NotificationOrchestrator` to deliver the consent request
        notification to the customer.

        Args:
            event: The raw event dict (already unwrapped from the SNS
                envelope by the SQS consumer).
        """
        payload = event.get("payload", {})
        consent_id = payload.get("consent_id", "")
        correlation_id = event.get("correlation_id", "")

        logger.info(
            "processing_consent_requested",
            consent_id=consent_id,
            correlation_id=correlation_id,
        )

        try:
            consent = await self._get_consent(consent_id)
            await self._notification_orchestrator.request_notification(consent)
        except Exception:
            logger.exception(
                "consent_requested_processing_failed",
                consent_id=consent_id,
            )
            raise

    async def process_notification_sent(self, event: dict) -> None:
        """Handle a NotificationSent event.

        Transitions the consent from PENDING to SENT so that downstream
        consumers (and the customer-facing API) can reflect that the
        notification has been dispatched.

        Args:
            event: The raw event dict.
        """
        payload = event.get("payload", {})
        consent_id = payload.get("consent_id", "")

        logger.info("processing_notification_sent", consent_id=consent_id)

        try:
            await self.transition(consent_id, ConsentStatus.SENT)
        except ValueError as exc:
            logger.warning(
                "notification_sent_transition_skipped",
                consent_id=consent_id,
                reason=str(exc),
            )

    async def process_notification_failed(self, event: dict) -> None:
        """Handle a NotificationFailed event.

        If the retry count is below the configured maximum the consent is
        moved back to PENDING and a new notification request is published.
        Otherwise the consent is marked as FAILED.

        Args:
            event: The raw event dict.
        """
        payload = event.get("payload", {})
        consent_id = payload.get("consent_id", "")
        retry_count = payload.get("retry_count", 0)

        logger.info(
            "processing_notification_failed",
            consent_id=consent_id,
            retry_count=retry_count,
        )

        try:
            if retry_count < self._settings.max_notification_retries:
                # Transition to FAILED first, then back to PENDING for retry
                try:
                    await self.transition(consent_id, ConsentStatus.FAILED)
                except ValueError:
                    # May already be in FAILED state
                    pass

                consent = await self._get_consent(consent_id)
                if consent.status == ConsentStatus.FAILED:
                    await self.transition(consent_id, ConsentStatus.PENDING)
                    consent = await self._get_consent(consent_id)
                    await self._notification_orchestrator.request_notification(
                        consent, retry_count=retry_count + 1
                    )

                logger.info(
                    "notification_retry_scheduled",
                    consent_id=consent_id,
                    retry_count=retry_count + 1,
                )
            else:
                await self.transition(consent_id, ConsentStatus.FAILED)
                logger.warning(
                    "consent_marked_failed_max_retries",
                    consent_id=consent_id,
                    retry_count=retry_count,
                )
        except Exception:
            logger.exception(
                "notification_failed_processing_error",
                consent_id=consent_id,
            )
            raise
