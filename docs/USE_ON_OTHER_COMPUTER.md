# Use Briwell On Another Computer

This guide explains how to run the Briwell MVP on another laptop or desktop.

## Recommended Computer Setup

Install these first:

1. Git
2. Python 3.11+ or 3.12+
3. Node.js LTS, optional but recommended for dashboard validation
4. A code editor such as VS Code, Cursor, Claude Code, or another IDE

PostgreSQL is optional for local validation. The backend runs with
`USE_DATABASE=false` by default, so the API can start without a database.

## Clone The Repository

PowerShell:

```powershell
git clone https://github.com/DavidAction/briwell-creator-commerce.git
cd briwell-creator-commerce
```

## One-Time Setup

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

This script:

1. Creates the backend Python virtual environment
2. Installs backend dependencies
3. Creates `work\briwell_mvp_app\.env` from `.env.example` if missing
4. Enables the local auto-push git hook for this clone
5. Runs dashboard JS validation if Node.js is installed

## Start The App

Option A, start both backend and dashboard in separate PowerShell windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_local_stack_windows.ps1
```

Then open:

```text
Dashboard: http://127.0.0.1:8070
API docs:  http://127.0.0.1:8030/docs
```

Option B, start each service manually:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_backend_windows.ps1
```

In another terminal:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_dashboard_windows.ps1
```

## Run Tests

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test_local_windows.ps1
```

Expected backend result:

```text
149 passed, 5 skipped
```

Dashboard smoke test should print:

```text
dashboard smoke passed
```

## Updating GitHub From Another Computer

After clone, auto-push is enabled by `scripts\setup_windows.ps1`.

If needed, enable it manually:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\enable_auto_push_windows.ps1
```

When you commit:

```powershell
git add .
git commit -m "Describe the work"
```

The post-commit hook attempts to push to GitHub automatically.

If GitHub credentials are not configured on the new computer, the first push may
ask you to log in through Git Credential Manager. Follow the browser login
prompt, then retry:

```powershell
git push
```

## Using Claude Code Or An Outsourced Team

Share this repository:

```text
https://github.com/DavidAction/briwell-creator-commerce
```

First files to read:

1. `README.md`
2. `HANDOFF.md`
3. `docs/USE_ON_OTHER_COMPUTER.md`
4. `work/briwell_mvp_app/README.md`
5. `work/briwell_dashboard_app/README.md`

Important product rule:

1. No unauthorized TikTok or Instagram scraping
2. No CAPTCHA bypass
3. No automated DM sending
4. Use recent 20 approved post snapshots as the first creator-fit screen
5. Keep human review gates before outreach

## Optional Local PostgreSQL

Local DB is not required for basic development. When ready, use the backend
README for Docker or managed PostgreSQL setup:

```text
work/briwell_mvp_app/README.md
```

