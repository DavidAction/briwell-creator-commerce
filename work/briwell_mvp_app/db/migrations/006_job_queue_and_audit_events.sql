-- Generic async job-queue and append-only audit-event infrastructure.
--
-- Rationale: internal single-team tool, so Postgres SKIP LOCKED is used as the
-- queue backend instead of standing up Redis/RabbitMQ -- an intentional scope
-- decision, not an oversight. This migration only creates the two tables; no
-- application code is wired to run automatically as a result of it landing.
--
-- jobs: generic work queue. Workers claim rows with
-- "SELECT ... FOR UPDATE SKIP LOCKED" scoped to status = 'pending'.
--
-- audit_events: append-only event log. By convention no UPDATE/DELETE helper
-- is written against this table -- rows are immutable once inserted.
--
-- Idempotent-safe: CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS
-- throughout so this migration can be re-run safely.

CREATE TABLE IF NOT EXISTS jobs (
  id BIGSERIAL PRIMARY KEY,
  job_type TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'done', 'failed')),
  attempts INT NOT NULL DEFAULT 0,
  max_attempts INT NOT NULL DEFAULT 5,
  last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS jobs_status_created_at_idx ON jobs (status, created_at);

CREATE TABLE IF NOT EXISTS audit_events (
  id BIGSERIAL PRIMARY KEY,
  event_type TEXT NOT NULL,
  aggregate_type TEXT NOT NULL,
  aggregate_id TEXT NOT NULL,
  actor_role TEXT,
  actor_email TEXT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_events_aggregate_type_aggregate_id_idx ON audit_events (aggregate_type, aggregate_id);
