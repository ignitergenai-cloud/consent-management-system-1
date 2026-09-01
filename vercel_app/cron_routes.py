"""CMS cron endpoints — process DB queues, expire consents, detect anomalies."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from vercel_app.db import SupabaseDB
from vercel_app.email import send_email
from vercel_app.config import UnifiedSettings

logger = structlog.get_logger()
router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db(request: Request) -> SupabaseDB:
    return request.app.state.db


def _cfg(request: Request) -> UnifiedSettings:
    return request.app.state.settings


def _check_cron_secret(request: Request) -> bool:
    cfg = _cfg(request)
    if not cfg.cron_secret:
        return True  # not configured — allow (dev mode)
    auth = request.headers.get("authorization", "")
    return auth == f"Bearer {cfg.cron_secret}"


# ──────────────────────────────────────────────────────────────────────
# Send pending notifications (email)
# ──────────────────────────────────────────────────────────────────────

@router.get("/api/cron/process-notifications")
async def process_notifications(request: Request):
    if not _check_cron_secret(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    db = _db(request)
    cfg = _cfg(request)

    rows = await db.select(
        "cms_notification_queue",
        limit=20,
        status="eq.pending",
        order="created_at.asc",
    )

    processed = 0
    errors = 0
    for row in rows:
        nid = row["id"]
        channel = row.get("channel", "EMAIL")
        recipient = row.get("recipient", "")
        subject = row.get("subject") or "Consent Request"
        body_text = row.get("body") or "Please respond to your consent request."
        consent_id = row.get("consent_id", "")

        if channel == "EMAIL" and recipient and "@" in recipient:
            html = f"<p>{body_text}</p><p>Consent ID: {consent_id}</p>"
            msg_id = await send_email(
                api_key=cfg.resend_api_key,
                to=recipient,
                subject=subject,
                html=html,
                from_email=cfg.from_email,
            )
            success = msg_id is not None
        else:
            # SMS: log only (no SMS provider configured)
            logger.info("sms_notification_skipped", recipient=recipient, consent_id=consent_id)
            success = True

        if success:
            await db.update(
                "cms_notification_queue",
                {"status": "sent", "processed_at": _now_iso()},
                id=f"eq.{nid}",
            )
            processed += 1
        else:
            await db.update(
                "cms_notification_queue",
                {"attempts": row.get("attempts", 0) + 1},
                id=f"eq.{nid}",
            )
            errors += 1

    return {"processed": processed, "errors": errors}


# ──────────────────────────────────────────────────────────────────────
# Expire consents past their expiry date
# ──────────────────────────────────────────────────────────────────────

@router.get("/api/cron/check-expired-consents")
async def check_expired_consents(request: Request):
    if not _check_cron_secret(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    db = _db(request)
    now = _now_iso()
    rows = await db.select(
        "consents",
        columns="consent_id",
        status="eq.PENDING",
        expires_at=f"lt.{now}",
        limit=100,
    )

    expired = 0
    for row in rows:
        await db.update(
            "consents",
            {"status": "EXPIRED", "updated_at": now},
            consent_id=f"eq.{row['consent_id']}",
        )
        expired += 1

    return {"expired": expired, "checked_at": now}


# ──────────────────────────────────────────────────────────────────────
# Anomaly detection (simple threshold check on consent metrics)
# ──────────────────────────────────────────────────────────────────────

@router.get("/api/cron/detect-anomalies")
async def detect_anomalies(request: Request):
    if not _check_cron_secret(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    db = _db(request)
    cfg = _cfg(request)

    # Count consents by status in last 15 minutes
    window_start = datetime.now(timezone.utc)
    window_start = window_start.replace(
        minute=window_start.minute - 15 if window_start.minute >= 15 else 0
    )
    ws_iso = window_start.isoformat()

    rows = await db.select(
        "consents",
        columns="status",
        created_at=f"gt.{ws_iso}",
        limit=1000,
    )

    total = len(rows)
    failed = sum(1 for r in rows if r["status"] in ("FAILED", "EXPIRED"))
    failure_rate = failed / total if total > 0 else 0.0

    incidents_created = 0
    if total > 0 and failure_rate > cfg.failure_rate_threshold:
        incident_id = str(uuid.uuid4())
        await db.insert("cms_incidents", {
            "incident_id": incident_id,
            "type": "HIGH_FAILURE_RATE",
            "severity": "HIGH",
            "status": "open",
            "description": (
                f"Consent failure rate {failure_rate:.1%} exceeds threshold "
                f"{cfg.failure_rate_threshold:.1%} (window: {total} events)"
            ),
            "details": {
                "failure_rate": failure_rate,
                "threshold": cfg.failure_rate_threshold,
                "total_events": total,
                "failed_events": failed,
                "window_minutes": 15,
            },
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        })
        incidents_created += 1

    return {
        "window_events": total,
        "failure_rate": round(failure_rate, 4),
        "threshold": cfg.failure_rate_threshold,
        "incidents_created": incidents_created,
    }


# ──────────────────────────────────────────────────────────────────────
# Cleanup old metric events and sent notifications
# ──────────────────────────────────────────────────────────────────────

@router.get("/api/cron/cleanup")
async def cleanup(request: Request):
    if not _check_cron_secret(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    db = _db(request)
    # Remove metric events older than 2 hours
    cutoff = datetime.now(timezone.utc).replace(hour=datetime.now(timezone.utc).hour - 2)
    await db.delete("cms_metric_events", created_at=f"lt.{cutoff.isoformat()}")
    # Remove sent/processed notifications older than 24 hours
    day_ago = datetime.now(timezone.utc).replace(day=datetime.now(timezone.utc).day - 1)
    await db.delete(
        "cms_notification_queue",
        status="eq.sent",
        processed_at=f"lt.{day_ago.isoformat()}",
    )
    return {"cleaned_at": _now_iso()}
