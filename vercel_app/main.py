"""CMS Unified FastAPI app — Supabase + Resend, no AWS required."""

from __future__ import annotations

import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from vercel_app.config import UnifiedSettings
from vercel_app.db import SupabaseDB
from vercel_app.email import send_email
from vercel_app.cron_routes import router as cron_router
from vercel_app.observability import ObservabilityMiddleware, register_exception_handlers, fire_pd_incident

logger = structlog.get_logger()

# ──────────────────────────────────────────────────────────────────────
# Pydantic models
# ──────────────────────────────────────────────────────────────────────

class ConsentRecord(BaseModel):
    consent_id: str
    customer_id: str
    consent_type: str
    channel: str
    status: str = "PENDING"
    message_template_id: str = "default"
    customer_phone: str | None = None
    customer_email: str | None = None
    consent_text: str = ""
    response_token: str | None = None
    expires_at: str
    created_at: str
    updated_at: str
    granted_at: str | None = None
    denied_at: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    metadata: dict = Field(default_factory=dict)


class CreateConsentRequest(BaseModel):
    customer_id: str
    consent_type: str
    channel: str
    customer_phone: str | None = None
    customer_email: str | None = None
    consent_text: str
    message_template_id: str = "default"
    expires_in_hours: int = 72
    metadata: dict = Field(default_factory=dict)


class CreateConsentResponse(BaseModel):
    consent_id: str
    status: str
    response_url: str
    expires_at: str
    created_at: str


class ConsentResponseRequest(BaseModel):
    granted: bool
    ip_address: str | None = None
    user_agent: str | None = None


class PaginatedConsentsResponse(BaseModel):
    items: list[ConsentRecord]
    count: int
    next_token: str | None = None


class ConsentAnalytics(BaseModel):
    total_consents: int
    by_status: dict[str, int]
    by_channel: dict[str, int]
    by_type: dict[str, int]
    expiring_soon: int


class Incident(BaseModel):
    incident_id: str
    type: str
    severity: str = "MEDIUM"
    status: str = "open"
    description: str = ""
    details: dict = Field(default_factory=dict)
    created_at: str
    updated_at: str
    resolved_at: str | None = None
    acknowledged_at: str | None = None


class HistoryEntry(BaseModel):
    id: int
    consent_id: str
    action: str
    details: dict = Field(default_factory=dict)
    created_at: str


# ──────────────────────────────────────────────────────────────────────
# App factory
# ──────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = UnifiedSettings()
    app.state.settings = settings
    app.state.db = SupabaseDB(settings.supabase_url, settings.supabase_key)
    logger.info("cms_startup", supabase_url=settings.supabase_url[:40] + "...")
    yield
    logger.info("cms_shutdown")


app = FastAPI(title="CMS Unified API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ObservabilityMiddleware, service_name="cms-unified")

register_exception_handlers(app, service_name="cms-unified")

app.include_router(cron_router)


def _db(request: Request) -> SupabaseDB:
    return request.app.state.db


def _settings(request: Request) -> UnifiedSettings:
    try:
        return request.app.state.settings
    except AttributeError:
        cfg = UnifiedSettings()
        request.app.state.settings = cfg
        return cfg


def _row_to_consent(row: dict) -> ConsentRecord:
    return ConsentRecord(
        consent_id=row["consent_id"],
        customer_id=row["customer_id"],
        consent_type=row["consent_type"],
        channel=row["channel"],
        status=row["status"],
        message_template_id=row.get("message_template_id", "default"),
        customer_phone=row.get("customer_phone"),
        customer_email=row.get("customer_email"),
        consent_text=row.get("consent_text", ""),
        response_token=row.get("response_token"),
        expires_at=str(row["expires_at"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        granted_at=str(row["granted_at"]) if row.get("granted_at") else None,
        denied_at=str(row["denied_at"]) if row.get("denied_at") else None,
        ip_address=row.get("ip_address"),
        user_agent=row.get("user_agent"),
        metadata=row.get("metadata") or {},
    )


# ──────────────────────────────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────────────────────────────

@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "service": "cms-unified", "timestamp": _now_iso()}



# ──────────────────────────────────────────────────────────────────────
# Consents CRUD
# ──────────────────────────────────────────────────────────────────────

@app.post("/api/v1/consents", response_model=CreateConsentResponse, status_code=201)
async def create_consent(body: CreateConsentRequest, request: Request):
    db = _db(request)
    cfg = _settings(request)

    if cfg.chaos_mode:
        import asyncio, random
        _CHAOS_SCENARIOS = [
            {
                "type": "db_connection",
                "error": "Supabase connection pool exhausted: max connections reached",
                "detail": "All database connections are in use. Consent records cannot be written.",
            },
            {
                "type": "email_service",
                "error": "Resend API unavailable: 503 Service Unavailable",
                "detail": "Email notification service is down. Consent confirmation emails cannot be sent.",
            },
            {
                "type": "validation_timeout",
                "error": "Consent validation engine timed out after 30s",
                "detail": "The downstream compliance validation service is not responding.",
            },
            {
                "type": "compliance_service",
                "error": "GDPR compliance service unreachable: TLS certificate expired",
                "detail": "Regulatory compliance checks cannot be performed. All consent creation is blocked.",
            },
            {
                "type": "encryption_failure",
                "error": "Token signing key unavailable: KMS rotation in progress",
                "detail": "Consent response tokens cannot be generated. Encryption service is unavailable.",
            },
        ]
        scenario = random.choice(_CHAOS_SCENARIOS)
        error_msg = scenario["error"]
        logger.error(
            "chaos_mode_triggered",
            service="cms-unified",
            endpoint="POST /api/v1/consents",
            incident_type=scenario["type"],
            error=error_msg,
        )
        ui_page = request.headers.get("x-ui-page") or None
        ui_action = request.headers.get("x-ui-action") or None
        ui_route = request.headers.get("x-ui-route") or None
        await asyncio.to_thread(
            fire_pd_incident,
            cfg, "cms-unified", "/api/v1/consents", error_msg, "chaos_mode=True",
            ui_page, ui_action, ui_route, scenario["type"],
        )
        raise HTTPException(500, f"{error_msg}. {scenario['detail']}")

    if body.channel == "EMAIL" and not body.customer_email:
        raise HTTPException(400, "customer_email required for EMAIL channel")
    if body.channel == "SMS" and not body.customer_phone:
        raise HTTPException(400, "customer_phone required for SMS channel")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=body.expires_in_hours)
    consent_id = str(uuid.uuid4())
    response_token = secrets.token_urlsafe(32)

    row = {
        "consent_id": consent_id,
        "customer_id": body.customer_id,
        "consent_type": body.consent_type,
        "channel": body.channel,
        "status": "PENDING",
        "message_template_id": body.message_template_id,
        "customer_phone": body.customer_phone,
        "customer_email": body.customer_email,
        "consent_text": body.consent_text,
        "response_token": response_token,
        "expires_at": expires_at.isoformat(),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "metadata": body.metadata,
    }
    await db.insert("consents", row)

    # Queue notification
    recipient = body.customer_email or body.customer_phone or ""
    if recipient:
        await db.insert("cms_notification_queue", {
            "consent_id": consent_id,
            "channel": body.channel,
            "recipient": recipient,
            "subject": "Consent Request",
            "body": body.consent_text,
        })

    response_url = f"{cfg.base_url}/api/v1/consents/respond/{response_token}"
    return CreateConsentResponse(
        consent_id=consent_id,
        status="PENDING",
        response_url=response_url,
        expires_at=expires_at.isoformat(),
        created_at=now.isoformat(),
    )


@app.post("/api/v1/consents/bulk", status_code=201)
async def bulk_create_consents(body: list[CreateConsentRequest], request: Request):
    results = []
    for req in body:
        try:
            result = await create_consent(req, request)
            results.append({"success": True, "consent_id": result.consent_id})
        except Exception as exc:
            results.append({"success": False, "error": str(exc)})
    return {"created": sum(1 for r in results if r["success"]), "results": results}


@app.get("/api/v1/consents", response_model=PaginatedConsentsResponse)
async def list_consents(
    request: Request,
    status: str | None = Query(None),
    channel: str | None = Query(None),
    customer_id: str | None = Query(None),
    page_size: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
):
    db = _db(request)
    filters: dict[str, str] = {}
    if status:
        filters["status"] = f"eq.{status}"
    if channel:
        filters["channel"] = f"eq.{channel}"
    if customer_id:
        filters["customer_id"] = f"eq.{customer_id}"

    rows = await db.select(
        "consents",
        order="created_at.desc",
        limit=page_size,
        offset=offset,
        **filters,
    )
    items = [_row_to_consent(r) for r in rows]
    return PaginatedConsentsResponse(items=items, count=len(items))


@app.get("/api/v1/consents/{consent_id}", response_model=ConsentRecord)
async def get_consent(consent_id: str, request: Request):
    db = _db(request)
    row = await db.select_one("consents", consent_id=f"eq.{consent_id}")
    if not row:
        raise HTTPException(404, f"Consent {consent_id} not found")
    return _row_to_consent(row)


@app.patch("/api/v1/consents/{consent_id}", response_model=ConsentRecord)
async def update_consent(consent_id: str, updates: dict[str, Any], request: Request):
    db = _db(request)
    updates["updated_at"] = _now_iso()
    rows = await db.update("consents", updates, consent_id=f"eq.{consent_id}")
    if not rows:
        raise HTTPException(404, f"Consent {consent_id} not found")
    return _row_to_consent(rows[0])


@app.post("/api/v1/consents/{consent_id}/revoke", response_model=ConsentRecord)
async def revoke_consent(consent_id: str, request: Request):
    db = _db(request)
    now = _now_iso()
    rows = await db.update(
        "consents",
        {"status": "REVOKED", "updated_at": now},
        consent_id=f"eq.{consent_id}",
    )
    if not rows:
        raise HTTPException(404, f"Consent {consent_id} not found")
    await db.insert("consent_history", {
        "consent_id": consent_id,
        "action": "REVOKED",
        "details": {"revoked_at": now},
        "created_at": now,
    })
    return _row_to_consent(rows[0])


@app.delete("/api/v1/consents/{consent_id}", status_code=200)
async def revoke_consent_delete(consent_id: str, request: Request):
    return await revoke_consent(consent_id, request)


@app.get("/api/v1/consents/{consent_id}/history", response_model=list[HistoryEntry])
async def get_consent_history(consent_id: str, request: Request):
    db = _db(request)
    rows = await db.select(
        "consent_history",
        order="created_at.desc",
        consent_id=f"eq.{consent_id}",
    )
    return [
        HistoryEntry(
            id=r["id"],
            consent_id=r["consent_id"],
            action=r["action"],
            details=r.get("details") or {},
            created_at=str(r["created_at"]),
        )
        for r in rows
    ]


@app.get("/api/v1/customers/{customer_id}/consents", response_model=PaginatedConsentsResponse)
async def list_customer_consents(
    customer_id: str,
    request: Request,
    page_size: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
):
    db = _db(request)
    rows = await db.select(
        "consents",
        order="created_at.desc",
        limit=page_size,
        offset=offset,
        customer_id=f"eq.{customer_id}",
    )
    items = [_row_to_consent(r) for r in rows]
    return PaginatedConsentsResponse(items=items, count=len(items))


# ──────────────────────────────────────────────────────────────────────
# Consent response (customer-facing)
# ──────────────────────────────────────────────────────────────────────

@app.post("/api/v1/consents/respond/{response_token}", response_model=ConsentRecord)
async def respond_to_consent(
    response_token: str,
    body: ConsentResponseRequest,
    request: Request,
):
    db = _db(request)
    row = await db.select_one("consents", response_token=f"eq.{response_token}")
    if not row:
        raise HTTPException(404, "Consent not found")
    if row["status"] not in ("PENDING", "SENT", "DELIVERED"):
        raise HTTPException(400, f"Consent already in terminal status: {row['status']}")

    now = _now_iso()
    new_status = "GRANTED" if body.granted else "DENIED"
    updates = {
        "status": new_status,
        "updated_at": now,
        "ip_address": body.ip_address or (request.client.host if request.client else None),
        "user_agent": body.user_agent or request.headers.get("user-agent"),
    }
    if body.granted:
        updates["granted_at"] = now
    else:
        updates["denied_at"] = now

    rows = await db.update("consents", updates, response_token=f"eq.{response_token}")
    if not rows:
        raise HTTPException(500, "Failed to update consent")

    await db.insert("consent_history", {
        "consent_id": row["consent_id"],
        "action": new_status,
        "details": {"ip_address": updates.get("ip_address"), "user_agent": updates.get("user_agent")},
    })
    return _row_to_consent(rows[0])


_CONSENT_RESPONSE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Consent Request</title>
  <style>
    * {{ margin:0;padding:0;box-sizing:border-box }}
    body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
            background:#f5f5f5;display:flex;justify-content:center;align-items:center;
            min-height:100vh;padding:1rem }}
    .card {{ background:#fff;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.1);
             max-width:480px;width:100%;padding:2rem }}
    h1 {{ font-size:1.4rem;margin-bottom:1rem }}
    .text {{ background:#f9f9f9;border:1px solid #e0e0e0;border-radius:4px;
             padding:1rem;margin-bottom:1.5rem;line-height:1.6 }}
    .actions {{ display:flex;gap:1rem }}
    button {{ flex:1;padding:.75rem 1rem;border:none;border-radius:4px;font-size:1rem;
              cursor:pointer;font-weight:600 }}
    .grant {{ background:#22c55e;color:#fff }}
    .deny  {{ background:#ef4444;color:#fff }}
    .msg   {{ text-align:center;padding:2rem 0;font-size:1.1rem }}
    .ok {{ color:#16a34a }} .no {{ color:#dc2626 }} .err {{ color:#d97706 }}
  </style>
</head>
<body>
<div class="card">
  <h1>Consent Request</h1>
  <div class="text">{consent_text}</div>
  <div id="actions" class="actions">
    <button class="grant" onclick="respond(true)">Grant Consent</button>
    <button class="deny"  onclick="respond(false)">Deny</button>
  </div>
  <div id="msg" class="msg" style="display:none"></div>
</div>
<script>
async function respond(granted) {{
  document.getElementById('actions').style.display='none';
  const r = await fetch(window.location.pathname, {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{granted}})
  }});
  const msg = document.getElementById('msg');
  msg.style.display='block';
  if (r.ok) {{
    const data = await r.json();
    if (granted) {{ msg.className='msg ok'; msg.textContent='Thank you! Consent granted.'; }}
    else {{ msg.className='msg no'; msg.textContent='Consent denied. Your preference has been recorded.'; }}
  }} else {{
    msg.className='msg err'; msg.textContent='An error occurred. Please try again.';
    document.getElementById('actions').style.display='flex';
  }}
}}
</script>
</body>
</html>"""


@app.get("/api/v1/consents/respond/{response_token}", response_class=HTMLResponse)
async def consent_response_page(response_token: str, request: Request):
    db = _db(request)
    row = await db.select_one("consents", response_token=f"eq.{response_token}")
    if not row:
        return HTMLResponse("<h1>Consent request not found</h1>", status_code=404)
    text = row.get("consent_text") or "Please review and respond to this consent request."
    return HTMLResponse(_CONSENT_RESPONSE_HTML.format(consent_text=text))


# ──────────────────────────────────────────────────────────────────────
# Analytics
# ──────────────────────────────────────────────────────────────────────

@app.get("/api/v1/analytics/consents", response_model=ConsentAnalytics)
async def get_consent_analytics(request: Request):
    db = _db(request)
    rows = await db.select("consents", columns="status,channel,consent_type,expires_at")
    total = len(rows)
    by_status: dict[str, int] = {}
    by_channel: dict[str, int] = {}
    by_type: dict[str, int] = {}
    soon_cutoff = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    expiring_soon = 0

    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        by_channel[r["channel"]] = by_channel.get(r["channel"], 0) + 1
        by_type[r["consent_type"]] = by_type.get(r["consent_type"], 0) + 1
        if r.get("expires_at") and str(r["expires_at"]) <= soon_cutoff and r["status"] == "PENDING":
            expiring_soon += 1

    return ConsentAnalytics(
        total_consents=total,
        by_status=by_status,
        by_channel=by_channel,
        by_type=by_type,
        expiring_soon=expiring_soon,
    )


# ──────────────────────────────────────────────────────────────────────
# Incidents
# ──────────────────────────────────────────────────────────────────────

def _row_to_incident(r: dict) -> Incident:
    return Incident(
        incident_id=r["incident_id"],
        type=r["type"],
        severity=r.get("severity", "MEDIUM"),
        status=r.get("status", "open"),
        description=r.get("description", ""),
        details=r.get("details") or {},
        created_at=str(r["created_at"]),
        updated_at=str(r["updated_at"]),
        resolved_at=str(r["resolved_at"]) if r.get("resolved_at") else None,
        acknowledged_at=str(r.get("acknowledged_at")) if r.get("acknowledged_at") else None,
    )


@app.get("/api/v1/incidents", response_model=list[Incident])
async def list_incidents(
    request: Request,
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
):
    db = _db(request)
    filters: dict[str, str] = {}
    if status:
        filters["status"] = f"eq.{status}"
    rows = await db.select("cms_incidents", order="created_at.desc", limit=limit, **filters)
    return [_row_to_incident(r) for r in rows]


@app.get("/api/v1/incidents/{incident_id}", response_model=Incident)
async def get_incident(incident_id: str, request: Request):
    db = _db(request)
    row = await db.select_one("cms_incidents", incident_id=f"eq.{incident_id}")
    if not row:
        raise HTTPException(404, f"Incident {incident_id} not found")
    return _row_to_incident(row)


@app.post("/api/v1/incidents/{incident_id}/acknowledge")
async def acknowledge_incident(incident_id: str, request: Request):
    db = _db(request)
    now = _now_iso()
    rows = await db.update(
        "cms_incidents",
        {"status": "acknowledged", "acknowledged_at": now, "updated_at": now},
        incident_id=f"eq.{incident_id}",
    )
    if not rows:
        raise HTTPException(404, f"Incident {incident_id} not found")
    return _row_to_incident(rows[0])


@app.post("/api/v1/incidents/{incident_id}/resolve")
async def resolve_incident(incident_id: str, request: Request):
    db = _db(request)
    now = _now_iso()
    rows = await db.update(
        "cms_incidents",
        {"status": "resolved", "resolved_at": now, "updated_at": now},
        incident_id=f"eq.{incident_id}",
    )
    if not rows:
        raise HTTPException(404, f"Incident {incident_id} not found")
    return _row_to_incident(rows[0])
