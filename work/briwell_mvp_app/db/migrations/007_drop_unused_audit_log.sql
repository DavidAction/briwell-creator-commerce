-- audit_log (001_initial_schema.sql) was never wired to any application code; the
-- append-only audit trail that actually ships is audit_events (006_job_queue_and_audit_events.sql),
-- used by /ops/audit-log and the outreach status-transition handler. Dropping the orphaned
-- table instead of leaving two structurally different "audit" tables to reconcile.

DROP INDEX IF EXISTS idx_audit_log_entity;
DROP TABLE IF EXISTS audit_log;
