# Briwell Handoff

This document is for external development teams and AI coding tools continuing the Briwell MVP.

## Start Here (last updated 2026-07-12)

Read this block first, then `PROJECT_BRIEFING_KO.md` (Korean master briefing; latest state lives in the numbered `0.0.x` sections, most recent = highest number).

**Repo is fully synced.** Local clone and `origin/main` match; every change below is committed and pushed. On a new machine: `git clone` → `powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1` → done. See `docs/USE_ON_OTHER_COMPUTER.md`. Commits auto-push via the post-commit hook.

**Latest verified state (re-run 2026-07-12):** backend `379 passed, 26 skipped`; dashboard `node tests\smoke.mjs` passes.

**What shipped most recently (newest first):**
-7. Vendor portal plan v0 (briefing 0.0.19, NO CODE YET): brand clients upload
   catalogs/ingredients, AI structures them (extract -> INCI normalize -> validate ->
   regulatory signal -> completeness score), operator approves into product_catalog.
   Full plan + global benchmarking (Akeneo SDM, Salsify, UMMA, CosIng, COFEPRIS/
   DIGEMID/Decision 833) in outputs/briwell_vendor_portal_plan_v0.md. Awaiting
   David's decisions on the 7 points in its §9 before Phase 1 implementation.
-6. Dashboard portal-link panel + CORS DELETE fix (briefing 0.0.18): the settlement
   screen now issues/rotates and revokes portal links (write-confirm gated), assembles
   the `?t=` personal link with a copy button, and refuses to fabricate tokens offline
   (api_unreachable — a locally invented token is a dead link). Real-browser
   verification caught that the CORS gate allowed only GET/POST/OPTIONS, so the
   0.0.17 revoke kill switch (DELETE /portal/tokens) was unreachable from any
   browser — fixed in app/main.py + preflight regression test, 378->379 passing.
   Remaining portal deploy items (both David decisions): portal page origin in
   CORS_ALLOWED_ORIGINS (noted in DEPLOY_RENDER.md) and the production URL shape.
-5. Creator self-serve portal (briefing 0.0.17): tokenized personal links (no login) —
   migration 009 + /portal/tokens (RBAC issue/rotate/revoke) + public read-only
   GET /portal/me?token= with a strict field whitelist (no operator emails, memos or
   cross-creator data), reusing the existing commerce ledger/balance schema. Mobile web
   UI at work/briwell_portal_app (The Well identity, demo mode, copy-code, error
   states). Tests 368->378 passing. Deploy notes: CORS origin for the portal page,
   dashboard issue-token button, production URL shape.
-4. Brand decisions + dashboard PWA + mobile roadmap (briefing 0.0.16): official notation
   "Briwell", tagline "Bridge + Well", faith kept internal-only (scripture removed from the
   public KO page), logo/cards deferred (13 mark directions + 7 wordmark type candidates in
   work/briwell_brand/). Native apps deliberately deferred on a trigger-based roadmap; the
   operator dashboard is now an installable PWA (manifest + sw.js + icons, smoke passing,
   375px verified). Landing pages audited responsive-clean at 360-1024px. Creator portal
   (tokenized personal links) designed, implementation next session.
-3. Brand-identity redesign "The Well" (briefing 0.0.15): David revealed the brand core —
   Briwell = Bridge + Well (Isaiah 12:3 wells of salvation, Isaac's wells, living water;
   one deep well filling other wells, Korea ↔ LATAM). Both landing pages rebuilt in the
   identity-driven design system (deep-teal/aqua/gold/stone palette, circular well-mouth
   photo frames, ripple motifs, deep-ink sections). Scripture only in the KO brand-story
   section; ES uses universal water language; all 0.0.14 copy rules kept. Identity also
   saved to assistant memory (briwell-brand-identity).
-2. ES creator landing page approved — concept C (briefing 0.0.14): strategy session →
   3 full-page concepts with official product photos (Parnell / Essenherb·BRTC / Dermal) →
   David picked C, now `work/briwell_landing_page/index.html`. Form-only CTA (placeholder
   links until the apply form exists — spec ready in `docs/CREATOR_APPLY_FORM_ES.md`,
   mapped to the creator_provided CSV columns), no operational promises in copy, dead
   live-pulse fetch removed from landing.js. The ko/ company page (brand partners /
   grant reviewers) was renewed 2026-07-10 in the C design system, old version
   preserved. Open: form creation, domain/hosting/email, brand photo-usage
   confirmation — all David decisions.
-1. Market news-signal panel on the discovery screen (briefing 0.0.13): public Google News RSS fetcher (`app/trends/news_rss.py`, `GET /trends/news`) behind the house dual live gate (`NEWS_RSS_*`, dry-run samples by default, 15-min cache), Spanish per-market queries, XSS-guarded panel rendering. Market signals only — never creator workflow inputs. Slimmed-C step (b) is done; production render.yaml ships with the news gates open (public feed).
0. creator_provided submission channel (briefing 0.0.12): two creator-facing CSV templates (consent columns required), Spanish request copy (`docs/CREATOR_DATA_REQUEST_ES.md`) with one-click copy in the dashboard, and an intake panel that validates consent fail-closed, normalizes via `/providers/creator-provided/import` (pure compute, allowlisted), and feeds the existing quality-gate/screening/import machinery. Slimmed-C step (a) is done.
1. Live-transition prep (briefing 0.0.11): `render.yaml` moved to the repo root (Render only detects root blueprints; `rootDir` points at the app), SHOPIFY_* env vars added (the old blueprint predated the Shopify integration — deploying it would have 503'd every webhook), managed Postgres block with `DATABASE_URL` via `fromDatabase`, and a full deploy runbook `docs/DEPLOY_RENDER.md` (Supabase OIDC → backup evidence → blueprint → verify → dashboard hookup). Dashboard settings drawer gained a Bearer-token (OIDC) field — production rejects header RBAC, so this is how the dashboard talks to a deployed API until a full login flow exists.
2. Derived-figure honesty markers (briefing 0.0.11): `추정` tags + footnotes on the GMV forecast card, ratio-derived funnel stages (auto-clears when real brand-safe counts exist), representative-shape sparklines, and the GMV trend hero.
3. Per-screen KPI metric strips on candidates/tracking/settlement, all real-data anchored via session write logs (cancelled/API-rejected writes excluded). Dashboard Phase 3 complete.
4. Shopify go-live preflight `scripts/shopify_golive_preflight.py` (executable checklist for runbook step 2, zero network calls) + earlier Shopify integration/funnel work (briefing 0.0.7–0.0.10).

**Priority order (re-evaluated 2026-07-08, briefing 0.0.11 배경 — do not silently reorder):**
1. **Deploy (ops — needs David's Render + Supabase accounts)**: follow `docs/DEPLOY_RENDER.md`. Blueprint and runbook are ready; the readiness gate fails closed until config is complete.
2. **Real-data pilot without new code**: manually research 10–20 real LATAM creators via the playbook's Low/Medium-risk lanes (`outputs/briwell_pilot_operations_playbook_v0.md`) and register them through the existing intake screens; execute at least one manual outreach. This is roadmap priority 2 — it does not need the trend tab. The outreach landing page is ready (see -2 above); to include its link in outreach messages, the apply form + domain must exist first.
3. **C slimmed down (code, in order)**: (a) ~~creator_provided submission channel~~ — DONE 2026-07-08 (briefing 0.0.12); (b) ~~news-RSS panel on the discovery screen~~ — DONE 2026-07-08 (briefing 0.0.13); (c) full trend tab only after real data flows. Full-tab design notes in briefing 0.0.8; the 0.0.8 mockup was never committed. **All account-independent code work is now done — the remaining priorities (deploy, real-data pilot, Shopify) need David's accounts/ops.**
4. **Shopify go-live (ops — blocked on Shopify account)**: `docs/SHOPIFY_GOLIVE.md` + `python -m scripts.shopify_golive_preflight`.

**Compliance decision on record (do NOT re-litigate):** the user asked twice to port the local `trend-viewer` tool's TikTok collection, which relies on `tikwm` — a third-party proxy that bypasses TikTok's X-Bogus/msToken signing and TLS-fingerprint anti-bot controls. This was declined: it violates the non-negotiable constraints below (unauthorized scraping / anti-bot bypass), which are enforced in `app/core/policy.py`, and it is a real business risk (platform bans, third-party dependency). The trend feature is being delivered via legal source lanes instead. A prior session (briefing §0.3) already made the same call.

**Working conventions:** model routing for this project is Fable 5 for planning/review, Sonnet 5 for implementation, Haiku 4.5 for mechanical work (briefing §0.3). The user works across multiple computers and relies on git + auto-push to sync between them, so commit before switching machines.

**Mandatory post-work self-verification (user directive, 2026-07-08):** after completing any implementation work and BEFORE reporting it done or committing, run a critical self-verification pass unprompted — re-read the full diff, check changes against runtime gates/configs/docs for contradictions, verify assumptions against actual code, run the relevant tests, fix findings, and report them (or an explicit clean result). Precedent: the 2026-07-08 re-check of already-committed work found a deploy blueprint missing `OUTBOX_WORKER_ENABLED` and a runbook step contradicting the production CORS gate.

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

Current production blockers (deploy-ready as of 2026-07-08 — the root `render.yaml`
blueprint plus `docs/DEPLOY_RENDER.md` resolve 1–2 and most of 3–5 once executed;
blocked only on Render/Supabase accounts):

1. Managed DB is not yet connected (blueprint provisions `briwell-postgres`).
2. Secret manager is not yet configured (blueprint uses Render env vars, `sync: false`).
3. OIDC is scaffolded and the dashboard can send a Bearer token (settings drawer), but there is no full login flow yet.
4. Backup automation and restore-test evidence are not productionized (runbook step 2 gates on it).
5. Rate limit is enabled in the blueprint; monitoring/alerting is still open.

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
