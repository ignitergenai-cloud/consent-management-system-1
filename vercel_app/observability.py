"""Observability: New Relic log shipping + PagerDuty incident creation."""

from __future__ import annotations

import json
import time
import traceback
import urllib.request
import uuid
from contextvars import ContextVar
from typing import TYPE_CHECKING, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

if TYPE_CHECKING:
    from vercel_app.config import UnifiedSettings

logger = structlog.get_logger()

_NR_LOG_URL = "https://log-api.newrelic.com/log/v1"
_SKIP_PATHS = {"/api/v1/health"}
_PD_RATE_LIMIT_SECONDS = 300
_pd_last_fired: dict[str, float] = {}

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    return correlation_id_var.get()


def _send_to_newrelic(license_key: str, payload: list[dict]) -> None:
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            _NR_LOG_URL,
            data=data,
            headers={"Api-Key": license_key, "Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def _fire_pd_incident(cfg: "UnifiedSettings", service: str, path: str, error: str, tb: str) -> None:
    error_key = f"{service}:{path}"
    now = time.time()
    if now - _pd_last_fired.get(error_key, 0) < _PD_RATE_LIMIT_SECONDS:
        return
    _pd_last_fired[error_key] = now

    title = f"[P1-CRITICAL] CMS/{service}: 500 on {path} — {error[:80]}"
    details = (
        f"CRITICAL ERROR — Consent Management System\n\n"
        f"Service   : {service}\n"
        f"Endpoint  : {path}\n"
        f"Error     : {error}\n\n"
        f"Stack Trace:\n{tb}\n\n"
        f"Application : consent-management-system\n"
        f"Environment : production\n"
        f"Severity    : P1"
    )
    body = {
        "incident": {
            "type": "incident",
            "title": title,
            "service": {"id": cfg.pagerduty_service_id, "type": "service_reference"},
            "urgency": "high",
            "priority": {"id": cfg.pagerduty_priority_id, "type": "priority_reference"},
            "escalation_policy": {"id": cfg.pagerduty_escalation_id, "type": "escalation_policy_reference"},
            "body": {"type": "incident_body", "details": details},
        }
    }
    try:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            "https://api.pagerduty.com/incidents",
            data=data,
            headers={
                "Authorization": f"Token token={cfg.pagerduty_api_token}",
                "Accept": "application/vnd.pagerduty+json;version=2",
                "Content-Type": "application/json",
                "From": cfg.pagerduty_from_email,
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=8)
        logger.warning("pagerduty_incident_created", service=service, path=path)
    except Exception as exc:
        logger.error("pagerduty_incident_failed", error=str(exc))


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Log every request to New Relic; fire PagerDuty P1 on 5xx."""

    def __init__(self, app, service_name: str = "cms-unified") -> None:
        super().__init__(app)
        self._service_name = service_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        correlation_id_var.set(correlation_id)

        if request.url.path in _SKIP_PATHS:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            return response

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        status = response.status_code
        level = "ERROR" if status >= 500 else "WARNING" if status >= 400 else "INFO"

        try:
            cfg = request.app.state.settings
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
                "correlation_id": correlation_id,
            }
            if request.url.query:
                record["query"] = request.url.query

            import threading
            threading.Thread(
                target=_send_to_newrelic,
                args=(cfg.newrelic_license_key, [record]),
                daemon=True,
            ).start()
        except Exception:
            pass

        response.headers["X-Correlation-ID"] = correlation_id
        return response


def register_exception_handlers(app, service_name: str = "cms-unified") -> None:
    from fastapi.responses import JSONResponse

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        tb = traceback.format_exc()
        logger.exception("unhandled_exception", error=str(exc), path=request.url.path)

        try:
            cfg = request.app.state.settings
            import threading
            threading.Thread(
                target=_fire_pd_incident,
                args=(cfg, service_name, request.url.path, str(exc), tb),
                daemon=True,
            ).start()
        except Exception:
            pass

        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "An internal error occurred",
                                "correlation_id": get_correlation_id()}},
        )
