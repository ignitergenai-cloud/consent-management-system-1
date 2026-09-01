"""FastAPI application entry-point for the Incident Detector service."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI

from cms_shared.aws.dynamodb import DynamoDBManager
from cms_shared.aws.sns import SNSPublisher
from cms_shared.middleware.correlation import CorrelationIdMiddleware
from cms_shared.middleware.error_handler import register_exception_handlers
from cms_shared.middleware.logging_config import setup_logging
from cms_shared.middleware.newrelic import NewRelicLoggingMiddleware

from incident_detector.config import IncidentDetectorSettings
from incident_detector.consumers.consent_events_consumer import ConsentEventsConsumer
from incident_detector.routers import health, incidents, metrics
from incident_detector.rules.error_spike_rule import ErrorSpikeRule
from incident_detector.rules.failure_rate_rule import FailureRateRule
from incident_detector.rules.throughput_rule import ThroughputDropRule
from incident_detector.services.anomaly_detector import AnomalyDetector
from incident_detector.services.incident_manager import IncidentManager
from incident_detector.services.metric_collector import MetricCollector

logger = structlog.get_logger(__name__)


async def _detection_loop(
    detector: AnomalyDetector,
    collector: MetricCollector,
    manager: IncidentManager,
    interval_seconds: int,
) -> None:
    """Periodically collect metrics, run anomaly detection, and create
    incidents for any anomalies found.
    """
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            current_metrics = collector.get_metrics()

            logger.debug("detection_cycle", metrics=current_metrics)

            anomalies = detector.detect(current_metrics)
            for anomaly in anomalies:
                await manager.create_incident(anomaly)

        except asyncio.CancelledError:
            logger.info("detection_loop_cancelled")
            break
        except Exception:
            logger.exception("detection_loop_error")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle -- start and stop infrastructure."""
    settings = IncidentDetectorSettings()
    setup_logging(settings.service_name)

    # -- AWS clients --
    dynamo = DynamoDBManager(settings)
    await dynamo.startup()

    sns = SNSPublisher(settings)
    await sns.startup()

    # -- Core services --
    collector = MetricCollector(window_minutes=settings.detection_window_minutes)

    rules = [
        FailureRateRule(threshold=settings.failure_rate_threshold),
        ThroughputDropRule(threshold=settings.throughput_drop_threshold),
        ErrorSpikeRule(multiplier=settings.error_spike_multiplier),
    ]
    detector = AnomalyDetector(rules=rules)

    manager = IncidentManager(dynamo=dynamo, sns=sns, settings=settings)

    # -- SQS consumer --
    consumer = ConsentEventsConsumer(
        settings=settings,
        metric_collector=collector,
    )
    await consumer.startup()
    consumer_task = asyncio.create_task(consumer.start())

    # -- Periodic detection loop --
    detection_task = asyncio.create_task(
        _detection_loop(
            detector=detector,
            collector=collector,
            manager=manager,
            interval_seconds=settings.detection_interval_seconds,
        )
    )

    # -- Expose on app.state for dependency injection --
    app.state.settings = settings
    app.state.dynamo_manager = dynamo
    app.state.sns_publisher = sns
    app.state.metric_collector = collector
    app.state.anomaly_detector = detector
    app.state.incident_manager = manager

    logger.info("incident_detector_started")

    yield

    # -- Shutdown --
    logger.info("incident_detector_shutting_down")

    detection_task.cancel()
    await consumer.stop()
    consumer_task.cancel()

    try:
        await detection_task
    except asyncio.CancelledError:
        pass
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass

    await sns.shutdown()
    await dynamo.shutdown()

    logger.info("incident_detector_stopped")


def create_app() -> FastAPI:
    """Factory function that builds and returns the configured FastAPI app."""
    app = FastAPI(
        title="Incident Detector",
        description="Anomaly detection and incident management for the Consent Management System",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware
    
    app.add_middleware(NewRelicLoggingMiddleware, service_name="incident-detector")
    register_exception_handlers(app, service_name="incident-detector")

    # Routers
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(metrics.router, prefix="/api/v1")
    app.include_router(incidents.router, prefix="/api/v1")

    return app


app = create_app()
