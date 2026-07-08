# Briwell Handoff

This document is for external development teams and AI coding tools continuing the Briwell MVP.

## Start Here (last updated 2026-07-08)

Read this block first, then `PROJECT_BRIEFING_KO.md` (Korean master briefing; latest state lives in the numbered `0.0.x` sections, most recent = highest number).

**Repo is fully synced.** Local clone and `origin/main` match; every change below is committed and pushed. On a new machine: `git clone` → `powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1` → done. See `docs/USE_ON_OTHER_COMPUTER.md`. Commits auto-push via the post-commit hook.

**Latest verified state:** backend `360 passed, 26 skipped`; dashboard `node tests\smoke.mjs` passes.

**What shipped most recently (newest first):**
1. Per-screen KPI metric strips on candidates/tracking/settlement (`renderScreenKpis()` + per-screen builders). All numbers are real-data anchored: candidates derive from `buildCommandMetrics()`, tracking/settlement aggregate session write logs (`state.sessionSnapshots`/`sessionContracts`/`sessionDiscountCodes`) that only count completed writes (cancelled and API-rejected writes are excluded). Payout table and settlement KPIs share one source (`PAYOUT_ROWS`). Dashboard Phase 3 is now complete.
2. Shopify go-live preflight: `scripts/shopify_golive_preflight.py` — executable checklist for runbook step 2 (domain/token/webhook secret/API version/FX incl. MXN·PEN coverage/DB/live gates), zero network calls, `--json` mode, cp949-safe output. Referenced from `docs/SHOPIFY_GOLIVE.md` step 2. 6 pure-logic tests (354→360).
3. `48b863f` Campaign execution funnel wired to live state (`buildCampaignFunnel()`), replacing hardcoded 24/14/9/6/2.
4. `5cf7a7d`/`d5b387b` Dashboard Phase 3 pass 1 + real Shopify integration (HMAC webhook receivers, gated Admin API discount issuance) + `scripts/register_shopify_webhooks.py` + `docs/SHOPIFY_GOLIVE.md`.

**Next candidates (pick one):**
- **B. Shopify go-live (ops, not code — blocked on David creating a Shopify account/store)** — CODE + TOOLING READY, dry-run paths verified 2026-07-08. When the account exists, follow `docs/SHOPIFY_GOLIVE.md`: create the custom app, set `SHOPIFY_*` secrets in `.env`, run `python -m scripts.shopify_golive_preflight` until nothing is MISSING, register webhooks, verify with a test order.
- **C. Trend-signal tab for Creator Search** — DESIGNED + MOCKUP APPROVED-FOR-REVIEW, not built. A "트렌드" sub-tab under Creator Search surfacing rising creators/formats. Tier-1 sources = `creator_provided` intake + public Google-News RSS (both legal, buildable today); tier-2 = official TikTok/IG APIs (skeleton exists) and licensed vendors (Data365/BrightData), which light up the same UI later. Building tier-1 doubles as real-data inflow (roadmap priority 2). See briefing 0.0.8. **This is the main remaining code work.**

**Compliance decision on record (do NOT re-litigate):** the user asked twice to port the local `trend-viewer` tool's TikTok collection, which relies on `tikwm` — a third-party proxy that bypasses TikTok's X-Bogus/msToken signing and TLS-fingerprint anti-bot controls. This was declined: it violates the non-negotiable constraints below (unauthorized scraping / anti-bot bypass), which are enforced in `app/core/policy.py`, and it is a real business risk (platform bans, third-party dependency). The trend feature is being delivered via legal source lanes instead. A prior session (briefing §0.3) already made the same call.

**Working conventions:** model routing for this project is Fable 5 for planning/review, Sonnet 5 for implementation, Haiku 4.5 for mechanical work (briefing §0.3). The user works across multiple computers and relies on git + auto-push to sync between them, so commit before switching machines.

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
4. Latest quality upgrade audit: `outputs/briwell_quality_upgrade_audit_v0.md`.

## Non-Negotiable Product Constraints

1. Do not implement unauthorized TikTok scraping.
2. Do not implement CAPTCHA bypass.
3. Do not automate external DM sending.
4. Do not store or process High Risk or Not Allowed source records as valid workflow inputs.
5. Accept only approved collection source types: `manual`, `official_api`, `approved_provider`, and `creator_provided`.
6. Do not treat country compliance rules as legal advice.
7. Keep human approval before any manual outreach status transition.

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
