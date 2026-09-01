"""Metrics endpoint for the Incident Detector service."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from incident_detector.dependencies import get_metric_collector
from incident_detector.services.metric_collector import MetricCollector

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def get_metrics(
    collector: MetricCollector = Depends(get_metric_collector),
) -> dict:
    """Return the current detection-window metrics snapshot."""
    return collector.get_metrics()
