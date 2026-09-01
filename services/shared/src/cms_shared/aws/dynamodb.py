"""DynamoDB async manager."""

import aioboto3
from contextlib import AsyncExitStack

import structlog

logger = structlog.get_logger()


class DynamoDBManager:
    """Async DynamoDB manager using aioboto3."""

    def __init__(self, settings) -> None:
        self._settings = settings
        self._session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key,
            aws_secret_access_key=settings.aws_secret_key,
            region_name=settings.aws_region,
        )
        self._exit_stack: AsyncExitStack | None = None
        self._resource = None
        self._table = None

    async def startup(self) -> None:
        """Initialize DynamoDB resource and table."""
        self._exit_stack = AsyncExitStack()
        self._resource = await self._exit_stack.enter_async_context(
            self._session.resource(
                "dynamodb",
                endpoint_url=self._settings.aws_endpoint_url,
            )
        )
        self._table = await self._resource.Table(self._settings.dynamodb_table_name)
        logger.info("DynamoDB manager started", table=self._settings.dynamodb_table_name)

    async def shutdown(self) -> None:
        """Close DynamoDB connections."""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._resource = None
            self._table = None
        logger.info("DynamoDB manager shut down")

    @property
    def table(self):
        """Get the DynamoDB table."""
        if self._table is None:
            raise RuntimeError("DynamoDB manager not started. Call startup() first.")
        return self._table

    @property
    def resource(self):
        """Get the DynamoDB resource."""
        if self._resource is None:
            raise RuntimeError("DynamoDB manager not started. Call startup() first.")
        return self._resource
