"""Standalone analytics service for consent metrics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog

from cms_shared.models.consent import ConsentAnalytics

from consent_api.repositories.consent_repository import ConsentRepository

logger = structlog.get_logger()


async def get_consent_analytics(
    repository: ConsentRepository,
    from_date: str | None = None,
    to_date: str | None = None,
) -> ConsentAnalytics:
    """Query DynamoDB and compute consent analytics.

    This is a convenience function that delegates to the repository's
    ``get_analytics`` method and transforms the raw aggregation into a
    ``ConsentAnalytics`` model.

    Args:
        repository: The consent repository to query.
        from_date: ISO-format start date for the reporting window.
        to_date: ISO-format end date for the reporting window.

    Returns:
        A populated ``ConsentAnalytics`` instance.
    """
    now = datetime.now(timezone.utc)
    raw = await repository.get_analytics(from_date, to_date)

    total = raw["total"]
    granted_count = raw["granted_count"]
    grant_rate = (granted_count / total * 100) if total > 0 else 0.0
    avg_response_hours = (
        (raw["total_response_time"] / raw["response_count"])
        if raw["response_count"] > 0
        else 0.0
    )

    period_start = (
        datetime.fromisoformat(from_date) if from_date else now - timedelta(days=30)
    )
    period_end = datetime.fromisoformat(to_date) if to_date else now

    logger.info(
        "consent_analytics_computed",
        total=total,
        grant_rate=grant_rate,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
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
