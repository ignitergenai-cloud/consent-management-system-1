# Configuration Management Database (CMDB) — Consent Management System

**CMDB Record ID:** CMS-APP-001  
**Record Type:** Application Configuration Item (CI)  
**Last Updated:** 2026-09-02  
**Status:** Production

---

## 1. Application Identity

| Field | Value |
|---|---|
| **Application Name** | Consent Management System |
| **Alias / Short Name** | CMS |
| **Service Tag** | `cms-unified` (Vercel), `consent-api` / `consent-processor` / `notification-service` (microservices) |
| **Application Type** | Internal business application — consent lifecycle management |
| **Business Domain** | Compliance / Customer Communication |
| **Deployment Model** | Serverless (production) + Microservices (local/staging) |
| **Lifecycle State** | Active |
| **Criticality** | HIGH — compliance-adjacent; consent records required for lawful customer communication |

---

## 2. Business Context

### Purpose
Records, tracks, and enforces customer consent for communications across SMS, email, and push notification channels. Provides an audit trail of consent state transitions for regulatory compliance.

### Business Owners

| Role | Responsibility |
|---|---|
| Product Owner | Defines consent scope, channel support, expiry policies |
| Legal / Compliance | Consent record retention requirements, audit trail |
| Engineering Lead | Technical ownership, incident response authority |

### Business Impact if Unavailable

| Impact Area | Severity |
|---|---|
| Consent collection (new customers) | HIGH — new customers cannot provide consent |
| Consent revocation | CRITICAL — customers cannot withdraw consent (regulatory risk) |
| Communication dispatch | MEDIUM — downstream systems may send unsolicited communications |
| Audit/reporting | LOW — historical records remain available; no new events |

---

## 3. Architecture Mode

The system operates in two modes:

| Mode | Purpose | Environment |
|---|---|---|
| **Vercel Unified** | Single serverless FastAPI app | Production |
| **Microservices (Docker)** | Five containerised services | Local dev, staging |

> This CMDB record covers both modes. Production entries are marked **[PROD]**; local/staging entries are marked **[DEV]**.

---

## 4. Component Inventory

### 4.1 Application Services

| Component ID | Name | Technology | Mode | Version Source |
|---|---|---|---|---|
| CMS-SVC-001 | cms-unified API | FastAPI (Python 3.12) | **[PROD]** Vercel Serverless | `vercel_app/main.py` |
| CMS-SVC-002 | consent-api | FastAPI (Python 3.12) | **[DEV]** Docker, port 8000 | `services/consent-api/` |
| CMS-SVC-003 | consent-processor | Python asyncio consumer | **[DEV]** Docker, port 8001 | `services/consent-processor/` |
| CMS-SVC-004 | notification-service | FastAPI (Python 3.12) | **[DEV]** Docker, port 8002 | `services/notification-service/` |
| CMS-SVC-005 | incident-detector | FastAPI (Python 3.12) | **[DEV]** Docker, port 8003 | `services/incident-detector/` |
| CMS-SVC-006 | incident-bridge | FastAPI (Python 3.12) | **[DEV]** Docker, port 8004 | `services/incident-bridge/` |
| CMS-SVC-007 | Frontend (static) | HTML/CSS/JS | **[PROD]** Vercel Static | `frontend/` |

### 4.2 Data Stores

| Component ID | Name | Technology | Mode | Purpose |
|---|---|---|---|---|
| CMS-DB-001 | Supabase (Postgres) | PostgreSQL via PostgREST | **[PROD]** | Primary data store — all consent records, history, incidents |
| CMS-DB-002 | DynamoDB `cms-consents` | AWS DynamoDB (PAY_PER_REQUEST) | **[DEV]** | Primary data store for microservices mode |

#### Supabase (Production) Tables

| Table | Record Type | Retention |
|---|---|---|
| `consents` | Active consent records | Permanent |
| `consent_history` | Audit trail per consent event | Permanent |
| `cms_incidents` | Detected incidents | Permanent |
| `cms_metric_events` | Rolling short-term metrics | 2 hours (cron cleanup) |
| `cms_state` | Key-value system state (pause flags, caches) | Permanent |
| `cms_notification_queue` | Outbound notification queue | 24 hours post-send |

#### DynamoDB (Development/Staging)

| Attribute | Value |
|---|---|
| Table name | `cms-consents` |
| Billing mode | PAY_PER_REQUEST |
| Partition key | `PK` (string) |
| Sort key | `SK` (string) |
| GSI1 | Customer lookup (`GSI1PK`, `GSI1SK`) |
| GSI2 | Status lookup (`GSI2PK`, `GSI2SK`) |
| GSI3 | Channel lookup (`GSI3PK`, `GSI3SK`) |

### 4.3 Messaging Infrastructure (Microservices mode)

| Component ID | Name | Type | Connected From → To |
|---|---|---|---|
| CMS-MSG-001 | `cms-consent-events` | SNS Topic | consent-api → consent-processor, incident-detector |
| CMS-MSG-002 | `cms-notification-commands` | SNS Topic | consent-processor → notification-service |
| CMS-MSG-003 | `cms-notification-events` | SNS Topic | notification-service → consent-processor |
| CMS-MSG-004 | `cms-incident-events` | SNS Topic | incident-detector → incident-bridge |
| CMS-MSG-005 | `cms-internal-commands` | SNS Topic | incident-bridge → internal |
| CMS-MSG-006 | `cms-incident-commands` | SNS Topic | incident management → incident-detector |
| CMS-MSG-007 | `cms-system-events` | SNS Topic | system-wide broadcasts |
| CMS-MSG-Q001 | `cms-consent-processing-queue` | SQS FIFO (standard) | Processing consent events |
| CMS-MSG-Q002 | `cms-notification-queue` | SQS | Outbound notification commands |
| CMS-MSG-Q003 | `cms-notification-status-queue` | SQS | Notification delivery confirmations |
| CMS-MSG-Q004 | `cms-incident-detection-queue` | SQS | Events for anomaly detection |
| CMS-MSG-Q005 | `cms-incident-bridge-queue` | SQS | Incident escalation |
| CMS-MSG-Q006 | `cms-internal-commands-queue` | SQS | Internal command bus |
| CMS-MSG-Q007 | `cms-incident-commands-queue` | SQS | Incident management commands |

All queues have a corresponding DLQ (suffix `-dlq`) with `maxReceiveCount=3`.

### 4.4 External Integrations

| Component ID | Name | Type | Purpose | Dependency Level |
|---|---|---|---|---|
| CMS-EXT-001 | Resend | Email SaaS API | Outbound email notifications | HIGH — production notifications |
| CMS-EXT-002 | PagerDuty | Incident management SaaS | Auto-incident creation on HTTP 500 | MEDIUM — alerting only |
| CMS-EXT-003 | New Relic | Observability SaaS | Log aggregation, structured log shipping | MEDIUM — observability |
| CMS-EXT-004 | Vercel | Serverless platform | API + frontend hosting | CRITICAL — all production traffic |

### 4.5 Scheduled Jobs (Cron)

| Job ID | Name | Schedule | Handler |
|---|---|---|---|
| CMS-CRON-001 | Process notifications | Daily 08:00 UTC | `/api/cron/process-notifications` |
| CMS-CRON-002 | Check expired consents | Daily 09:00 UTC | `/api/cron/check-expired-consents` |
| CMS-CRON-003 | Detect anomalies | Daily 10:00 UTC | `/api/cron/detect-anomalies` |
| CMS-CRON-004 | Cleanup | Daily 02:00 UTC | `/api/cron/cleanup` |

---

## 5. Hosting and Infrastructure

### Production (Vercel)

| Attribute | Value |
|---|---|
| Platform | Vercel (Serverless) |
| API Project | `cms-unified` |
| API URL | `https://cms-unified-api-ai-igniters.vercel.app` |
| Frontend URL | `https://cms-frontend-pied-zeta.vercel.app` |
| Entrypoint | `api/index.py` |
| Function timeout | 60 seconds |
| Function memory | 1024 MB |
| Deployment trigger | `node deploy-to-vercel.js` |
| Vercel config | `vercel.json` |
| Region | Default Vercel region (auto) |

### Development / Staging (Docker)

| Attribute | Value |
|---|---|
| Platform | Docker Compose |
| Compose file | `docker-compose.yml` |
| LocalStack (AWS mock) | `localhost:4566` |
| Services | 7 containers (5 app + 1 LocalStack + 1 DB proxy) |

---

## 6. Configuration Management

### Environment Variables — Production (Vercel)

| Variable | Classification | Default | Notes |
|---|---|---|---|
| `CHAOS_MODE` | Operational | `false` | **Must be `false` in production.** Committed as `true` in `.env` — see Known Risks |
| `SUPABASE_URL` | Secret | — | Set in Vercel env vars |
| `SUPABASE_KEY` | Secret | — | Service role key; set in Vercel env vars |
| `RESEND_API_KEY` | Secret | — | Set in Vercel env vars |
| `CRON_SECRET` | Secret | `""` | Bearer token for cron endpoints; empty = no auth (dev only) |
| `NEWRELIC_LICENSE_KEY` | Secret | hardcoded | See Known Risks — move to env var |
| `PAGERDUTY_INTEGRATION_KEY` | Secret | hardcoded | See Known Risks — move to env var |
| `FAILURE_RATE_THRESHOLD` | Operational | `0.3` | Fraction (30%) — anomaly detection trigger |
| `DB_TIMEOUT` | Operational | `10` | Supabase PostgREST request timeout in seconds |

### Environment Variables — Microservices (Docker)

| Variable | Classification | Default |
|---|---|---|
| `DYNAMODB_TABLE_NAME` | Operational | `cms-consents` |
| `AWS_ENDPOINT_URL` | Infrastructure | `http://localhost:4566` |
| `AWS_DEFAULT_REGION` | Infrastructure | `us-east-1` |
| `AWS_ACCESS_KEY_ID` | Secret (mock) | `test` |
| `AWS_SECRET_ACCESS_KEY` | Secret (mock) | `test` |
| `SNS_TOPIC_ARN_*` | Infrastructure | See shared config |
| `SQS_QUEUE_URL_*` | Infrastructure | See shared config |

### Config file locations

| File | Purpose |
|---|---|
| `.env` | Local dev defaults (do not use in production) |
| `.env.example` | Template for onboarding |
| `vercel.json` | Vercel routing, cron, function settings |
| `vercel_app/config.py` | Vercel app settings with Pydantic BaseSettings |
| `services/shared/src/cms_shared/config.py` | Microservices shared settings |

---

## 7. Network and Access

### API Endpoints (Production)

| Endpoint Group | Base Path | Auth Required |
|---|---|---|
| Auth | `POST /api/v1/auth/login` | No (provides token) |
| Consents | `/api/v1/consents/*` | Yes (header present — not validated) |
| Analytics | `GET /api/v1/analytics/consents` | Yes (header present) |
| Incidents | `/api/v1/incidents/*` | Yes (header present) |
| Cron | `/api/cron/*` | `CRON_SECRET` bearer token |
| Health | `/api/v1/health` | No |
| Health (ready) | `/api/v1/health/ready` | No |

### CORS Policy
- **Current configuration:** `allow_origins=["*"]` on all services — any origin can call the API.
- **Recommended:** Restrict to `https://cms-frontend-pied-zeta.vercel.app` in production.

### Authentication
- **Mechanism:** Hardcoded credentials (`admin` / `admin123`). Returns a random bearer token.
- **Token validation:** None — any non-empty `Authorization` header is accepted on all API endpoints.
- **Implication:** `http.has_auth: true` in logs confirms the header was present, not that the token is valid.

---

## 8. Consent State Machine

```
PENDING ──► SENT ──► DELIVERED ──► GRANTED  (terminal)
                                 ──► DENIED   (terminal)
            ──► FAILED ──► PENDING (retry, max 3 per notification attempt)
            ──► EXPIRED          (terminal)
GRANTED ──► REVOKED             (terminal)
```

- Max notification retries: 3 (consent-processor `consent_workflow.py`)
- Default consent expiry: configurable; checked by cron at 09:00 UTC
- Revocation endpoint: `POST /api/v1/consents/{id}/revoke`

---

## 9. Observability

### Logging
- **Platform:** New Relic (log shipping via `ObservabilityMiddleware`)
- **Format:** JSON structured logs
- **Key fields:** `service`, `level`, `http.status_code`, `http.path`, `duration_ms`, `correlation_id`, `chaos_mode`, `ui.page`, `ui.action`, `perf.category`
- **Performance categories:** `fast` (<100ms), `normal` (100–500ms), `slow` (500–2000ms), `very_slow` (>2000ms)
- **Skipped paths:** `/health`, `/health/ready`, `/metrics`

### Alerting
- **Platform:** PagerDuty (Service ID: `PUMAG77`)
- **Trigger:** Any HTTP 500 response
- **Rate limit:** 1 incident per `{service}:{path}:{incident_type}` per 5 minutes
- **Known noise source:** Chaos mode generates synthetic PagerDuty incidents — check `chaos_mode: true` field before treating as a real incident

### Health Endpoints

| Endpoint | Checks | Use for |
|---|---|---|
| `GET /api/v1/health` | Process alive only | Liveness probe |
| `GET /api/v1/health/ready` | DB connectivity | Readiness probe (microservices) |

---

## 10. Security Classification

| Area | Current State | Risk | Recommended Action |
|---|---|---|---|
| Authentication | Hardcoded credentials; no token validation | CRITICAL | Replace with JWT or Supabase Auth |
| PagerDuty API token | Hardcoded in `vercel_app/main.py` | HIGH | Move to `PAGERDUTY_INTEGRATION_KEY` env var; rotate token |
| New Relic license key | Hardcoded in `vercel_app/observability.py` | HIGH | Move to `NEWRELIC_LICENSE_KEY` env var; rotate key |
| `CHAOS_MODE` in `.env` | Committed as `true` | HIGH | Set to `false`; add CI check blocking `CHAOS_MODE=true` in deployments |
| CORS | `allow_origins=["*"]` | MEDIUM | Restrict to known frontend origin |
| `CRON_SECRET` | Empty by default | MEDIUM | Enforce non-empty in production |
| Transport | HTTPS enforced by Vercel | LOW | No action required |
| Secrets in source code | Multiple (see above) | HIGH | Audit all source files and rotate exposed credentials |

---

## 11. Known Risks and Open Issues

| Risk ID | Description | Severity | Status |
|---|---|---|---|
| CMS-RISK-001 | `CHAOS_MODE=true` committed in `.env` — accidental production activation risk | HIGH | Open |
| CMS-RISK-002 | PagerDuty and New Relic API tokens hardcoded in source | HIGH | Open |
| CMS-RISK-003 | No real authentication — any caller with an `Authorization` header can access all data | CRITICAL | Open |
| CMS-RISK-004 | Analytics endpoint full-table scan — O(n) latency growth with consent volume | MEDIUM | Open |
| CMS-RISK-005 | No DELETE route on Vercel app — frontend calling DELETE `/consents/{id}` gets 405 | MEDIUM | Open |
| CMS-RISK-006 | Liveness probe does not verify database connectivity — false-healthy during DB outage | MEDIUM | Open |
| CMS-RISK-007 | No circuit breakers or automatic failsafes on downstream dependency failures | MEDIUM | Open |
| CMS-RISK-008 | SNS publish and DB write are not atomic — orphaned PENDING consents possible (Scenario B) | MEDIUM | Open |
| CMS-RISK-009 | Notification retry has no enforced maximum in Vercel cron — potential infinite retry | LOW | Open |

---

## 12. Dependencies

### Upstream (what CMS depends on)

| Dependency | Type | Criticality | Failure Impact |
|---|---|---|---|
| Vercel platform | Hosting | CRITICAL | Complete outage |
| Supabase (Postgres) | Database | CRITICAL | All data operations fail |
| Resend API | Email delivery | HIGH | Notifications not delivered |
| PagerDuty | Alerting | MEDIUM | No incident alerts; monitoring blind |
| New Relic | Observability | MEDIUM | Log visibility lost |
| AWS (SNS/SQS) | Messaging | HIGH (dev/staging) | Consent workflow stalls |

### Downstream (what depends on CMS)

| Consumer | How It Uses CMS | Impact of CMS Outage |
|---|---|---|
| Communication Dispatch | Queries consent status before sending | May send unsolicited communications (compliance risk) |
| Customer Portal | Reads/writes consent preferences | Consent UI unavailable |
| Incident Management System | Reads incident history; generates hypotheses | Reduced post-mortem data |

---

## 13. Deployment and Change Management

### Deployment Procedure (Production — Vercel)
1. Verify `CHAOS_MODE=false` in Vercel environment variables.
2. Run `node deploy-to-vercel.js` from repo root.
3. Confirm deployment in Vercel Dashboard.
4. Run smoke test sequence (see Developer Runbook §5).
5. Monitor New Relic for elevated error rates for 10 minutes post-deploy.

### Schema Changes (Supabase)
- All schema changes applied via Supabase SQL Editor or migration tool.
- Reference schema: `schema.sql` at repo root.
- No automated migration tooling currently configured.

### Configuration Changes
- Vercel environment variable changes take effect on next redeployment.
- Local `.env` changes take effect on service restart.

---

## 14. Disaster Recovery

### Recovery Time Objective (RTO) / Recovery Point Objective (RPO)

| Scenario | RTO Target | RPO Target | Notes |
|---|---|---|---|
| Vercel deployment failure | 15 min | 0 (stateless) | Rollback to previous Vercel deployment |
| Supabase outage | Supabase SLA | Supabase SLA | Managed by Supabase; no self-hosted fallback |
| Chaos mode accidental activation | 10 min | 0 | Disable env var, redeploy |
| DynamoDB table deleted (dev) | 30 min | 0 (test data) | Re-run `01-dynamodb.sh` init script |

### Backup
- **Supabase:** Managed automated backups per Supabase tier.
- **DynamoDB (dev):** No backup configured; dev data is ephemeral.

---

## 15. Related Documentation

| Document | Location | Purpose |
|---|---|---|
| Developer Runbook | `docs/runbook/DEVELOPER-RUNBOOK.md` | Incident response procedures, operational tasks |
| KB-001 | `docs/knowledge-base/KB-001-dynamodb-table-not-found.md` | DynamoDB not found incident |
| KB-002 | `docs/knowledge-base/KB-002-consent-creation-500-chaos-mode.md` | Chaos mode 500s on consent creation |
| KB-003 | `docs/knowledge-base/KB-003-sns-publish-failure-queue-idle.md` | SNS pipeline stall |
| KB-004 | `docs/knowledge-base/KB-004-revoke-405-500-failures.md` | Revoke 405/500 failures |
| KB-005 | `docs/knowledge-base/KB-005-performance-degradation-slow-requests.md` | API performance degradation |
| KB-006 | `docs/knowledge-base/KB-006-authentication-500-401-failures.md` | Authentication failures |
| Architecture | `docs/ARCHITECTURE.md` | System architecture overview |
| API Design | `docs/API_DESIGN.md` | API contract and endpoint reference |
| Data Model | `docs/DATA_MODEL.md` | DynamoDB and Postgres data model |
| Infrastructure | `docs/INFRASTRUCTURE.md` | Infrastructure setup |
| Security | `docs/SECURITY.md` | Security model |
| Deployment | `docs/DEPLOYMENT.md` | Deployment guide |
| Integration | `docs/INTEGRATION.md` | Integration patterns |

---

*This CMDB record should be reviewed and updated after any major incident, architectural change, or new integration is added.*
