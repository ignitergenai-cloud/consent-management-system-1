-- ============================================================
-- CMS (Consent Management System) — Supabase Schema
-- Run this in the Supabase SQL Editor (Dashboard → SQL Editor)
-- ============================================================

-- Consents
CREATE TABLE IF NOT EXISTS consents (
    consent_id       TEXT PRIMARY KEY,
    customer_id      TEXT NOT NULL,
    consent_type     TEXT NOT NULL,
    channel          TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'PENDING',
    message_template_id TEXT NOT NULL DEFAULT 'default',
    customer_phone   TEXT,
    customer_email   TEXT,
    consent_text     TEXT NOT NULL DEFAULT '',
    response_token   TEXT UNIQUE,
    expires_at       TIMESTAMPTZ NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    granted_at       TIMESTAMPTZ,
    denied_at        TIMESTAMPTZ,
    ip_address       TEXT,
    user_agent       TEXT,
    metadata         JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS consents_customer_id_idx ON consents(customer_id);
CREATE INDEX IF NOT EXISTS consents_status_idx       ON consents(status);
CREATE INDEX IF NOT EXISTS consents_channel_idx      ON consents(channel);
CREATE INDEX IF NOT EXISTS consents_expires_at_idx   ON consents(expires_at);

-- Consent history (audit trail)
CREATE TABLE IF NOT EXISTS consent_history (
    id          BIGSERIAL PRIMARY KEY,
    consent_id  TEXT NOT NULL REFERENCES consents(consent_id) ON DELETE CASCADE,
    action      TEXT NOT NULL,
    details     JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS consent_history_consent_idx ON consent_history(consent_id);

-- Incidents
CREATE TABLE IF NOT EXISTS cms_incidents (
    incident_id   TEXT PRIMARY KEY,
    type          TEXT NOT NULL,
    severity      TEXT NOT NULL DEFAULT 'MEDIUM',
    status        TEXT NOT NULL DEFAULT 'open',
    description   TEXT NOT NULL DEFAULT '',
    details       JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at   TIMESTAMPTZ,
    acknowledged_at TIMESTAMPTZ
);

-- Metric events (for anomaly detection, kept 1 hour)
CREATE TABLE IF NOT EXISTS cms_metric_events (
    id          BIGSERIAL PRIMARY KEY,
    event_type  TEXT NOT NULL,
    details     JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS cms_metric_events_type_time_idx ON cms_metric_events(event_type, created_at);

-- System state (pause/resume and other config)
CREATE TABLE IF NOT EXISTS cms_state (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL DEFAULT '{}',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Notification queue (processed by cron)
CREATE TABLE IF NOT EXISTS cms_notification_queue (
    id              BIGSERIAL PRIMARY KEY,
    consent_id      TEXT NOT NULL,
    channel         TEXT NOT NULL,
    recipient       TEXT NOT NULL,
    subject         TEXT,
    body            TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    attempts        INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS cms_notif_queue_status_idx ON cms_notification_queue(status, created_at);

-- Enable Row Level Security (optional but recommended)
-- ALTER TABLE consents ENABLE ROW LEVEL SECURITY;
-- Use service_role key on backend — no RLS policies needed for server-side access
