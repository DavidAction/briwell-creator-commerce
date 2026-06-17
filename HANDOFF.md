# Briwell Handoff

This document is for external development teams and AI coding tools continuing the Briwell MVP.

## Business Context

Briwell sells Korean cosmetics into Latin America. The first B2C online growth system focuses on creator commerce operations for Mexico, Peru, and Ecuador.

The MVP goal is to discover, evaluate, shortlist, contact, track, and settle beauty creators while keeping data acquisition and outreach compliant.

## What Exists Now

Backend:

1. FastAPI app scaffold with routers for health, products, keywords, creators, videos, comments, AI jobs, AI invocation logs, campaigns, outreach, compliance, performance, settlements, and operations readiness.
2. PostgreSQL schema migrations and seed data.
3. Repository-backed persistence for core workflow entities when `USE_DATABASE=true`.
4. Dry-run Gemini-first AI adapter structure.
5. Deterministic scoring and ranking layer.
6. Human review gate for outreach.
7. Manual-send tracking without external message automation.
8. OIDC/Supabase-compatible JWT validation scaffold for production.
9. Operations orchestration endpoints for import QA, creator enrichment, recent-post apply, campaign match, outreach plan, CRM board, and performance rollup.
10. Fast-fail PostgreSQL connection timeout for API and bootstrap scripts.

Frontend:

1. Static dashboard at `work/briwell_dashboard_app`.
2. Global MCN-style UI with Creator Discovery, Talent Intelligence, Campaign Studio, Brand Safety Desk, Performance Analytics, and Contracts & Payouts.
3. Creator profile and channel visual placeholders.
4. API client with mock fallback.
5. Smoke test coverage for core visual and workflow surfaces.
6. Talent Intake workflow for creator CSV upload, recent 20 post intake, import quality gate, and coverage audit visibility.

Documentation:

1. PRD and implementation reviews in `outputs/`.
2. Cloud stack plan and production risk notes.
3. API spec and AI prompt/schema documents.

## Non-Negotiable Product Constraints

1. Do not implement unauthorized TikTok scraping.
2. Do not implement CAPTCHA bypass.
3. Do not automate external DM sending.
4. Do not store or process High Risk or Not Allowed source records as valid workflow inputs.
5. Do not treat country compliance rules as legal advice.
6. Keep human approval before any manual outreach status transition.

## Recommended Next Development Order

1. Use `POST /analysis-jobs/run-recent-posts-screen` as the first creator-fit gate with the latest 20 approved recent post snapshots.
2. Use `/operations/*` as the dashboard orchestration layer for import QA through performance rollup.
3. Replace local header RBAC in the dashboard with Supabase Auth/OIDC bearer tokens.
4. Move development DB from portable PostgreSQL to managed PostgreSQL.
5. Connect the dashboard to production API environment config.
6. Implement approved-provider or manual import flows for real creator and recent-post data.
7. Add live Gemini calls behind cost, logging, and operator review controls.
8. Build real media asset ingestion for creator-provided or approved-provider content.
9. Add production monitoring, error alerts, backup restore drills, and rate limits.

## Creator Discovery Recall Policy

The discovery planner returns `coverage_audit` and `recall_safeguards`.

Use these fields before concluding that a market or product has weak creator supply:

1. Keep discovery, concern, format, and commerce keyword intent coverage balanced.
2. Run second-pass expansion when any intent type is missing.
3. Avoid hard follower-count cutoffs during initial discovery.
4. Screen the latest 20 approved posts before excluding borderline creators.
5. Keep TikTok, Instagram, approved provider exports, manual import, and creator-provided lists as separate source lanes.

## Local Commands

Backend:

```powershell
cd work\briwell_mvp_app
.venv\Scripts\activate
pytest -q
uvicorn app.main:app --host 127.0.0.1 --port 8030 --reload
```

Dashboard:

```powershell
cd work\briwell_dashboard_app
node --check app.js
node tests\smoke.mjs
python -m http.server 8070
```

## Production Notes

Current production blockers:

1. Managed DB is not yet connected.
2. Secret manager is not yet configured.
3. OAuth/OIDC is scaffolded but not wired to a live dashboard login flow.
4. Backup automation and restore-test evidence are not productionized.
5. Rate limit and monitoring are not productionized.

## Git Workflow

The repo includes a post-commit hook under `.githooks/post-commit`.

Once a GitHub remote named `origin` exists, each local commit attempts to push automatically.

To disable auto-push temporarily:

```powershell
$env:DISABLE_AUTO_PUSH="1"
```

To re-enable:

```powershell
Remove-Item Env:\DISABLE_AUTO_PUSH
```
