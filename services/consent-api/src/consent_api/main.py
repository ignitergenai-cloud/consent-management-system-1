"""FastAPI application entry point for the Consent API."""

import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cms_shared.aws.dynamodb import DynamoDBManager
from cms_shared.aws.sns import SNSPublisher
from cms_shared.middleware.correlation import CorrelationIdMiddleware
from cms_shared.middleware.error_handler import register_exception_handlers
from cms_shared.middleware.logging_config import setup_logging

from consent_api.config import ConsentApiSettings
from consent_api.consumers.internal_commands_consumer import InternalCommandsConsumer
from consent_api.routers import analytics, consents, customers, health, response

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown of application resources."""
    settings = ConsentApiSettings()
    setup_logging(settings.service_name)

    logger.info("starting_consent_api", port=settings.service_port)

    # Initialize AWS managers
    dynamo_manager = DynamoDBManager(settings)
    sns_publisher = SNSPublisher(settings)
    commands_consumer = InternalCommandsConsumer(
        queue_url=settings.internal_commands_queue_url,
        settings=settings,
    )

    await dynamo_manager.startup()
    await sns_publisher.startup()
    await commands_consumer.startup()

    # Start SQS consumer in background
    consumer_task = asyncio.create_task(commands_consumer.start())

    # Store in app state
    app.state.settings = settings
    app.state.dynamo_manager = dynamo_manager
    app.state.sns_publisher = sns_publisher
    app.state.commands_consumer = commands_consumer

    logger.info("consent_api_started")

    yield

    # Shutdown
    logger.info("shutting_down_consent_api")
    await commands_consumer.stop()
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    await commands_consumer.shutdown()
    await sns_publisher.shutdown()
    await dynamo_manager.shutdown()
    logger.info("consent_api_stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Consent Management API",
        description="Core REST API for the Consent Management System",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware — order matters (last added = first executed)
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
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(consents.router, prefix="/api/v1", tags=["consents"])
    app.include_router(response.router, prefix="/api/v1", tags=["consent-response"])
    app.include_router(customers.router, prefix="/api/v1", tags=["customers"])
    app.include_router(analytics.router, prefix="/api/v1", tags=["analytics"])

    return app


app = create_app()
