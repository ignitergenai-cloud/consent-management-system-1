"""New Relic log-shipping middleware.

Ships one structured log record to New Relic for every HTTP request,
without blocking the response path (fire-and-forget via thread executor).
"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.request
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from cms_shared.middleware.correlation import get_correlation_id

NR_LICENSE_KEY = "350ed5b6c2fb675958bb75486c57c570679dNRAL"
NR_LOG_URL = "https://log-api.newrelic.com/log/v1"
_NR_HEADERS = {
    "Api-Key": NR_LICENSE_KEY,
    "Content-Type": "application/json",
}

_SKIP_PATHS = {"/health", "/health/ready", "/metrics"}


def _send(payload: list[dict]) -> None:
    """Send log batch to New Relic (runs in a thread pool, never raises)."""
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            NR_LOG_URL, data=data, headers=_NR_HEADERS, method="POST"
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


class NewRelicLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request + response to New Relic Logs.

    Instantiate with a service_name:
        app.add_middleware(NewRelicLoggingMiddleware, service_name="consent-api")
    """

    def __init__(self, app, service_name: str = "unknown") -> None:
        super().__init__(app)
        self._service_name = service_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        status = response.status_code
        level = "ERROR" if status >= 500 else "WARNING" if status >= 400 else "INFO"

        record = {
            "timestamp": int(time.time() * 1000),
            "message": f"{request.method} {request.url.path} -> {status} ({duration_ms}ms)",
            "level": level,
            "application": "consent-management-system",
            "service": self._service_name,
            "environment": "production",
            "method": request.method,
            "path": request.url.path,
            "status_code": status,
            "duration_ms": duration_ms,
            "correlation_id": get_correlation_id(),
        }
        if request.url.query:
            record["query"] = request.url.query

        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _send, [record])

        return response
