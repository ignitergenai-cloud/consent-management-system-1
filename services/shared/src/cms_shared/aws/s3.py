"""S3 helper client."""

from contextlib import AsyncExitStack

import aioboto3
import structlog

logger = structlog.get_logger()


class S3Client:
    """Async S3 client."""

    def __init__(self, settings) -> None:
        self._settings = settings
        self._session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key,
            aws_secret_access_key=settings.aws_secret_key,
            region_name=settings.aws_region,
        )
        self._exit_stack: AsyncExitStack | None = None
        self._client = None

    async def startup(self) -> None:
        """Initialize S3 client."""
        self._exit_stack = AsyncExitStack()
        self._client = await self._exit_stack.enter_async_context(
            self._session.client(
                "s3",
                endpoint_url=self._settings.aws_endpoint_url,
            )
        )
        logger.info("S3 client started")

    async def shutdown(self) -> None:
        """Close S3 connections."""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._client = None
        logger.info("S3 client shut down")

    async def upload_file(
        self,
        bucket: str,
        key: str,
        body: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a file to S3.

        Args:
            bucket: S3 bucket name.
            key: S3 object key.
            body: File content as bytes.
            content_type: MIME content type.

        Returns:
            The S3 object URL.
        """
        if self._client is None:
            raise RuntimeError("S3 client not started. Call startup() first.")

        await self._client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )
        url = f"s3://{bucket}/{key}"
        logger.info("File uploaded to S3", bucket=bucket, key=key)
        return url

    async def get_file(self, bucket: str, key: str) -> bytes:
        """Download a file from S3.

        Args:
            bucket: S3 bucket name.
            key: S3 object key.

        Returns:
            File content as bytes.
        """
        if self._client is None:
            raise RuntimeError("S3 client not started. Call startup() first.")

        response = await self._client.get_object(Bucket=bucket, Key=key)
        content = await response["Body"].read()
        logger.info("File downloaded from S3", bucket=bucket, key=key)
        return content

    async def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate a presigned URL for an S3 object.

        Args:
            bucket: S3 bucket name.
            key: S3 object key.
            expires_in: URL expiration time in seconds.

        Returns:
            The presigned URL string.
        """
        if self._client is None:
            raise RuntimeError("S3 client not started. Call startup() first.")

        url = await self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        logger.info("Presigned URL generated", bucket=bucket, key=key, expires_in=expires_in)
        return url
