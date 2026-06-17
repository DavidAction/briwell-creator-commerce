# Briwell Production Risk Reduction Review v0

Created: 2026-06-17

Status: Key production risks reduced with local safeguards, scripts, and tests.

## 1. Risks Addressed

Original risks:

1. Portable PostgreSQL is development-only.
2. Local password file is not a production secret strategy.
3. Backup and restore were not implemented.
4. Header RBAC is not production auth.
5. DB persistence E2E coverage was too shallow.

## 2. Work Completed

Implemented:

1. `scripts/backup_db.py`
2. `scripts/restore_db.py`
3. `scripts/db_tools.py`
4. `.env.production.example`
5. `app/core/readiness.py`
6. Stronger `/ops/readiness` production blockers
7. Expanded DB persistence E2E test
8. Backup/restore unit tests
9. Readiness guard tests
10. Real backup and restore smoke against local PostgreSQL

## 3. Three-Pass Review

### Pass 1: Backup and Restore

Result: Pass

Checks:

1. `pg_dump` custom-format backup completed.
2. Backup file was created under `work/db_backups`.
3. Restore into separate DB `briwell_restore_smoke` completed.
4. Restore verification passed required tables, enums, and seed counts.
5. Database URL redaction avoids printing passwords in script JSON output.

### Pass 2: Production Guardrails

Result: Pass

Checks:

1. Production readiness blocks header RBAC.
2. Production readiness blocks localhost DB.
3. Production readiness blocks missing managed secret provider.
4. Production readiness blocks missing backup/restore evidence.
5. Production readiness blocks missing rate limits.
6. OIDC production configuration path is represented through env settings.

### Pass 3: DB Persistence Depth

Result: Pass

Checks:

1. Creator import persists to DB.
2. Creator analysis persists to DB.
3. Campaign creation persists to DB.
4. Campaign candidate ranking reads DB state.
5. Outreach draft persists to DB.
6. Claims check status update persists to DB.
7. Human review approval persists to DB.

## 4. Validation Result

Latest validation:

```text
Risk-focused tests: 10 passed
Full regression with DB tests enabled: 140 passed
compileall passed
CSV validation passed
Backup smoke passed
Restore smoke passed
```

## 5. Remaining Honest Risks

Still not solved locally:

1. Managed production PostgreSQL must be selected and provisioned.
2. Real secret manager must be selected and connected.
3. Real OAuth/OIDC provider must be selected and integrated.
4. Rate limiting must be implemented at gateway or middleware level.
5. Monitoring, alerting, audit retention, and backup schedules must be deployed.

Conclusion: The risks are now materially reduced for MVP/internal testing, but
production deployment still requires external infrastructure decisions.
