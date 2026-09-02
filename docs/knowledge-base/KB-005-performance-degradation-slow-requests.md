# KB-005: API Performance Degradation — Slow Requests

**Article ID:** KB-005  
**Application:** consent-management-system / cms-unified (Vercel)  
**Severity:** MEDIUM  
**Affected Endpoints:** `GET /api/v1/consents`, `GET /api/v1/analytics/consents`  
**Last Updated:** 2026-09-02

---

## Summary

Production logs consistently show `GET /api/v1/consents` and `GET /api/v1/analytics/consents` taking 700–1800 ms, categorised as `perf.category: slow` or `perf.category: very_slow`. The analytics endpoint performs a full table scan on every request. Response times are elevated across all client IPs and geographies, indicating a server-side cause rather than network latency.

---

## Performance Thresholds (ObservabilityMiddleware)

| Category | Duration |
|---|---|
| `fast` | < 100 ms |
| `normal` | 100–500 ms |
| `slow` | 500–2000 ms |
| `very_slow` | > 2000 ms |

The vast majority of observed requests fall in the `slow` band (700–1400 ms). Occasional `very_slow` requests (1600–2945 ms) appear on the consent list and analytics endpoints.

---

## Observed Patterns

### `GET /api/v1/consents`
- Typical range: 290–1690 ms across the log sample
- `page_size=10` requests tend to be faster (300–900 ms)
- `page_size=25` requests tend to be slower (700–1700 ms)
- Both authenticated and unauthenticated requests show similar latency

### `GET /api/v1/analytics/consents`
- Typical range: 300–1780 ms
- Called frequently as a dashboard widget — every dashboard page load triggers this endpoint
- No pagination — fetches all consents on every call

### `GET /api/v1/consents` (very slow outliers)
- `2945 ms` observed (page_size=10)
- `2588 ms` observed on `/api/v1/incidents`

### Cron job performance
- `/api/cron/cleanup` — 2387 ms (`slow_request: true`)
- `/api/cron/process-notifications` — 6166 ms (`perf.category: very_slow`) — exceeds 5 second threshold

---

## Root Cause

### 1. Analytics endpoint full-table scan
**File:** `vercel_app/main.py`, line 582  
`GET /api/v1/analytics/consents` fetches **all consents** from Supabase on every call, then computes aggregations in Python. There is no server-side aggregation, no caching, and no limit. As the consents table grows, this endpoint degrades linearly.

```python
# Current implementation (simplified):
all_consents = await db.select("consents")  # unbounded full scan
# then compute counts in Python
```

### 2. Supabase/PostgREST cold start latency
Vercel serverless functions have cold start overhead, and the Supabase PostgREST connection must be re-established on each cold invocation. The `SupabaseDB` client uses a 10-second timeout but does not maintain a persistent connection pool across invocations.

### 3. No database-level indexes for common query patterns
The `GET /api/v1/consents` list endpoint filters on `status`, `channel`, and `customer_id`. Without appropriate index coverage in Supabase, these queries degrade with table growth. (`schema.sql` defines indexes on `customer_id`, `status`, `channel`, `expires_at` — verify these exist in production Supabase.)

### 4. Dashboard over-fetches
Every Dashboard page load fires three concurrent API calls: `GET /api/v1/consents`, `GET /api/v1/analytics/consents`, and `GET /api/v1/incidents`. The analytics endpoint is the bottleneck since it scans the entire table.

### 5. Chaos mode adds latency on some paths
When `CHAOS_MODE=true`, the failure scenarios add some processing overhead before the error is raised, which inflates response times for failed requests.

---

## Impact

- **Degraded user experience** on Dashboard and Consents pages — page loads take 1–3 seconds minimum.
- **Compounding load** — the Dashboard polls frequently; each poll triggers the full-table-scan analytics endpoint.
- **Cron job timeout risk** — `process-notifications` at 6166 ms is approaching the Vercel function timeout of 60 seconds under load; with a large notification queue it could time out.

---

## Diagnosis Steps

### Step 1 — Confirm it is the analytics endpoint
```
# New Relic NRQL:
SELECT average(duration_ms), max(duration_ms), percentile(duration_ms, 95) 
FROM Log 
WHERE service = 'cms-unified' 
FACET http.path 
SINCE 1 hour ago
```
Expected: `GET /api/v1/analytics/consents` will show the highest p95.

### Step 2 — Check Supabase table size
```sql
SELECT COUNT(*) FROM consents;
SELECT COUNT(*) FROM cms_metric_events;
```
Analytics endpoint latency scales with consent count. > 10,000 rows will show noticeable degradation.

### Step 3 — Verify indexes exist
```sql
-- In Supabase SQL editor:
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'consents';
```
Expected indexes: `customer_id`, `status`, `channel`, `expires_at`.

### Step 4 — Check cleanup cron is running
If `cms_metric_events` has not been cleaned up (cron not running), it accumulates and can slow queries.
```sql
SELECT COUNT(*), MIN(created_at), MAX(created_at) FROM cms_metric_events;
```
Expected: rows from the last 2 hours only. If older rows exist, the cleanup cron has not run.

---

## Resolution

### Immediate — Reduce analytics endpoint load
Add a `LIMIT` clause to prevent full unbounded scans while a proper fix is implemented:
```python
# vercel_app/main.py — analytics endpoint:
all_consents = await db.select("consents", params={"limit": 10000})
```

### Short-term — Cache analytics response
Add a simple in-memory TTL cache (60 seconds) on the analytics endpoint. Vercel functions are stateless per invocation, so use an external cache (e.g., Upstash Redis via `supabase_url` environment config) or move aggregation to a scheduled cron that writes results to the `cms_state` key-value table.

```python
# Recommended: pre-compute analytics in detect-anomalies cron and store in cms_state:
await db.upsert("cms_state", {"key": "analytics_cache", "value": json.dumps(analytics_data), "updated_at": "now()"})
# GET /api/v1/analytics/consents reads from cache
```

### Short-term — Move aggregations to database
Replace the Python-side aggregation with a single SQL query:
```sql
SELECT status, COUNT(*) 
FROM consents 
GROUP BY status;
```
This is orders of magnitude faster than fetching all rows to Python.

### Medium-term — Add pagination to analytics
Support time-windowed analytics (`since=24h`, `since=7d`) rather than all-time aggregations on every call.

### For cleanup cron not running
Trigger manually:
```bash
curl -H "Authorization: Bearer <cron_secret>" \
  https://<deployment-url>/api/cron/cleanup
```
Then verify the cron schedule in `vercel.json` is set correctly.

---

## Prevention

- Add a **response time SLO alert** in New Relic: p95 > 2000 ms on `/api/v1/analytics/consents` for > 3 minutes triggers a warning.
- Add a **consent table row count alert**: alert when `COUNT(*) FROM consents` exceeds 50,000 rows to prompt index review.
- Run the analytics endpoint through a load test (e.g., k6) before each major deployment.
- Ensure the cleanup cron is verified in post-deployment smoke tests.

---

## Related Articles
- KB-003: SNS Publish Failures and Processing Queue Idle (cron process-notifications overlap)
