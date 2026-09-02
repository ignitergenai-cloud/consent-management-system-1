# KB-006: Authentication — 500 Internal Server Error and 401 Unauthorized

**Article ID:** KB-006  
**Application:** consent-management-system / cms-unified (Vercel)  
**Severity:** HIGH  
**Affected Endpoint:** `POST /api/v1/auth/login`  
**Last Updated:** 2026-09-02

---

## Summary

Two authentication failure modes appear in production logs:

1. **500 Internal Server Error** on `POST /api/v1/auth/login` — caused by chaos mode randomly injecting a failure on the login endpoint when `CHAOS_MODE=true`. This blocks all user access to the application.
2. **401 Unauthorized** on `POST /api/v1/auth/login` — caused by incorrect credentials. Normal behaviour; not an incident.

Additionally, the authentication system has critical design limitations that are relevant to incident response: tokens are not validated on any endpoint, and credentials are hardcoded.

---

## Observed Symptoms

### 500 Pattern (chaos mode)
```
[SLOW ERROR] POST /api/v1/auth/login → 500 (554.79ms) | page=LoginPage action=Login | ERROR: internal_server_error
[SLOW ERROR] POST /api/v1/auth/login → 500 (590.6ms) | chaos_mode: true
```
- Affects all login attempts during chaos mode
- Users cannot log in; the frontend shows a login error
- `chaos_mode: true` on log record

### 401 Pattern (bad credentials)
```
[FAST WARNING] POST /api/v1/auth/login → 401 (2.69ms) | page=LoginPage action=Login | ERROR: unauthorized
```
- Sub-3 ms response (immediate credential check)
- `chaos_mode: false` on log record — this is a real rejection, not injected
- Log level `WARNING` (not ERROR)

### Successful login
```
[FAST INFO] POST /api/v1/auth/login → 200 (0.92ms) | page=LoginPage action=Login
[FAST INFO] POST /api/v1/auth/login → 200 (0.80ms) | chaos_mode: false
```

---

## Root Cause

### 500 Root Cause — Chaos Mode
**File:** `vercel_app/main.py`, line 208  
When `CHAOS_MODE=true`, the login endpoint is also subject to the chaos injection logic. The error injected is `internal_server_error`, which maps to HTTP 500.

### 401 Root Cause — Wrong Credentials
The authentication system uses hardcoded credentials:
- **Username:** `admin`
- **Password:** `admin123`

Any other username/password combination returns 401. This is expected behaviour.

### Critical Design Limitation — No Token Validation
The login endpoint returns a random token (`secrets.token_urlsafe(32)`). This token is:
- Not stored anywhere (not in DB, not in memory)
- Not validated on any subsequent API endpoint
- Not a JWT (no claims, no expiry, no signature)

**Implication for incident response:** Even if a user has a "valid" token from a previous login, API endpoints do not check it. The `http.has_auth: true` flag in logs reflects only whether the `Authorization` header was *present*, not whether the token was *valid*. There is no real session management.

---

## Impact

- **500 failures:** Complete login outage — no user can access the application. All protected pages become inaccessible from the frontend.
- **401 failures:** Individual user cannot log in with wrong password. No system-wide impact.
- **PagerDuty:** Chaos-mode 500s on login fire PagerDuty incidents (rate-limited per 5 minutes).

---

## Diagnosis Steps

### Step 1 — Distinguish 500 from 401
```
# 500s (actionable):
service:cms-unified http.path:/api/v1/auth/login http.status_code:500

# 401s (expected bad credentials):
service:cms-unified http.path:/api/v1/auth/login http.status_code:401
```

### Step 2 — Check chaos mode for 500s
```bash
grep CHAOS_MODE .env
# Or check Vercel env vars
```

### Step 3 — Validate credentials manually
```bash
curl -X POST https://<api-host>/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
# Expected: 200 with access_token
```
If this returns 500, chaos mode is active. If it returns 401, credentials have been changed (check `vercel_app/main.py` line 208 for hardcoded values).

### Step 4 — Check if 401s are anomalous
A small number of 401s (< 5% of login attempts) is normal (typos, automation probing). A sudden spike in 401s could indicate a brute-force attempt — check `http.client_ip` distribution on 401 log records.

---

## Resolution

### For 500 — Disable chaos mode
See KB-002 Resolution: set `CHAOS_MODE=false` in Vercel environment variables and redeploy.

### For 401 — Correct credentials
The only valid credentials are `admin` / `admin123` (hardcoded in `vercel_app/main.py`). There is no password reset flow. If the hardcoded credentials have been changed in a deployment, locate the change in `vercel_app/main.py` line ~208 and revert or update accordingly.

### For a complete login outage — Emergency bypass
Because no endpoints validate the token, a user who already has a token (from any previous login session) can still make API calls directly. The frontend login gate is the only barrier. As a temporary measure, API calls can be made with any non-empty `Authorization` header.

> ⚠️ This is a security gap, not a recommended workaround for production. Document and remediate.

---

## Known Security Issues (for Runbook context)

These are documented limitations of the current system, not incidents, but must be understood during post-mortems:

| Issue | Location | Risk |
|---|---|---|
| Hardcoded credentials | `vercel_app/main.py:208` | Anyone with code access knows the password |
| No token validation | All API endpoints | Tokens are cosmetic; any value passes |
| No session expiry | Auth system | Tokens never expire |
| CORS `allow_origins=["*"]` | All services | Any origin can call the API |
| Hardcoded PagerDuty token in source | `vercel_app/main.py` | Credential exposure in code |
| `CHAOS_MODE=true` committed in `.env` | `.env` line 2 | Accidental production activation |

---

## Prevention

- Replace the hardcoded auth with a proper mechanism (JWT with a secret key, or Supabase Auth) before any production traffic carries real PII.
- Add a CI check that rejects deployments with `CHAOS_MODE=true` and hardcoded credentials.
- Rotate the PagerDuty API token and move it to an environment secret (not hardcoded in source).
- Add `POST /api/v1/auth/login` to the E2E smoke test suite so login outages are caught before deployment completes.

---

## Related Articles
- KB-002: Consent Creation Intermittent 500 Failures (Chaos Mode)
- KB-004: Revoke Consent 500 and 405 Failures
