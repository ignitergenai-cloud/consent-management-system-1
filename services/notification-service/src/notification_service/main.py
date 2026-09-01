"""FastAPI application entry point for the Notification Service."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cms_shared.aws.dynamodb import DynamoDBManager
from cms_shared.aws.ses import SESClient
from cms_shared.aws.sns import SNSPublisher
from cms_shared.middleware import (
    CorrelationIdMiddleware,
    register_exception_handlers,
    setup_logging,
)

from notification_service import __version__
from notification_service.config import NotificationServiceSettings
from notification_service.consumers.notification_consumer import NotificationConsumer
from notification_service.routers import health, notifications, templates
from notification_service.services.template_engine import TemplateEngine

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle: start and stop all service components.

    Initializes DynamoDB, SNS, SES clients and the SQS notification consumer
    on startup, and gracefully shuts them all down on application exit.
    """
    settings = NotificationServiceSettings()
    setup_logging(settings.service_name)

    log = structlog.get_logger("lifespan")
    await log.ainfo("Starting notification service", version=__version__)

    # Initialize AWS clients
    db = DynamoDBManager(settings)
    await db.startup()

    sns = SNSPublisher(settings)
    await sns.startup()

    ses = SESClient(settings)
    await ses.startup()

    # Initialize template engine
    template_engine = TemplateEngine()

    # Initialize SQS consumer
    consumer = NotificationConsumer(
        queue_url=settings.notification_queue_url,
        settings=settings,
        db=db,
        sns=sns,
        ses=ses,
        template_engine=template_engine,
    )

    # Start the SQS consumer client
    await consumer.startup()

    # Store components in app state for dependency injection
    app.state.settings = settings
    app.state.db = db
    app.state.sns = sns
    app.state.ses = ses
    app.state.template_engine = template_engine
    app.state.consumer = consumer

    # Start the SQS consumer as a background task
    consumer_task = asyncio.create_task(consumer.start())
    app.state.consumer_task = consumer_task

    await log.ainfo("Notification service started successfully")

    yield

    # Shutdown
    await log.ainfo("Shutting down notification service")

    await consumer.stop()
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass

    await consumer.shutdown()
    await ses.shutdown()
    await sns.shutdown()
    await db.shutdown()

    await log.ainfo("Notification service shut down successfully")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        FastAPI: The fully configured application instance with all routers,
        middleware, and exception handlers registered.
    """
    app = FastAPI(
        title="Notification Service",
        description="Consent Management System - Notification Service",
        version=__version__,
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add correlation ID middleware
    app.add_middleware(CorrelationIdMiddleware)

    # Register exception handlers
    register_exception_handlers(app)

    # Include routers
    app.include_router(health.router, tags=["health"])
    app.include_router(templates.router, prefix="/templates", tags=["templates"])
    app.include_router(
        notifications.router, prefix="/notifications", tags=["notifications"]
    )

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = NotificationServiceSettings()
    uvicorn.run(
        "notification_service.main:app",
        host="0.0.0.0",
        port=settings.service_port,
        reload=True,
    )
