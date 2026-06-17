# Briwell Creator Commerce Intelligence

Briwell Creator Commerce Intelligence is an MVP for operating LATAM K-beauty creator commerce campaigns across Mexico, Peru, and Ecuador.

The system currently includes:

1. FastAPI backend for creator discovery, risk policy, AI analysis scaffolding, campaign workflows, outreach review gates, performance tracking, settlement records, and production readiness checks.
2. Static operator dashboard for global MCN-style creator operations.
3. PostgreSQL migrations, seed data, import templates, and local validation scripts.
4. Handoff documents for external developers and AI coding tools.

## Current Analysis Gate

Creator fit should start with the latest 20 approved recent post snapshots.

Flow:

1. Import or provide recent post snapshots through compliant sources only.
2. Run `POST /analysis-jobs/run-recent-posts-screen`.
3. Only creators that pass or need human review continue to profile, comment, multimodal, and score analysis.
4. Do not reject a creator only because of low follower count or narrow initial keyword discovery.

## Current Product Rule

The MVP only supports Low, Low/Medium, and Medium risk sources.

Blocked by design:

1. Unauthorized TikTok or Instagram scraping
2. CAPTCHA bypass
3. Browser automation against public social pages
4. Automated DM sending
5. High Risk or Not Allowed source records

Outreach is draft, review, and manual-send tracking only.

## Repository Layout

```text
work/briwell_mvp_app/        FastAPI backend
work/briwell_dashboard_app/  Static operator dashboard
outputs/                    Product docs and user-facing deliverables
docs/                       GitHub handoff and development notes
.githooks/                  Local git hooks, including auto-push after commit
```

## Use On Another Computer

Clone from GitHub:

```powershell
git clone https://github.com/DavidAction/briwell-creator-commerce.git
cd briwell-creator-commerce
```

Run one-time Windows setup:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

Start backend and dashboard:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_local_stack_windows.ps1
```

Open:

```text
Dashboard: http://127.0.0.1:8070
API docs:  http://127.0.0.1:8030/docs
```

Full guide:

```text
docs/USE_ON_OTHER_COMPUTER.md
```

## Backend Quick Start

```powershell
cd work\briwell_mvp_app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8030 --reload
```

API docs:

```text
http://127.0.0.1:8030/docs
```

## Dashboard Quick Start

```powershell
cd work\briwell_dashboard_app
python -m http.server 8070
```

Dashboard:

```text
http://127.0.0.1:8070
```

The dashboard connects to `http://127.0.0.1:8030` when the API is available and falls back to mock mode when offline.

## Validation

Backend:

```powershell
cd work\briwell_mvp_app
.venv\Scripts\activate
pytest -q
```

Dashboard:

```powershell
cd work\briwell_dashboard_app
node --check app.js
node tests\smoke.mjs
```

## First Files To Read

1. `HANDOFF.md`
2. `docs/AUTO_PUSH.md`
3. `work/briwell_mvp_app/README.md`
4. `work/briwell_dashboard_app/README.md`
5. `outputs/briwell_mvp_v0_1_prd.md`
6. `outputs/briwell_cloud_stack_execution_plan_v0.md`

## GitHub Handoff Status

This repository is prepared for GitHub handoff. Local git auto-push is configured through `.githooks/post-commit` once a remote named `origin` is set.

If no remote exists yet:

```powershell
git remote add origin <github-repo-url>
git push -u origin main
```

After that, each new local commit will attempt to push automatically.
