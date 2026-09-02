# Consent Management System — Developer Runbook

**Version:** 1.0  
**Application:** consent-management-system  
**Last Updated:** 2026-09-02  
**Audience:** On-call engineers, SREs, developers responding to incidents

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Quick Reference](#2-architecture-quick-reference)
3. [Deployment Topology](#3-deployment-topology)
4. [Key Configuration Variables](#4-key-configuration-variables)
5. [Health Checks](#5-health-checks)
6. [Common Incident Playbooks](#6-common-incident-playbooks)
7. [Chaos Mode — Critical Warning](#7-chaos-mode--critical-warning)
8. [Database Operations](#8-database-operations)
9. [Messaging System (SNS/SQS)](#9-messaging-system-snssqs)
10. [Cron Jobs](#10-cron-jobs)
11. [Observability and Alerting](#11-observability-and-alerting)
12. [Known System Limitations](#12-known-system-limitations)
13. [Escalation and Contacts](#13-escalation-and-contacts)

---

## 1. System Overview

The Consent Management System (CMS) records, tracks, and manages customer consent for communications across multiple channels (SMS, email, push). It operates in two modes:

| Mode | Description | Used In |
|---|---|---|
| **Vercel Unified** | Single serverless FastAPI app; Supabase (Postgres) + Resend email | Production (Vercel) |
| **Microservices** | Five Docker services; DynamoDB + SNS/SQS | Local dev / Kubernetes |

> **Production is always the Vercel unified deployment.** The microservices stack is used for local development and staging only.

### Consent Lifecycle States
```
PENDING → SENT → DELIVERED → GRANTED (terminal)
                            → DENIED  (terminal)
         → FAILED → PENDING (retry, max 3 attempts)
         → EXPIRED          (terminal)
GRANTED → REVOKED           (terminal)
```

---

## 2. Architecture Quick Reference

### Vercel Production (cms-unified)

```
Frontend (Vercel static)
    │
    ▼
cms-unified API (Vercel Serverless, /api/index.py)
    │
    ├─── Supabase (Postgres via PostgREST)
    │        Tables: consents, consent_history, cms_incidents,
    │                cms_metric_events, cms_state, cms_notification_queue
    │
    ├─── Resend API (email notifications)
    │
    └─── New Relic (log shipping, fire-and-forget)
         PagerDuty (auto-incident on 500)

Cron jobs (Vercel Cron):
    /api/cron/process-notifications   08:00 UTC daily
    /api/cron/check-expired-consents  09:00 UTC daily
    /api/cron/detect-anomalies        10:00 UTC daily
    /api/cron/cleanup                 02:00 UTC daily
```

### Microservices (local / staging)

```
consent-api (port 8000)
    ├── DynamoDB table: cms-consents
    └── SNS: cms-consent-events →
            SQS: cms-consent-processing-queue → consent-processor (port 8001)
            SQS: cms-incident-detection-queue → incident-detector (port 8003)

consent-processor → SNS: cms-notification-commands →
            SQS: cms-notification-queue → notification-service (port 8002)

notification-service → SNS: cms-notification-events →
            SQS: cms-notification-status-queue → consent-processor

incident-detector → SNS: cms-incident-events →
            SQS: cms-incident-bridge-queue → incident-bridge (port 8004)
```

---

## 3. Deployment Topology

### Production (Vercel)
- **API:** `https://cms-unified-api-ai-igniters.vercel.app`
- **Frontend:** `https://cms-frontend-pied-zeta.vercel.app`
- **Deployment script:** `node deploy-to-vercel.js` (at repo root)
- **Vercel project:** `cms-unified`
- **Function timeout:** 60 seconds
- **Function memory:** 1024 MB

### Local Development
```bash
# Full microservices stack:
docker compose up

# Vercel unified (simulates production):
pip install -r requirements.txt
uvicorn api.index:app --reload --port 8000
```

### Environment files
| File | Purpose |
|---|---|
| `.env` | Local dev defaults — **do not use in production** |
| `.env.example` | Template for required variables |
| Vercel Dashboard | Production environment variables |

---

## 4. Key Configuration Variables

### Critical variables (Vercel production)

| Variable | Purpose | Safe Value |
|---|---|---|
| `CHAOS_MODE` | Enables random 500 injection | **`false`** — must never be `true` in prod |
| `SUPABASE_URL` | Supabase project URL | Set in Vercel env vars |
| `SUPABASE_KEY` | Supabase service role key | Set in Vercel env vars |
| `RESEND_API_KEY` | Email delivery via Resend | Set in Vercel env vars |
| `CRON_SECRET` | Bearer token for cron endpoint auth | Set in Vercel env vars |
| `NEWRELIC_LICENSE_KEY` | Log shipping to New Relic | Set in Vercel env vars |
| `FAILURE_RATE_THRESHOLD` | Anomaly detection trigger (default: 0.3 = 30%) | `0.3` |

### Microservices (local)

| Variable | Purpose | Default |
|---|---|---|
| `DYNAMODB_TABLE_NAME` | DynamoDB table name | `cms-consents` |
| `AWS_ENDPOINT_URL` | LocalStack endpoint | `http://localhost:4566` |
| `AWS_DEFAULT_REGION` | AWS region | `us-east-1` |
| `CHAOS_MODE` | Chaos injection | `false` |

---

## 5. Health Checks

### Vercel unified
```bash
# Liveness (does NOT check database):
curl https://cms-unified-api-ai-igniters.vercel.app/api/v1/health
# Expected: {"status": "ok", "service": "cms-unified", "timestamp": "..."}

# Full smoke test sequence:
curl -X POST .../api/v1/auth/login -d '{"username":"admin","password":"admin123"}'
curl .../api/v1/consents?page=1&page_size=1
curl .../api/v1/analytics/consents
curl .../api/v1/incidents
```

### Microservices (local)
```bash
# consent-api liveness:
curl http://localhost:8000/api/v1/health

# consent-api readiness (checks DynamoDB):
curl http://localhost:8000/api/v1/health/ready
# If this returns non-200, DynamoDB is not reachable

# Check all service health:
for port in 8000 8001 8002 8003 8004; do
  echo "Port $port:" && curl -s http://localhost:$port/api/v1/health
done
```

---

## 6. Common Incident Playbooks

---

### P1-A: 100% Consent Creation Failure (ResourceNotFoundException)

**Indicator:** CRITICAL log — `DynamoDB table 'cms-consents' not found`  
**KB Article:** KB-001

**Response steps:**
1. Check `CHAOS_MODE` in running environment:
   ```bash
   docker exec consent-api env | grep CHAOS_MODE
   ```
2. If `CHAOS_MODE=true` → set to `false`, restart service.
3. If `CHAOS_MODE=false` → check DynamoDB table:
   ```bash
   aws --endpoint-url http://localhost:4566 dynamodb describe-table --table-name cms-consents
   ```
4. If table missing → re-run init scripts:
   ```bash
   bash infrastructure/localstack/init-aws.d/01-dynamodb.sh
   ```
5. Verify recovery: make a test `POST /api/v1/consents` and confirm 201.
6. Check `cms-consent-processing-queue` depth — re-publish any orphaned PENDING consents if needed (see KB-003).

**Escalate if:** Table missing in production AWS — requires DBA and infrastructure team.

---

### P1-B: Complete Consent Creation Outage (Vercel, Chaos Mode)

**Indicator:** Multiple ERROR logs on `POST /api/v1/consents` with `chaos_mode: true`  
**KB Article:** KB-002

**Response steps:**
1. Go to Vercel Dashboard → Project (cms-unified) → Settings → Environment Variables.
2. Set `CHAOS_MODE=false`.
3. Trigger redeployment.
4. Verify recovery: `POST /api/v1/consents` returns 201.
5. Close any chaos-generated PagerDuty incidents (check titles for synthetic error strings).

---

### P1-C: Login Outage (All Users Cannot Authenticate)

**Indicator:** ERROR logs on `POST /api/v1/auth/login` with status 500  
**KB Article:** KB-006

**Response steps:**
1. Check `chaos_mode` field on the error log record.
2. If `chaos_mode: true` → disable (same as P1-B steps 1–3).
3. Manually verify credentials work:
   ```bash
   curl -X POST https://<api>/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"admin123"}'
   ```
4. If 401 → credentials changed in source; check `vercel_app/main.py` ~line 208.

> ⚠️ **Note:** Even during a login outage, existing API sessions still work because tokens are not validated on API endpoints. Direct API calls with any non-empty `Authorization` header will succeed.

---

### P2-A: Processing Queue Idle

**Indicator:** WARNING — `Consent processor queue idle — no new PENDING events received in 15 minutes`  
**KB Article:** KB-003

**Response steps:**
1. Check if consent creation is also failing (P1-A or P1-B active) — queue idle is a downstream symptom.
2. Check queue depth:
   ```bash
   aws --endpoint-url http://localhost:4566 sqs get-queue-attributes \
     --queue-url .../cms-consent-processing-queue \
     --attribute-names ApproximateNumberOfMessages
   ```
3. Check for orphaned PENDING consents (> 30 min old) in DB.
4. If SNS subscriptions missing → re-run `04-sns-subscriptions.sh`.
5. If consent-processor crashed → `docker compose restart consent-processor`.

---

### P2-B: Consent Revocation Failing (405 or 500)

**Indicator:** WARNING logs on `DELETE /api/v1/consents/{id}` returning 405; or ERROR on `POST .../revoke` returning 500  
**KB Article:** KB-004

**405 — Wrong HTTP method:**
1. Identify frontend version calling DELETE.
2. Apply server-side alias (see KB-004 Resolution) as immediate fix.
3. Track frontend fix in next sprint.

**500 — Chaos mode:**
1. Disable chaos mode (see P1-B).

---

### P2-C: Slow API Responses (> 1 second)

**Indicator:** Sustained `perf.category: slow` or `perf.category: very_slow` on `/api/v1/analytics/consents`  
**KB Article:** KB-005

**Response steps:**
1. Check consent table row count:
   ```sql
   SELECT COUNT(*) FROM consents;
   ```
2. If > 50,000 rows, the analytics endpoint is the bottleneck.
3. Trigger cleanup cron manually:
   ```bash
   curl -H "Authorization: Bearer <cron_secret>" https://<api>/api/cron/cleanup
   ```
4. Apply `LIMIT 10000` patch to analytics endpoint as immediate mitigation (see KB-005).

---

### P3: PagerDuty Alert Storm (Multiple Simultaneous Incidents)

**Indicator:** 3–5 PagerDuty incidents firing in < 5 minutes with different synthetic error titles  

**This pattern indicates chaos mode is active.** The five chaos scenarios each have their own PagerDuty rate-limit key, so they all fire independently.

**Response steps:**
1. Check most recent `POST /api/v1/consents` error log for `chaos_mode: true`.
2. Disable chaos mode (P1-B steps).
3. Bulk-acknowledge/resolve the PagerDuty incidents as "noise / chaos mode" once chaos mode is confirmed.

---

## 7. Chaos Mode — Critical Warning

> **⚠️ CHAOS MODE MUST NEVER BE ENABLED IN PRODUCTION**

Chaos mode (`CHAOS_MODE=true`) is a development/testing tool that randomly injects HTTP 500 failures into:
- `POST /api/v1/consents` (5 scenarios)
- `POST /api/v1/consents/{id}/revoke` (1 scenario)
- `POST /api/v1/auth/login` (1 scenario)

**Current state:** The committed `.env` file has `CHAOS_MODE=true`. This is the most likely cause of any unexplained 500 errors in non-production environments.

**How to verify:**
```bash
grep CHAOS_MODE .env                    # local / microservices
# Vercel Dashboard → env vars          # production
```

**How to disable:**
```bash
# Local:
sed -i 's/CHAOS_MODE=true/CHAOS_MODE=false/' .env
docker compose restart

# Vercel: Dashboard → Environment Variables → set CHAOS_MODE=false → redeploy
```

**Chaos mode tells you it's active:** Every chaos-injected failure includes `chaos_mode: true` in the structured log record. A 500 without this field is a real failure.

---

## 8. Database Operations

### Vercel Production — Supabase

**Tables:**

| Table | Purpose | Retention |
|---|---|---|
| `consents` | Main consent records | Permanent |
| `consent_history` | Audit trail per consent | Permanent |
| `cms_incidents` | Detected incidents | Permanent |
| `cms_metric_events` | Short-term metrics for anomaly detection | 2 hours (cleaned by cron) |
| `cms_state` | Key-value system state (pause/resume) | Permanent |
| `cms_notification_queue` | Outbound notification queue | 24 hours post-send (cleaned by cron) |

**Common queries:**
```sql
-- Count consents by status:
SELECT status, COUNT(*) FROM consents GROUP BY status;

-- Find stuck PENDING consents (> 30 min):
SELECT id, customer_id, created_at FROM consents 
WHERE status = 'PENDING' AND created_at < NOW() - INTERVAL '30 minutes';

-- Check notification queue depth:
SELECT status, COUNT(*) FROM cms_notification_queue GROUP BY status;

-- Pending notifications with high attempt count:
SELECT id, attempts, last_error FROM cms_notification_queue 
WHERE status = 'pending' AND attempts >= 2;

-- Recent incidents:
SELECT id, title, status, severity, created_at FROM cms_incidents 
ORDER BY created_at DESC LIMIT 20;

-- Check cleanup ran (metric_events should only have recent rows):
SELECT MIN(created_at), MAX(created_at), COUNT(*) FROM cms_metric_events;
```

### Microservices — DynamoDB

**Table:** `cms-consents` (PAY_PER_REQUEST, single-table design)  
**GSIs:** `GSI1` (customer lookup), `GSI2` (status lookup), `GSI3` (channel lookup)

```bash
# List all items (dev only — expensive on large tables):
aws --endpoint-url http://localhost:4566 dynamodb scan \
  --table-name cms-consents

# Get specific consent:
aws --endpoint-url http://localhost:4566 dynamodb get-item \
  --table-name cms-consents \
  --key '{"PK": {"S": "CONSENT#<id>"}, "SK": {"S": "METADATA"}}'

# Query by status (using GSI2):
aws --endpoint-url http://localhost:4566 dynamodb query \
  --table-name cms-consents \
  --index-name GSI2 \
  --key-condition-expression "GSI2PK = :pk" \
  --expression-attribute-values '{":pk": {"S": "STATUS#PENDING"}}'
```

---

## 9. Messaging System (SNS/SQS)

### Check queue depths (microservices)
```bash
ENDPOINT="http://localhost:4566"
ACCOUNT="000000000000"
REGION="us-east-1"

for queue in \
  cms-consent-processing-queue \
  cms-notification-queue \
  cms-notification-status-queue \
  cms-incident-detection-queue \
  cms-incident-bridge-queue \
  cms-internal-commands-queue \
  cms-incident-commands-queue; do
    echo -n "$queue: "
    aws --endpoint-url $ENDPOINT sqs get-queue-attributes \
      --queue-url "$ENDPOINT/$ACCOUNT/$queue" \
      --attribute-names ApproximateNumberOfMessages \
      --query 'Attributes.ApproximateNumberOfMessages' \
      --output text
done
```

### Check DLQ depths (indicates processing failures)
```bash
for queue in \
  cms-consent-processing-queue-dlq \
  cms-notification-queue-dlq; do
    echo -n "$queue: "
    aws --endpoint-url $ENDPOINT sqs get-queue-attributes \
      --queue-url "$ENDPOINT/$ACCOUNT/$queue" \
      --attribute-names ApproximateNumberOfMessages \
      --query 'Attributes.ApproximateNumberOfMessages' \
      --output text
done
```

### Manually re-drive a message from DLQ
```bash
# Receive from DLQ:
aws --endpoint-url $ENDPOINT sqs receive-message \
  --queue-url "$ENDPOINT/$ACCOUNT/cms-consent-processing-queue-dlq"

# Send to main queue:
aws --endpoint-url $ENDPOINT sqs send-message \
  --queue-url "$ENDPOINT/$ACCOUNT/cms-consent-processing-queue" \
  --message-body '<message-body-from-above>'
```

### Verify SNS subscriptions
```bash
aws --endpoint-url $ENDPOINT sns list-subscriptions
```

---

## 10. Cron Jobs

All cron jobs require the `Authorization: Bearer <CRON_SECRET>` header. If `CRON_SECRET` is empty, all requests are allowed (local dev default).

| Job | Schedule | Max items | Expected duration |
|---|---|---|---|
| `/api/cron/process-notifications` | 08:00 UTC | 20 notifications | < 30 s |
| `/api/cron/check-expired-consents` | 09:00 UTC | 100 consents | < 10 s |
| `/api/cron/detect-anomalies` | 10:00 UTC | — | < 5 s |
| `/api/cron/cleanup` | 02:00 UTC | Unbounded delete | < 15 s |

### Trigger manually
```bash
CRON_SECRET=$(grep CRON_SECRET .env | cut -d= -f2)
BASE_URL="https://cms-unified-api-ai-igniters.vercel.app"

curl -H "Authorization: Bearer $CRON_SECRET" "$BASE_URL/api/cron/process-notifications"
curl -H "Authorization: Bearer $CRON_SECRET" "$BASE_URL/api/cron/check-expired-consents"
curl -H "Authorization: Bearer $CRON_SECRET" "$BASE_URL/api/cron/detect-anomalies"
curl -H "Authorization: Bearer $CRON_SECRET" "$BASE_URL/api/cron/cleanup"
```

### Verify cron ran
```sql
-- Cleanup: metric_events should only have rows from last 2 hours:
SELECT MIN(created_at), MAX(created_at) FROM cms_metric_events;

-- Expired consents: no PENDING consents past their expires_at:
SELECT COUNT(*) FROM consents WHERE status = 'PENDING' AND expires_at < NOW();

-- Notifications: no unsent notifications older than 10 minutes:
SELECT COUNT(*) FROM cms_notification_queue 
WHERE status = 'pending' AND created_at < NOW() - INTERVAL '10 minutes';
```

---

## 11. Observability and Alerting

### New Relic
- **Log ingestion key:** `350ed5b6c2fb675958bb75486c57c570679dNRAL` (rotate this — it is in source code)
- **Key log fields:** `service`, `level`, `http.status_code`, `http.path`, `duration_ms`, `correlation_id`, `chaos_mode`, `ui.page`, `ui.action`, `perf.category`

**Useful NRQL queries:**
```sql
-- Error rate by endpoint (last 1 hour):
SELECT count(*) FROM Log 
WHERE service = 'cms-unified' AND level = 'ERROR'
FACET http.path SINCE 1 hour ago

-- p95 response time:
SELECT percentile(duration_ms, 95) FROM Log 
WHERE service = 'cms-unified'
FACET http.path SINCE 1 hour ago

-- Chaos mode incidents:
SELECT count(*) FROM Log 
WHERE chaos_mode = true AND level = 'ERROR'
SINCE 24 hours ago

-- Slow requests:
SELECT count(*) FROM Log
WHERE service = 'cms-unified' AND perf.category IN ('slow', 'very_slow')
FACET http.path SINCE 1 hour ago
```

### PagerDuty
- **Service ID:** `PUMAG77`
- **Auto-incident trigger:** Any HTTP 500 on any endpoint (rate-limited to 1 per endpoint per 5 minutes)
- **Chaos mode incidents:** Identified by synthetic error message in title (see KB-002)

> ⚠️ The PagerDuty API token (`u+2Kf6xufQUhr1CLJsBw`) is hardcoded in `vercel_app/main.py`. **Rotate this token immediately** and move it to an environment variable.

### Correlation IDs
Every request generates a `correlation_id` (UUID). Use it to trace a request across all service logs:
```
service:cms-unified correlation_id:"<uuid>"
```

---

## 12. Known System Limitations

These are documented gaps, not active incidents. Relevant during post-mortems and RCA.

| Limitation | Location | Notes |
|---|---|---|
| **No real authentication** | `vercel_app/main.py:208` | Hardcoded credentials; tokens not validated on any endpoint |
| **Analytics full-table scan** | `vercel_app/main.py:582` | O(n) with consent count; no caching |
| **Chaos mode committed as `true`** | `.env` line 2 | Must be set to `false` in all environments |
| **No DELETE route on Vercel** | `vercel_app/main.py` | Frontend calling DELETE gets 405 |
| **Liveness probe doesn't check DB** | `/api/v1/health` | Service appears healthy when DB is down |
| **No circuit breakers** | All services | No automatic failsafe on downstream dependency failures |
| **PagerDuty token in source code** | `vercel_app/main.py` | Security exposure |
| **New Relic key in source code** | `vercel_app/observability.py` | Security exposure |
| **`CRON_SECRET` empty by default** | `vercel_app/config.py` | Cron endpoints unprotected if not configured |
| **Notification retry has no max limit** | `vercel_app/cron_routes.py` | Notifications can be retried indefinitely |
| **SNS/DB not atomic** | `consent_service.py` | Consent can be written but event not published (Scenario B orphan) |

---

## 13. Escalation and Contacts

| Escalation Path | When to Use |
|---|---|
| DynamoDB table deleted in production AWS | P1-A and table restore needed |
| Supabase database unavailable | All Vercel-mode operations failing |
| PagerDuty alerts not acknowledged after 15 min | Auto-escalation per PagerDuty service config |
| Vercel deployment failing | Deployment script errors; check Vercel Dashboard |

### Quick reference — who owns what
| Component | Owner |
|---|---|
| Vercel deployments | Platform / DevOps |
| Supabase schema changes | Backend team |
| Frontend API calls (405 issue) | Frontend team |
| Chaos mode configuration | Any engineer with Vercel access |
| PagerDuty service config | On-call lead |

---

*For knowledge base articles covering individual failure modes in detail, see [docs/knowledge-base/](../knowledge-base/).*
