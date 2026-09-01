"""Observability: New Relic log shipping + PagerDuty incident creation."""

from __future__ import annotations

import asyncio
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


def fire_pd_incident(
    cfg: "UnifiedSettings",
    service: str,
    path: str,
    error: str,
    tb: str,
    ui_page: str | None = None,
    ui_action: str | None = None,
    ui_route: str | None = None,
) -> None:
    error_key = f"{service}:{path}"
    now = time.time()
    if now - _pd_last_fired.get(error_key, 0) < _PD_RATE_LIMIT_SECONDS:
        return
    _pd_last_fired[error_key] = now

    ui_lines = ""
    if ui_page or ui_action or ui_route:
        ui_lines = (
            f"\nUI Context:\n"
            f"  Page   : {ui_page or 'unknown'}\n"
            f"  Action : {ui_action or 'unknown'}\n"
            f"  Route  : {ui_route or 'unknown'}\n"
        )

    title = f"[P1-CRITICAL] CMS/{service}: 500 on {path} — {error[:80]}"
    details = (
        f"CRITICAL ERROR — Consent Management System\n\n"
        f"Service   : {service}\n"
        f"Endpoint  : {path}\n"
        f"Error     : {error}\n"
        f"{ui_lines}\n"
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
            try:
                cfg = request.app.state.settings
            except AttributeError:
                from vercel_app.config import UnifiedSettings
                cfg = UnifiedSettings()
                request.app.state.settings = cfg

            # Classify slow requests
            slow = duration_ms > 2000

            # Client IP (Vercel puts real IP in x-forwarded-for)
            client_ip = (
                request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                or request.headers.get("x-real-ip", "")
                or (request.client.host if request.client else "unknown")
            )

            ui_page = request.headers.get("x-ui-page", "") or None
            ui_action = request.headers.get("x-ui-action", "") or None
            ui_route = request.headers.get("x-ui-route", "") or None

            # Build human-readable message including UI context when available
            ui_context = f" | page={ui_page} action={ui_action}" if ui_page or ui_action else ""
            record = {
                "timestamp": int(time.time() * 1000),
                "message": (
                    f"[{'SLOW ' if slow else ''}{level}] "
                    f"{request.method} {request.url.path} → {status} "
                    f"({duration_ms}ms) | {self._service_name} | corr={correlation_id[:8]}"
                    f"{ui_context}"
                ),
                "level": level,
                # Service identity
                "application": "consent-management-system",
                "service": self._service_name,
                "environment": "production",
                # Request details
                "http.method": request.method,
                "http.path": request.url.path,
                "http.query": request.url.query or None,
                "http.host": request.headers.get("host", ""),
                "http.user_agent": request.headers.get("user-agent", ""),
                "http.referer": request.headers.get("referer", "") or None,
                "http.content_type": request.headers.get("content-type", "") or None,
                "http.content_length": request.headers.get("content-length", "") or None,
                "http.client_ip": client_ip,
                # Response details
                "http.status_code": status,
                "http.status_class": f"{status // 100}xx",
                # Performance
                "duration_ms": duration_ms,
                "slow_request": slow,
                # Tracing
                "correlation_id": correlation_id,
                "request_id": str(uuid.uuid4()),
                # UI context (sent by frontend axios interceptor)
                "ui.page": ui_page,
                "ui.action": ui_action,
                "ui.route": ui_route,
            }
            # Remove None values to keep logs clean
            record = {k: v for k, v in record.items() if v is not None}

            await asyncio.to_thread(_send_to_newrelic, cfg.newrelic_license_key, [record])
        except Exception:
            pass

        response.headers["X-Correlation-ID"] = correlation_id
        return response


def register_exception_handlers(app, service_name: str = "cms-unified") -> None:
    from fastapi.responses import JSONResponse

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        tb = traceback.format_exc()
        ui_page = request.headers.get("x-ui-page") or None
        ui_action = request.headers.get("x-ui-action") or None
        ui_route = request.headers.get("x-ui-route") or None
        logger.exception(
            "unhandled_exception",
            error=str(exc),
            path=request.url.path,
            ui_page=ui_page,
            ui_action=ui_action,
        )

        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "An internal error occurred",
                                "correlation_id": get_correlation_id()}},
        )
