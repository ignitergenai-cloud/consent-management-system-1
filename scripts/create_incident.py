"""
Consent Management System — Incident Generator
===============================================
Creates a P1 Major Incident in PagerDuty and pushes error logs to Grafana/Loki
whenever a critical issue is detected in the CMS application.

Usage:
    python scripts/create_incident.py

Configuration:
    Edit the CONFIG section below or set environment variables.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# CONFIG — edit these or override with environment variables
# ---------------------------------------------------------------------------
PD_API_TOKEN      = os.getenv("PD_API_TOKEN",      "u+2Kf6xufQUhr1CLJsBw")
PD_SERVICE_ID     = os.getenv("PD_SERVICE_ID",      "PUMAG77")
PD_PRIORITY_P1    = os.getenv("PD_PRIORITY_P1",     "P9VA1XZ")   # P1 priority ID
PD_FROM_EMAIL     = os.getenv("PD_FROM_EMAIL",      "gaurav.chandak@tcs.com")
PD_ESCALATION_ID  = os.getenv("PD_ESCALATION_ID",  "P0Z7O6F")

# Grafana Loki (Grafana Cloud or self-hosted with Loki)
# Get from: Grafana Cloud -> My Account -> Grafana Stack -> Loki -> Details
LOKI_URL          = os.getenv("LOKI_URL",           "")   # e.g. https://logs-prod-us-central1.grafana.net
LOKI_USERNAME     = os.getenv("LOKI_USERNAME",      "")   # numeric user ID from Grafana Cloud
LOKI_API_KEY      = os.getenv("LOKI_API_KEY",       "")   # Grafana Cloud API key (glc_...)

# New Relic Log API (alternative — requires License/Ingest key, not NRAK- key)
NR_LICENSE_KEY    = os.getenv("NR_LICENSE_KEY",     "")   # starts with license key format
NR_LOG_ENDPOINT   = os.getenv("NR_LOG_ENDPOINT",    "https://log-api.newrelic.com/log/v1")

# ---------------------------------------------------------------------------
# Incident definition
# ---------------------------------------------------------------------------
INCIDENT = {
    "title": "[P1-CRITICAL] CMS: Consent Creation Total Outage — DynamoDB ResourceNotFoundException",
    "severity": "P1",
    "component": "consent-api",
    "application": "consent-management-system",
    "environment": "production",
    "error_type": "ResourceNotFoundException",
    "affected_endpoint": "POST /api/v1/consents",
    "failure_rate": 1.0,
    "github_repo": "https://github.com/ignitergenai-cloud/consent-management-system-1",
    "details": (
        "CRITICAL INCIDENT — Consent Management System\n\n"
        "All POST /api/v1/consents requests are returning HTTP 500.\n"
        "Root cause: DynamoDB table 'cms-consents' is throwing ResourceNotFoundException\n"
        "on every write operation.\n\n"
        "Impact:\n"
        "  - 100% of new consent creation requests are failing\n"
        "  - No new customer consents can be recorded\n"
        "  - Existing consents are expiring without renewal capability\n"
        "  - GDPR / CCPA compliance at risk\n\n"
        "Error trace:\n"
        "  RuntimeError: DynamoDB table 'cms-consents' not found: ResourceNotFoundException.\n"
        "  All consent creation requests are failing. Data loss in progress.\n\n"
        "Affected service : consent-api (port 8000)\n"
        "GitHub commit    : https://github.com/ignitergenai-cloud/consent-management-system-1\n"
        "Environment      : Production\n"
        "Severity         : P1 / Major Incident"
    ),
}

ERROR_LOGS = [
    {
        "level": "CRITICAL",
        "message": "ResourceNotFoundException: DynamoDB table 'cms-consents' not found",
        "service": "consent-api",
        "endpoint": "POST /api/v1/consents",
        "http_status": 500,
        "error_type": "ResourceNotFoundException",
        "stack_trace": (
            "Traceback (most recent call last):\n"
            "  File consent_api/services/consent_service.py, line 62, in create_consent\n"
            "    raise RuntimeError(\"DynamoDB table 'cms-consents' not found\")\n"
            "RuntimeError: DynamoDB table 'cms-consents' not found: ResourceNotFoundException"
        ),
    },
    {
        "level": "CRITICAL",
        "message": "100% consent creation failure rate — data loss in progress",
        "service": "consent-api",
        "endpoint": "POST /api/v1/consents",
        "failure_rate": 1.0,
        "requests_failed": 100,
        "requests_succeeded": 0,
    },
    {
        "level": "ERROR",
        "message": "SNS publish skipped — upstream consent creation failed before reaching SNS",
        "service": "consent-api",
        "topic": "cms-consent-events",
        "reason": "consent_service.create_consent raised RuntimeError",
    },
    {
        "level": "WARNING",
        "message": "Consent processor queue idle — no new PENDING events received in 15 minutes",
        "service": "consent-processor",
        "queue": "cms-consent-processing-queue",
        "idle_minutes": 15,
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _http(method: str, url: str, headers: dict, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _pd_headers() -> dict:
    return {
        "Authorization": f"Token token={PD_API_TOKEN}",
        "Accept": "application/vnd.pagerduty+json;version=2",
        "Content-Type": "application/json",
        "From": PD_FROM_EMAIL,
    }


def _now_ms() -> int:
    return int(time.time() * 1000)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# ---------------------------------------------------------------------------
# PagerDuty
# ---------------------------------------------------------------------------

def create_pagerduty_incident() -> dict:
    print("\n[PagerDuty] Creating P1 Major Incident...")

    body = {
        "incident": {
            "type": "incident",
            "title": INCIDENT["title"],
            "service": {"id": PD_SERVICE_ID, "type": "service_reference"},
            "urgency": "high",
            "priority": {"id": PD_PRIORITY_P1, "type": "priority_reference"},
            "escalation_policy": {"id": PD_ESCALATION_ID, "type": "escalation_policy_reference"},
            "body": {
                "type": "incident_body",
                "details": INCIDENT["details"],
            },
        }
    }

    status, resp = _http("POST", "https://api.pagerduty.com/incidents", _pd_headers(), body)
    inc = resp.get("incident", {})

    if status in (200, 201):
        print(f"  [OK]Incident created")
        print(f"  ID       : {inc.get('id')}")
        print(f"  Priority : {inc.get('priority', {}).get('name', 'N/A')}")

        print(f"  URL      : {inc.get('html_url')}")
        return inc
    else:
        print(f"  [FAIL]Failed ({status}): {resp}")
        return {}


# ---------------------------------------------------------------------------
# Grafana / Loki
# ---------------------------------------------------------------------------

def push_logs_to_loki(incident_id: str) -> None:
    if not LOKI_URL or not LOKI_USERNAME or not LOKI_API_KEY:
        print("\n[Grafana/Loki] Skipped — set LOKI_URL, LOKI_USERNAME, LOKI_API_KEY to enable.")
        return

    print("\n[Grafana/Loki] Pushing error logs...")

    import base64
    credentials = base64.b64encode(f"{LOKI_USERNAME}:{LOKI_API_KEY}".encode()).decode()

    streams = []
    for log in ERROR_LOGS:
        entry = {**log, "application": "consent-management-system",
                 "environment": "production", "incident_id": incident_id,
                 "timestamp": _now_iso()}
        streams.append({
            "stream": {
                "application": "consent-management-system",
                "service": log["service"],
                "level": log["level"],
                "environment": "production",
            },
            "values": [[str(_now_ms() * 1_000_000), json.dumps(entry)]],
        })

    body = {"streams": streams}
    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json",
    }

    loki_push = f"{LOKI_URL.rstrip('/')}/loki/api/v1/push"
    status, resp = _http("POST", loki_push, headers, body)

    if status in (200, 204):
        print(f"  [OK]{len(streams)} log streams pushed to Loki")
        print(f"  Query in Grafana Explore: {{application=\"consent-management-system\"}}")
    else:
        print(f"  [FAIL]Loki push failed ({status}): {resp}")


def push_logs_to_newrelic(incident_id: str) -> None:
    if not NR_LICENSE_KEY:
        print("\n[New Relic] Skipped — set NR_LICENSE_KEY (License/Ingest key) to enable.")
        print("  Note: NRAK- keys are User API keys and cannot ingest logs.")
        print("  Go to: New Relic -> API Keys -> Create key -> Type: INGEST - LICENSE")
        return

    print("\n[New Relic] Pushing error logs...")
    ts = _now_ms()

    payload = [
        {**log, "timestamp": ts, "application": "consent-management-system",
         "environment": "production", "incident_id": incident_id}
        for log in ERROR_LOGS
    ]

    headers = {"Api-Key": NR_LICENSE_KEY, "Content-Type": "application/json"}
    status, resp = _http("POST", NR_LOG_ENDPOINT, headers, payload)

    if status in (200, 202):
        print(f"  [OK]{len(payload)} log events pushed to New Relic")
    else:
        print(f"  [FAIL]New Relic push failed ({status}): {resp}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("  Consent Management System — Incident Generator")
    print("=" * 60)

    inc = create_pagerduty_incident()
    incident_id = inc.get("id", "UNKNOWN")

    push_logs_to_loki(incident_id)
    push_logs_to_newrelic(incident_id)

    print()
    print("=" * 60)
    print("  Summary")
    print("=" * 60)
    if incident_id != "UNKNOWN":
        print(f"  PagerDuty Incident : {inc.get('html_url')}")
        print(f"  Priority           : P1 / Major Incident")
        print(f"  Status             : {inc.get('status', 'triggered')}")
    else:
        print("  PagerDuty          : FAILED — check token/config")
    print()
    print("  To resolve the incident:")
    print("    python scripts/create_incident.py --resolve <incident_id>")
    print()


if __name__ == "__main__":
    main()
