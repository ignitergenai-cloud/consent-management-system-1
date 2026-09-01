"""Global exception handler for FastAPI services.

On any unhandled 500 error, automatically fires a PagerDuty P1 incident
(rate-limited to one incident per error type per 5 minutes).
"""

from __future__ import annotations

import json
import time
import traceback
import urllib.request
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from cms_shared.middleware.correlation import get_correlation_id

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# PagerDuty config
# ---------------------------------------------------------------------------
_PD_TOKEN = "u+2Kf6xufQUhr1CLJsBw"
_PD_SERVICE_ID = "PUMAG77"
_PD_PRIORITY_P1 = "P9VA1XZ"
_PD_ESCALATION_ID = "P0Z7O6F"
_PD_FROM = "gaurav.chandak@tcs.com"
_PD_RATE_LIMIT_SECONDS = 300  # 5 minutes between incidents for same error key

# in-memory rate-limit store: {error_key: last_fired_epoch}
_pd_last_fired: dict[str, float] = {}


def _fire_pd_incident(service: str, path: str, error: str, tb: str) -> None:
    """Create a PagerDuty P1 incident for a real 500 error (never raises)."""
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
    body: dict[str, Any] = {
        "incident": {
            "type": "incident",
            "title": title,
            "service": {"id": _PD_SERVICE_ID, "type": "service_reference"},
            "urgency": "high",
            "priority": {"id": _PD_PRIORITY_P1, "type": "priority_reference"},
            "escalation_policy": {"id": _PD_ESCALATION_ID, "type": "escalation_policy_reference"},
            "body": {"type": "incident_body", "details": details},
        }
    }
    try:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            "https://api.pagerduty.com/incidents",
            data=data,
            headers={
                "Authorization": f"Token token={_PD_TOKEN}",
                "Accept": "application/vnd.pagerduty+json;version=2",
                "Content-Type": "application/json",
                "From": _PD_FROM,
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=8)
        logger.warning(
            "pagerduty_incident_created",
            service=service,
            path=path,
            error=error,
        )
    except Exception as exc:
        logger.error("pagerduty_incident_failed", error=str(exc))


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class ItemNotFoundError(Exception):
    def __init__(self, message: str = "Item not found") -> None:
        self.message = message
        super().__init__(self.message)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    correlation_id = get_correlation_id()
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "correlation_id": correlation_id}},
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_exception_handlers(app: FastAPI, service_name: str = "consent-api") -> None:
    """Register global exception handlers. Pass service_name for PD incidents."""

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        logger.warning("validation_error", error=str(exc), path=request.url.path)
        return _error_response(400, "BAD_REQUEST", str(exc))

    @app.exception_handler(KeyError)
    async def key_error_handler(request: Request, exc: KeyError) -> JSONResponse:
        logger.warning("key_not_found", error=str(exc), path=request.url.path)
        return _error_response(404, "NOT_FOUND", f"Resource not found: {exc}")

    @app.exception_handler(ItemNotFoundError)
    async def item_not_found_handler(request: Request, exc: ItemNotFoundError) -> JSONResponse:
        logger.warning("item_not_found", error=exc.message, path=request.url.path)
        return _error_response(404, "NOT_FOUND", exc.message)

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        tb = traceback.format_exc()
        logger.exception("unhandled_exception", error=str(exc), path=request.url.path)

        # Auto-fire PagerDuty incident (runs synchronously but is fast + rate-limited)
        import threading
        threading.Thread(
            target=_fire_pd_incident,
            args=(service_name, request.url.path, str(exc), tb),
            daemon=True,
        ).start()

        return _error_response(500, "INTERNAL_ERROR", "An internal error occurred")
