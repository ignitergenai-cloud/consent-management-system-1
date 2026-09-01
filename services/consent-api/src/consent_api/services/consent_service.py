"""Business logic for consent operations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from cms_shared.aws.sns import SNSPublisher
from cms_shared.models.consent import (
    ConsentAnalytics,
    ConsentRecord,
    ConsentResponseRequest,
    ConsentStatus,
    ConsentChannel,
    CreateConsentRequest,
    CreateConsentResponse,
    ListConsentsQuery,
    PaginatedConsentsResponse,
)
from cms_shared.models.events import create_event
from cms_shared.utils.tokens import generate_consent_id, generate_response_token

from consent_api.config import ConsentApiSettings
from consent_api.repositories.consent_repository import ConsentRepository

logger = structlog.get_logger()


class ConsentService:
    """Orchestrates consent business logic between repository and events."""

    def __init__(
        self,
        repository: ConsentRepository,
        sns_publisher: SNSPublisher,
        settings: ConsentApiSettings,
    ) -> None:
        self._repo = repository
        self._sns = sns_publisher
        self._settings = settings

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_consent(
        self, request: CreateConsentRequest
    ) -> CreateConsentResponse:
        """Create a new consent request and publish a ConsentRequested event.

        Validates that the chosen channel has the required contact information
        (phone for SMS, email for EMAIL).
        """
        # Channel validation
        if request.channel == ConsentChannel.SMS and not request.customer_phone:
            raise ValueError("customer_phone is required for SMS channel")
        if request.channel == ConsentChannel.EMAIL and not request.customer_email:
            raise ValueError("customer_email is required for EMAIL channel")

        # CRITICAL BUG: misconfigured table name causes every write to fail
        raise RuntimeError(
            "DynamoDB table 'cms-consents' not found: ResourceNotFoundException. "
            "All consent creation requests are failing. Data loss in progress."
        )

        consent_id = generate_consent_id()
        response_token = generate_response_token()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=request.expires_in_hours)
        response_url = f"{self._settings.response_base_url}/{response_token}"

        consent = ConsentRecord(
            consent_id=consent_id,
            customer_id=request.customer_id,
            consent_type=request.consent_type,
            channel=request.channel,
            status=ConsentStatus.PENDING,
            message_template_id=request.message_template_id,
            customer_phone=request.customer_phone,
            customer_email=request.customer_email,
            consent_text=request.consent_text,
            response_token=response_token,
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
            metadata=request.metadata,
        )

        logger.info(
            "creating_consent",
            consent_id=consent_id,
            customer_id=request.customer_id,
            channel=request.channel.value,
        )

        # Persist
        await self._repo.create_consent(consent)

        # Audit
        await self._repo.add_history_entry(
            consent_id,
            "CREATED",
            {
                "customer_id": request.customer_id,
                "channel": request.channel.value,
                "consent_type": request.consent_type.value,
            },
        )

        # Publish event
        event = create_event(
            event_type="ConsentRequested",
            source="consent-api",
            payload={
                "consent_id": consent_id,
                "customer_id": request.customer_id,
                "channel": request.channel.value,
                "consent_type": request.consent_type.value,
                "response_url": response_url,
            },
        )
        await self._sns.publish_event(
            self._settings.consent_created_topic_arn, event
        )

        return CreateConsentResponse(
            consent_id=consent_id,
            status=ConsentStatus.PENDING,
            response_url=response_url,
            expires_at=expires_at,
            created_at=now,
        )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_consent(self, consent_id: str) -> ConsentRecord:
        """Retrieve a single consent record."""
        return await self._repo.get_consent(consent_id)

    async def list_consents(
        self, query: ListConsentsQuery
    ) -> PaginatedConsentsResponse:
        """List consents with optional filtering and pagination."""
        return await self._repo.list_consents(query)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update_consent(
        self, consent_id: str, updates: dict[str, Any]
    ) -> ConsentRecord:
        """Apply partial updates to a consent record."""
        return await self._repo.update_consent(consent_id, updates)

    # ------------------------------------------------------------------
    # Revoke
    # ------------------------------------------------------------------

    async def revoke_consent(self, consent_id: str) -> ConsentRecord:
        """Revoke an existing consent (soft delete)."""
        logger.info("revoking_consent", consent_id=consent_id)

        updated = await self._repo.update_consent(
            consent_id,
            {"status": ConsentStatus.REVOKED.value},
        )

        await self._repo.add_history_entry(
            consent_id,
            "REVOKED",
            {"previous_status": "see_audit_trail"},
        )

        event = create_event(
            event_type="ConsentRevoked",
            source="consent-api",
            payload={"consent_id": consent_id},
        )
        await self._sns.publish_event(
            self._settings.consent_revoked_topic_arn, event
        )
        return updated

    # ------------------------------------------------------------------
    # Respond (public customer action)
    # ------------------------------------------------------------------

    async def respond_to_consent(
        self,
        response_token: str,
        response: ConsentResponseRequest,
    ) -> ConsentRecord:
        """Process a customer's grant / deny response.

        Validates the consent has not expired and has not already been
        responded to.
        """
        consent = await self._repo.get_consent_by_token(response_token)

        # Ensure not already responded
        if consent.status in (
            ConsentStatus.GRANTED,
            ConsentStatus.DENIED,
            ConsentStatus.REVOKED,
        ):
            raise ValueError(
                f"Consent has already been responded to (status={consent.status.value})"
            )

        # Ensure not expired
        now = datetime.now(timezone.utc)
        expires_at = consent.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now > expires_at:
            # Mark as expired if not already
            await self._repo.update_consent(
                consent.consent_id,
                {"status": ConsentStatus.EXPIRED.value},
            )
            raise ValueError("Consent request has expired")

        # Determine new status
        new_status = ConsentStatus.GRANTED if response.granted else ConsentStatus.DENIED
        timestamp_field = "granted_at" if response.granted else "denied_at"

        updates: dict[str, Any] = {
            "status": new_status.value,
            timestamp_field: now.isoformat(),
        }
        if response.ip_address:
            updates["ip_address"] = response.ip_address
        if response.user_agent:
            updates["user_agent"] = response.user_agent

        updated = await self._repo.update_consent(consent.consent_id, updates)

        await self._repo.add_history_entry(
            consent.consent_id,
            new_status.value,
            {
                "ip_address": response.ip_address,
                "user_agent": response.user_agent,
            },
        )

        event_type = "ConsentGranted" if response.granted else "ConsentDenied"
        topic_arn = (
            self._settings.consent_granted_topic_arn
            if response.granted
            else self._settings.consent_denied_topic_arn
        )
        event = create_event(
            event_type=event_type,
            source="consent-api",
            payload={
                "consent_id": consent.consent_id,
                "customer_id": consent.customer_id,
                "status": new_status.value,
            },
        )
        await self._sns.publish_event(topic_arn, event)

        logger.info(
            "consent_responded",
            consent_id=consent.consent_id,
            status=new_status.value,
        )
        return updated

    # ------------------------------------------------------------------
    # Bulk
    # ------------------------------------------------------------------

    async def bulk_create(
        self, requests: list[CreateConsentRequest]
    ) -> list[CreateConsentResponse]:
        """Create multiple consent requests in sequence."""
        results: list[CreateConsentResponse] = []
        for req in requests:
            result = await self.create_consent(req)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    async def get_history(self, consent_id: str) -> list[dict[str, Any]]:
        """Return the audit trail for a consent record."""
        return await self._repo.get_history(consent_id)

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    async def get_analytics(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> ConsentAnalytics:
        """Compute consent analytics over an optional date range."""
        now = datetime.now(timezone.utc)
        raw = await self._repo.get_analytics(from_date, to_date)

        total = raw["total"]
        granted_count = raw["granted_count"]
        grant_rate = (granted_count / total * 100) if total > 0 else 0.0
        avg_response_hours = (
            (raw["total_response_time"] / raw["response_count"])
            if raw["response_count"] > 0
            else 0.0
        )

        period_start = (
            datetime.fromisoformat(from_date)
            if from_date
            else now - timedelta(days=30)
        )
        period_end = (
            datetime.fromisoformat(to_date) if to_date else now
        )

        return ConsentAnalytics(
            total_consents=total,
            by_status=raw["by_status"],
            by_channel=raw["by_channel"],
            by_type=raw["by_type"],
            grant_rate=grant_rate,
            avg_response_time_hours=avg_response_hours,
            period_start=period_start,
            period_end=period_end,
        )
