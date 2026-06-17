# Briwell PostgreSQL Live Setup Review v0

Created: 2026-06-17

Status: Live local PostgreSQL connected, migrated, seeded, and verified.

## 1. What Was Completed

1. Confirmed Docker, `psql`, and system PostgreSQL were not available.
2. Attempted Chocolatey install, but it failed because the shell was not elevated and Chocolatey could not write to `C:\ProgramData`.
3. Switched to a portable PostgreSQL setup inside the workspace.
4. Downloaded official EDB PostgreSQL 17.10 Windows x64 binaries.
5. Initialized local data directory at `work/postgres_data`.
6. Started PostgreSQL on `127.0.0.1:55432`.
7. Created the `briwell` database.
8. Applied migrations and seeds with `scripts/bootstrap_db.py`.
9. Added migration `003_keyword_seed_uniqueness.sql` to prevent duplicate keyword imports.
10. Verified actual DB-mode API persistence for campaign and creator import.

## 2. Connection

Runtime:

```text
PostgreSQL 17.10
Host: 127.0.0.1
Port: 55432
Database: briwell
User: briwell
```

Local password is stored in:

```text
work/postgres_pw.txt
```

## 3. Three-Pass Review

### Pass 1: Environment and Runtime

Result: Pass

Checks:

1. Portable PostgreSQL binary runs.
2. `initdb` succeeded outside the sandbox.
3. PostgreSQL server started on port `55432`.
4. `psql` connection to `postgres` and `briwell` succeeded.

### Pass 2: Schema and Seed Integrity

Result: Pass

Checks:

1. `001_initial_schema.sql` applied.
2. `002_execution_tracking_schema.sql` applied.
3. `003_keyword_seed_uniqueness.sql` applied.
4. `001_seed_data.sql` applied.
5. Keyword CSV imported 75 rows.
6. Re-running bootstrap keeps keyword row count at 75.
7. Database verification passed.

### Pass 3: App Integration

Result: Pass

Checks:

1. DB integration tests passed.
2. Full regression passed with DB tests enabled.
3. FastAPI DB mode smoke passed.
4. `/keywords` read persisted seed rows.
5. `/campaigns` persisted a campaign.
6. `/creators/import` persisted a creator.

## 4. Validation Result

Latest validation:

```text
DB integration: 4 passed
DB bootstrap contract + integration: 7 passed
Full regression with DB tests enabled: 134 passed
compileall passed
CSV validation passed
DB-mode HTTP smoke passed
```

## 5. Helper Scripts

Start PostgreSQL:

```powershell
powershell -ExecutionPolicy Bypass -File outputs\start_briwell_postgres_portable.ps1
```

Stop PostgreSQL:

```powershell
powershell -ExecutionPolicy Bypass -File outputs\stop_briwell_postgres_portable.ps1
```

Start API server in DB mode:

```powershell
powershell -ExecutionPolicy Bypass -File outputs\start_briwell_api_server_db.ps1
```

Swagger URL after starting the API server:

```text
http://127.0.0.1:8030/docs
```

## 6. Remaining Production Gap

This is a local portable PostgreSQL runtime, not a managed production database.
Production still needs managed backups, restore testing, monitoring, credentials
rotation, and network access controls.
