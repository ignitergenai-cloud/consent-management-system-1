"""FastAPI application entry point for the Consent Processor service.

Wires up DynamoDB, SNS, two SQS consumers (consent events and notification
status), the periodic expiry checker, and the health router inside a
single ``lifespan`` context manager.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cms_shared.aws.dynamodb import DynamoDBManager
from cms_shared.aws.sns import SNSPublisher
from cms_shared.middleware.correlation import CorrelationIdMiddleware
from cms_shared.middleware.error_handler import register_exception_handlers
from cms_shared.middleware.logging_config import setup_logging

from consent_processor import __version__
from consent_processor.config import ConsentProcessorSettings
from consent_processor.consumers.consent_events_consumer import ConsentEventsConsumer
from consent_processor.consumers.notification_status_consumer import NotificationStatusConsumer
from consent_processor.routers import health
from consent_processor.services.consent_workflow import ConsentWorkflow
from consent_processor.services.expiry_checker import ExpiryChecker
from consent_processor.services.notification_orchestrator import NotificationOrchestrator

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle: start and stop all service components.

    Startup sequence:
        1. Load settings and configure structured logging.
        2. Initialise DynamoDB and SNS clients.
        3. Create the domain services (NotificationOrchestrator,
           ConsentWorkflow, ExpiryChecker).
        4. Create and start both SQS consumers as background tasks.
        5. Start the periodic expiry checker as a background task.

    Shutdown sequence:
        1. Signal all consumers and the expiry checker to stop.
        2. Cancel their asyncio tasks and await completion.
        3. Shut down the AWS clients.
    """
    settings = ConsentProcessorSettings()
    setup_logging(settings.service_name)

    logger.info("starting_consent_processor", port=settings.service_port, version=__version__)

    # ── AWS clients ─────────────────────────────────────────────────────
    db = DynamoDBManager(settings)
    await db.startup()

    sns = SNSPublisher(settings)
    await sns.startup()

    # ── Domain services ─────────────────────────────────────────────────
    notification_orchestrator = NotificationOrchestrator(sns=sns, settings=settings)

    workflow = ConsentWorkflow(
        db=db,
        sns=sns,
        notification_orchestrator=notification_orchestrator,
        settings=settings,
    )

    expiry_checker = ExpiryChecker(db=db, sns=sns, settings=settings)

    # ── SQS consumers ──────────────────────────────────────────────────
    consent_events_consumer = ConsentEventsConsumer(settings=settings, workflow=workflow)
    await consent_events_consumer.startup()

    notification_status_consumer = NotificationStatusConsumer(settings=settings, workflow=workflow)
    await notification_status_consumer.startup()

    # Launch consumers and expiry checker as background tasks
    consent_events_task = asyncio.create_task(consent_events_consumer.start())
    notification_status_task = asyncio.create_task(notification_status_consumer.start())
    expiry_task = asyncio.create_task(expiry_checker.start())

    # ── Store in app state for dependency injection ─────────────────────
    app.state.settings = settings
    app.state.db = db
    app.state.sns = sns
    app.state.workflow = workflow
    app.state.notification_orchestrator = notification_orchestrator
    app.state.expiry_checker = expiry_checker
    app.state.consent_events_consumer = consent_events_consumer
    app.state.notification_status_consumer = notification_status_consumer

    logger.info("consent_processor_started")

    yield

    # ── Shutdown ────────────────────────────────────────────────────────
    logger.info("shutting_down_consent_processor")

    # Stop the periodic checker and consumers
    await expiry_checker.stop()
    await consent_events_consumer.stop()
    await notification_status_consumer.stop()

    # Cancel background tasks
    for task in (consent_events_task, notification_status_task, expiry_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Tear down SQS clients
    await consent_events_consumer.shutdown()
    await notification_status_consumer.shutdown()

    # Tear down core AWS clients
    await sns.shutdown()
    await db.shutdown()

    logger.info("consent_processor_stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        The fully configured :class:`FastAPI` instance with middleware,
        exception handlers, and routers registered.
    """
    app = FastAPI(
        title="Consent Processor",
        description="Consent Management System - Consent Processor Service",
        version=__version__,
        lifespan=lifespan,
    )

    # Middleware -- order matters (last added = first executed)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CorrelationIdMiddleware)

    # Error handlers
    register_exception_handlers(app)

    # Routers
    app.include_router(health.router, tags=["health"])

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = ConsentProcessorSettings()
    uvicorn.run(
        "consent_processor.main:app",
        host="0.0.0.0",
        port=settings.service_port,
        reload=True,
    )
