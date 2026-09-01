"""Periodic expiry checker for consent records.

Runs on a configurable interval, scanning DynamoDB for consent records
that have passed their ``expires_at`` timestamp while still in a
non-terminal status (PENDING, SENT, or DELIVERED).  Each expired record
is transitioned to EXPIRED and a corresponding domain event is published.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import structlog

from cms_shared.aws.dynamodb import DynamoDBManager
from cms_shared.aws.sns import SNSPublisher
from cms_shared.models.consent import ConsentRecord, ConsentStatus
from cms_shared.models.events import create_event
from cms_shared.utils.serialization import from_dynamodb_item

from consent_processor.config import ConsentProcessorSettings

logger = structlog.get_logger()


class ExpiryChecker:
    """Periodically checks for and expires overdue consents.

    The checker scans DynamoDB for records whose ``expires_at`` timestamp
    is in the past and whose status is still one of PENDING, SENT, or
    DELIVERED.  For each match it updates the status to EXPIRED and
    publishes a ``ConsentExpired`` event so that other services can react.
    """

    def __init__(
        self,
        db: DynamoDBManager,
        sns: SNSPublisher,
        settings: ConsentProcessorSettings,
    ) -> None:
        self._db = db
        self._sns = sns
        self._settings = settings
        self._interval = settings.consent_expiry_check_interval
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Run the periodic expiry check loop.

        Loops indefinitely (with ``self._interval`` second sleeps) until
        :meth:`stop` is called.  Exceptions inside a single iteration are
        logged but do not break the loop.
        """
        self._running = True
        logger.info(
            "expiry_checker_started",
            interval_seconds=self._interval,
        )

        while self._running:
            try:
                await self.check_expired_consents()
            except asyncio.CancelledError:
                logger.info("expiry_checker_cancelled")
                break
            except Exception:
                logger.exception("expiry_check_failed")

            try:
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                logger.info("expiry_checker_sleep_cancelled")
                break

    async def check_expired_consents(self) -> int:
        """Query DynamoDB for consents past their expiry date and transition them.

        Performs a table scan filtered to records with status PENDING, SENT,
        or DELIVERED whose ``expires_at`` value is before the current UTC
        time.

        Returns:
            The number of consents that were expired during this check.
        """
        now_iso = datetime.utcnow().isoformat()
        expirable_statuses = [
            ConsentStatus.PENDING.value,
            ConsentStatus.SENT.value,
            ConsentStatus.DELIVERED.value,
        ]

        expired_count = 0
        last_evaluated_key = None

        while True:
            scan_kwargs: dict = {
                "FilterExpression": (
                    "#st IN (:s1, :s2, :s3) AND #exp < :now"
                ),
                "ExpressionAttributeNames": {
                    "#st": "status",
                    "#exp": "expires_at",
                },
                "ExpressionAttributeValues": {
                    ":s1": expirable_statuses[0],
                    ":s2": expirable_statuses[1],
                    ":s3": expirable_statuses[2],
                    ":now": now_iso,
                },
            }

            if last_evaluated_key:
                scan_kwargs["ExclusiveStartKey"] = last_evaluated_key

            response = await self._db.table.scan(**scan_kwargs)
            items = response.get("Items", [])

            for item in items:
                try:
                    consent = from_dynamodb_item(item, ConsentRecord)
                    await self._expire_consent(consent)
                    expired_count += 1
                except Exception:
                    consent_id = item.get("consent_id", "unknown")
                    logger.exception(
                        "consent_expiry_failed",
                        consent_id=consent_id,
                    )

            last_evaluated_key = response.get("LastEvaluatedKey")
            if not last_evaluated_key:
                break

        if expired_count > 0:
            logger.info("expired_consents_processed", count=expired_count)
        else:
            logger.debug("no_expired_consents_found")

        return expired_count

    async def _expire_consent(self, consent: ConsentRecord) -> None:
        """Transition a single consent to EXPIRED and publish the domain event.

        Args:
            consent: The consent record to expire.
        """
        consent_id = consent.consent_id
        key = {"PK": f"CONSENT#{consent_id}", "SK": f"CONSENT#{consent_id}"}
        now_iso = datetime.utcnow().isoformat()

        await self._db.table.update_item(
            Key=key,
            UpdateExpression="SET #st = :expired, #ua = :now",
            ExpressionAttributeNames={
                "#st": "status",
                "#ua": "updated_at",
            },
            ExpressionAttributeValues={
                ":expired": ConsentStatus.EXPIRED.value,
                ":now": now_iso,
            },
        )

        event = create_event(
            event_type="ConsentExpired",
            source="consent-processor",
            payload={
                "consent_id": consent_id,
                "customer_id": consent.customer_id,
                "consent_type": consent.consent_type.value,
                "channel": consent.channel.value,
                "previous_status": consent.status.value,
                "expired_at": now_iso,
            },
        )

        await self._sns.publish_event(
            topic_arn=self._settings.consent_expired_topic_arn,
            event=event,
        )

        logger.info(
            "consent_expired",
            consent_id=consent_id,
            previous_status=consent.status.value,
        )

    async def stop(self) -> None:
        """Signal the periodic loop to stop after the current iteration."""
        self._running = False
        logger.info("expiry_checker_stopping")
