# KB-002: Consent Creation Intermittent 500 Failures — Chaos Mode (Vercel / Unified App)

**Article ID:** KB-002  
**Application:** consent-management-system / cms-unified (Vercel)  
**Severity:** HIGH  
**Affected Endpoint:** `POST /api/v1/consents`  
**Last Updated:** 2026-09-02

---

## Summary

The Vercel-deployed unified app (`cms-unified`) includes an intentional chaos mode that randomly injects HTTP 500 failures on `POST /api/v1/consents` and `POST /api/v1/consents/{id}/revoke`. When `CHAOS_MODE=true` (currently the committed default), roughly 1-in-N consent creation attempts fail with one of five synthetic error scenarios. These failures are real HTTP 500s that reach users, trigger PagerDuty incidents, and appear in logs marked `chaos_mode: true`.

---

## Observed Symptoms

| Signal | Detail |
|---|---|
| HTTP response | `POST /api/v1/consents` → 500, response time 0–700 ms |
| Log level | `ERROR` |
| Log field | `chaos_mode: true` present on the log record |
| Error categories seen | `internal_server_error` |
| Affected pages | `ConsentsPage` (`ui.page=ConsentsPage`, `ui.action=CreateConsent`) |
| Pattern | Non-deterministic — some POST requests succeed (201), others fail (500) on identical input |

### Example log messages (from production):
```
[ERROR] POST /api/v1/consents → 500 (2.59ms) | cms-unified | page=ConsentsPage action=CreateConsent
[SLOW ERROR] POST /api/v1/consents → 500 (621.45ms) | cms-unified | page=ConsentsPage action=CreateConsent | ERROR: internal_server_error
[FAST ERROR] POST /api/v1/consents → 500 (1.15ms) | cms-unified | page=ConsentsPage action=CreateConsent | ERROR: internal_server_error
```

---

## Root Cause

**File:** `vercel_app/main.py`, lines 230–276  
**Trigger:** `settings.chaos_mode == True` AND endpoint is `POST /api/v1/consents`

When chaos mode is active, the endpoint randomly selects one of five failure scenarios before any real processing occurs:

| Scenario key | Error message injected |
|---|---|
| `db_connection` | `Supabase connection pool exhausted` |
| `email_service` | `Resend API unavailable: 503` |
| `validation_timeout` | `Consent validation engine timed out after 30s` |
| `compliance_service` | `GDPR compliance service unreachable: TLS certificate expired` |
| `encryption_failure` | `Token signing key unavailable: KMS rotation in progress` |

For `POST /api/v1/consents/{id}/revoke` (lines 390–404), the injected error is:
- `Audit log service unreachable`

Each chaos trigger also fires a PagerDuty incident (rate-limited to one per incident type per 5 minutes).

The response time difference visible in logs — some failures at ~1 ms (fast fail path) vs ~600 ms (after attempting some work) — reflects whether the chaos roll happens before or after the initial DB read.

---

## Impact

- **Partial consent creation failure** — some users cannot create consents; retrying may succeed.
- **Revoke operations also fail intermittently** when chaos mode is active.
- **PagerDuty alert storm** — each distinct error scenario key generates its own PagerDuty alert. Up to 5 different P1 incidents can fire in a short window.
- **User-facing error** — the frontend on `ConsentsPage` receives a 500 and shows an error state.

---

## Diagnosis Steps

### Step 1 — Confirm chaos mode is active
Check New Relic Logs for recent 500s on consent creation:
```
service:cms-unified http.method:POST http.path:/api/v1/consents http.status_code:500
```
Look at the `chaos_mode` field on the log record. If `chaos_mode: true`, this KB applies.

### Step 2 — Check environment configuration
```bash
# Vercel dashboard: Project → Settings → Environment Variables
# Look for CHAOS_MODE

# Or check the committed .env file:
grep CHAOS_MODE .env
# Expected (production): CHAOS_MODE=false
# Current (problem): CHAOS_MODE=true
```

### Step 3 — Confirm the pattern is non-deterministic
If the same payload sometimes succeeds and sometimes fails with different error messages, chaos mode is the cause. Deterministic failures (always same error) point to a real infrastructure issue — check KB-001.

### Step 4 — Count error distribution
```
# New Relic NRQL:
SELECT count(*) FROM Log 
WHERE service = 'cms-unified' 
  AND http.method = 'POST' 
  AND http.path = '/api/v1/consents'
  AND http.status_code = 500
FACET message 
SINCE 1 hour ago
```
If you see all five error message types with roughly equal counts, chaos mode is randomizing across them.

---

## Resolution

### Disable chaos mode (Vercel deployment):
1. Go to Vercel Dashboard → Project → Settings → Environment Variables.
2. Set `CHAOS_MODE=false` (or delete the variable; the default in `vercel_app/config.py` is `False`).
3. Trigger a redeployment:
   ```bash
   # Or via deploy script:
   node deploy-to-vercel.js
   ```
4. Verify: Make several `POST /api/v1/consents` requests — all should return 201.

### Disable chaos mode (local / Docker):
```bash
# Edit .env:
CHAOS_MODE=false
# Restart:
docker compose restart
```

### Acknowledge existing PagerDuty incidents:
Chaos mode fires PagerDuty incidents per error type. After disabling chaos mode, close any open PagerDuty incidents that were generated by it — check the incident title for the synthetic error message strings listed above.

---

## Prevention

- **Never commit `CHAOS_MODE=true`** in `.env`. Add a pre-commit hook or CI check:
  ```bash
  grep -q "CHAOS_MODE=true" .env && echo "ERROR: CHAOS_MODE must not be true in .env" && exit 1
  ```
- Add a Vercel deployment check that rejects `CHAOS_MODE=true` in production environment variables.
- Consider renaming the env var to `CHAOS_MODE_ENABLED` and requiring an explicit second flag (`CHAOS_CONFIRMED=yes`) to prevent accidental activation.
- Log a prominent `WARN` at application startup when chaos mode is active so it is visible in the startup log stream.

---

## Related Articles
- KB-001: DynamoDB Table Not Found (microservices chaos mode variant)
- KB-004: Revoke Consent 500 and 405 Failures
