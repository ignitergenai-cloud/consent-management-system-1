# KB-004: Revoke Consent — 405 Method Not Allowed and 500 Failures

**Article ID:** KB-004  
**Application:** consent-management-system / cms-unified (Vercel)  
**Severity:** MEDIUM–HIGH  
**Affected Endpoints:** `DELETE /api/v1/consents/{id}`, `POST /api/v1/consents/{id}/revoke`  
**Last Updated:** 2026-09-02

---

## Summary

Two distinct failure modes affect consent revocation in production:

1. **405 Method Not Allowed** on `DELETE /api/v1/consents/{id}` — consistently observed in logs; caused by a frontend routing issue calling the wrong HTTP method. The correct revocation method is `POST /api/v1/consents/{id}/revoke`.
2. **500 Internal Server Error** on `POST /api/v1/consents/{id}/revoke` — occurs intermittently; caused by chaos mode injecting an "audit log service unreachable" error when `CHAOS_MODE=true`.

---

## Observed Symptoms

### 405 Pattern
```
DELETE /api/v1/consents/1aeb3091-2333-4b83-8fc0-8b4e088d78af → 405 (0.39ms)
DELETE /api/v1/consents/f900dd97-4cd1-4ac6-b266-5c757e620588 → 405 (0.76ms)
DELETE /api/v1/consents/6bc3ed0c-ef87-4a7c-b39a-3cd3a50670f9 → 405 (0.41ms)
```
- Response time: sub-millisecond (immediate rejection by the router)
- Repeated for the same consent ID multiple times — suggesting retry loops in the frontend
- No server-side processing occurs; the route simply does not exist

### 500 Pattern
```
[SLOW ERROR] POST /api/v1/consents/{id}/revoke → 500 (539.96ms) | page=ConsentsPage action=RevokeConsent | ERROR: internal_server_error
[SLOW ERROR] POST /api/v1/consents/{id}/revoke → 500 (535.43ms) | chaos_mode: true
```
- Response time: 500–600 ms (chaos mode fires after some processing)
- Authenticated requests (`http.has_auth: true`) still fail — auth is not the cause
- `chaos_mode: true` visible on log records

---

## Root Cause

### 405 Root Cause — Wrong HTTP Method from Frontend
The API defines revocation as `POST /api/v1/consents/{id}/revoke`. There is no `DELETE /api/v1/consents/{id}` route in the current Vercel unified app (`vercel_app/main.py`).

The frontend (or API client) is calling `DELETE /api/v1/consents/{consent_id}` which does not match any registered route. FastAPI returns 405 automatically.

> **Note:** The microservices `consent-api` does define `DELETE /api/v1/consents/{id}` as a redirect to revoke, but the Vercel unified deployment does not include this route alias.

### 500 Root Cause — Chaos Mode on Revoke
**File:** `vercel_app/main.py`, lines 390–404  
When `CHAOS_MODE=true`, the revoke endpoint randomly raises:
```
RuntimeError("Audit log service unreachable: connection refused after 3 retries")
```
This fires a PagerDuty incident and returns HTTP 500.

---

## Impact

- **405 failures:** Users cannot revoke consents via the frontend UI. The 405 response is fast but definitive — no revocation occurs. Repeated retries create noise in logs but do not cause data changes.
- **500 failures:** Revocation requests fail intermittently. The consent remains in its current state (not revoked). The customer's consent is still active when it should be revoked — a potential compliance concern.

---

## Diagnosis Steps

### Distinguish 405 vs 500
```
# 405 pattern:
service:cms-unified http.method:DELETE http.status_code:405

# 500 pattern:
service:cms-unified ui.action:RevokeConsent http.status_code:500
```

### For 405 — Identify the caller
Check `http.referer` and `http.user_agent` on the 405 log records to identify which frontend version or API client is calling DELETE. Compare against current frontend source.

### For 500 — Check chaos mode
```bash
grep CHAOS_MODE .env
# Check Vercel env vars for CHAOS_MODE=true
```

### Verify a successful revoke flow
After fixing (see Resolution), confirm the correct endpoint works:
```bash
curl -X POST \
  https://<api-host>/api/v1/consents/<consent-id>/revoke \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json"
# Expected: 200 OK
```

---

## Resolution

### Fix 405 — Update frontend to use correct endpoint
The frontend must call `POST /api/v1/consents/{id}/revoke` instead of `DELETE /api/v1/consents/{id}`.

Frontend file to update (search for the DELETE call):
```bash
grep -r "DELETE.*consents" frontend/src/
```
Change the API call to:
```javascript
// Wrong:
await fetch(`/api/v1/consents/${id}`, { method: 'DELETE' })

// Correct:
await fetch(`/api/v1/consents/${id}/revoke`, { method: 'POST' })
```

**Interim server-side workaround** — add a route alias in `vercel_app/main.py` that delegates DELETE to the revoke logic (matching the microservices behaviour):
```python
@app.delete("/api/v1/consents/{consent_id}", status_code=200)
async def delete_consent(consent_id: str, ...):
    return await revoke_consent(consent_id, ...)
```

### Fix 500 — Disable chaos mode
See KB-002 Resolution: set `CHAOS_MODE=false` in Vercel environment variables and redeploy.

---

## Prevention

- Add an **API contract test** (e.g., using Dredd or Schemathesis against the OpenAPI spec) that would catch a frontend calling a non-existent route.
- Add `DELETE /api/v1/consents/{id}` as a documented alias in the OpenAPI spec that delegates to the revoke action, preventing this class of 405 regardless of frontend version.
- Include the revoke endpoint in the standard E2E test suite so chaos mode 500s on this path are caught in staging before production deployment.

---

## Related Articles
- KB-002: Consent Creation Intermittent 500 Failures (Chaos Mode)
- KB-006: Authentication 500 and 401 Failures
