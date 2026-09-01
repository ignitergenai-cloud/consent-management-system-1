"""FastAPI application entry point for the Incident Bridge service."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cms_shared.aws.sns import SNSPublisher
from cms_shared.middleware.correlation import CorrelationIdMiddleware
from cms_shared.middleware.error_handler import register_exception_handlers
from cms_shared.middleware.logging_config import setup_logging

from incident_bridge import __version__
from incident_bridge.config import IncidentBridgeSettings
from incident_bridge.consumers.incident_events_consumer import IncidentEventsConsumer
from incident_bridge.consumers.mims_commands_consumer import MIMSCommandsConsumer
from incident_bridge.routers import bridge, health
from incident_bridge.services.bridge_event_log import BridgeEventLog
from incident_bridge.services.command_translator import CommandTranslator
from incident_bridge.services.event_transformer import EventTransformer
from incident_bridge.services.mims_publisher import MIMSPublisher

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle: start and stop all service components.

    Initializes the SNS publisher, event transformer, MIMS publisher,
    command translator, bridge event log, and both SQS consumers on startup.
    Gracefully shuts them all down on application exit.
    """
    settings = IncidentBridgeSettings()
    setup_logging(settings.service_name)

    log = structlog.get_logger("lifespan")
    await log.ainfo("Starting incident-bridge service", version=__version__)

    # Initialize AWS SNS publisher
    sns = SNSPublisher(settings)
    await sns.startup()

    # Initialize core services
    event_transformer = EventTransformer()
    mims_publisher = MIMSPublisher(
        sns_publisher=sns,
        mims_topic_arn=settings.sns_mims_inbound_topic,
    )
    command_translator = CommandTranslator(
        sns_publisher=sns,
        internal_commands_topic_arn=settings.sns_internal_commands_topic,
        transformer=event_transformer,
    )
    bridge_event_log = BridgeEventLog(max_size=settings.max_event_log_size)

    # Initialize SQS consumers
    incident_consumer = IncidentEventsConsumer(
        queue_url=settings.sqs_incident_bridge_queue,
        settings=settings,
        event_transformer=event_transformer,
        mims_publisher=mims_publisher,
        bridge_event_log=bridge_event_log,
    )
    commands_consumer = MIMSCommandsConsumer(
        queue_url=settings.sqs_incident_commands_queue,
        settings=settings,
        command_translator=command_translator,
        bridge_event_log=bridge_event_log,
    )

    await incident_consumer.startup()
    await commands_consumer.startup()

    # Store all components in app state for dependency injection
    app.state.settings = settings
    app.state.sns = sns
    app.state.event_transformer = event_transformer
    app.state.mims_publisher = mims_publisher
    app.state.command_translator = command_translator
    app.state.bridge_event_log = bridge_event_log
    app.state.incident_consumer = incident_consumer
    app.state.commands_consumer = commands_consumer

    # Start both SQS consumers as background asyncio tasks
    incident_task = asyncio.create_task(incident_consumer.start())
    commands_task = asyncio.create_task(commands_consumer.start())
    app.state.incident_consumer_task = incident_task
    app.state.commands_consumer_task = commands_task

    await log.ainfo("Incident-bridge service started successfully")

    yield

    # Shutdown
    await log.ainfo("Shutting down incident-bridge service")

    await incident_consumer.stop()
    incident_task.cancel()
    try:
        await incident_task
    except asyncio.CancelledError:
        pass

    await commands_consumer.stop()
    commands_task.cancel()
    try:
        await commands_task
    except asyncio.CancelledError:
        pass

    await incident_consumer.shutdown()
    await commands_consumer.shutdown()
    await sns.shutdown()

    await log.ainfo("Incident-bridge service shut down successfully")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        FastAPI: The fully configured application instance with all routers,
        middleware, and exception handlers registered.
    """
    app = FastAPI(
        title="Incident Bridge",
        description="Bidirectional bridge between CMS and external MIMS",
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
    app.include_router(bridge.router, prefix="/bridge", tags=["bridge"])

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = IncidentBridgeSettings()
    uvicorn.run(
        "incident_bridge.main:app",
        host="0.0.0.0",
        port=settings.service_port,
        reload=True,
    )
