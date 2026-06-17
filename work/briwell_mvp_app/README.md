# Briwell Influencer Intelligence MVP App

Backend scaffold for Briwell MVP v0.1.

Core rule: MVP v0.1 only supports Low / Low to Medium / Medium Risk sources.
High Risk and Not Allowed sources must not be used to create jobs, videos,
comments, or outreach records.

## Structure

```text
app/
  main.py
  core/
    auth.py
    config.py
    db.py
    policy.py
  ai/
    adapters.py
    contracts.py
    dm.py
    gemini.py
    schema_validation.py
  compliance/
    claims.py
    country_rules.py
    outreach_review.py
  discovery/
    planner.py
  schemas/
    analysis.py
  ranking/
    campaign_candidates.py
  scoring/
    creator_score.py
  repositories/
    ai_invocation_logs.py
    analysis_jobs.py
    campaigns.py
    comments.py
    creator_analyses.py
    creators.py
    keywords.py
    outreach.py
    products.py
    videos.py
  routers/
    analysis_jobs.py
    ai.py
    ai_invocation_logs.py
    campaigns.py
    comments.py
    compliance.py
    health.py
    creators.py
    discovery.py
    keywords.py
    ops.py
    outreach.py
    performance.py
    products.py
    settlements.py
    videos.py
  workers/
    analysis_runner.py
    multimodal_analysis.py
    scoring_handoff.py
  workflows/
    outreach_status.py
db/
  migrations/
    001_initial_schema.sql
  seeds/
    001_seed_data.sql
    keyword_seed_v0.csv
scripts/
  run_analysis_worker.py
  validate_csv_imports.py
tests/
  test_policy.py
.env.production.example
render.yaml
```

## Local Setup

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Database

Apply migration and seed files in order:

```text
db/migrations/001_initial_schema.sql
db/seeds/001_seed_data.sql
db/seeds/keyword_seed_v0.csv
```

Keyword CSV import maps to `keyword_seed`.

By default, `USE_DATABASE=false`, so API routes validate requests without
persisting data. Set `USE_DATABASE=true` after PostgreSQL is available to enable
repository-backed persistence.

Apply schema and SQL seeds:

```bash
python scripts/apply_sql.py --with-seeds
```

Import keyword CSV seeds:

```bash
python scripts/import_keyword_seed.py
```

One-command bootstrap for a fresh PostgreSQL database:

```bash
python scripts/bootstrap_db.py --with-seeds --with-keywords --verify
```

The bootstrap command applies migrations, applies SQL seeds, imports keyword CSV
seeds, records applied SQL files in `schema_migration`, and verifies required
tables, enums, and minimum seed counts. PostgreSQL connections use a 5-second
timeout so a stopped local database fails fast instead of hanging the setup.

Safer local PostgreSQL option, if Docker is available:

```bash
set BRIWELL_POSTGRES_PASSWORD=<strong-password>
docker compose -f docker-compose.postgres.yml up -d
copy .env.db.example .env
python scripts/check_db_connection.py
python scripts/bootstrap_db.py --with-seeds --with-keywords --verify
set RUN_DB_TESTS=1
pytest -v
```

Do not use weak default database passwords in shared or persistent environments.

Portable local PostgreSQL was also verified for this workspace:

```powershell
powershell -ExecutionPolicy Bypass -File ..\..\outputs\start_briwell_postgres_portable.ps1
$env:DATABASE_URL="postgresql://briwell:<password-from-work-postgres_pw.txt>@127.0.0.1:55432/briwell"
$env:USE_DATABASE="true"
python scripts/bootstrap_db.py --with-seeds --with-keywords --verify
$env:RUN_DB_TESTS="1"
pytest tests\test_db_integration.py -q
```

The local portable database uses PostgreSQL 17.10 on `127.0.0.1:55432`.
The local password file is stored outside the packaged app at
`work/postgres_pw.txt`.

Create and verify a local backup:

```powershell
$env:PG_BIN_DIR="..\postgresql-17.10-portable\pgsql\bin"
python scripts/backup_db.py --output-dir ..\db_backups
python scripts/restore_db.py --backup-file <backup.dump> --target-db briwell_restore_smoke --drop-existing
```

`restore_db.py` restores into a separate target database and runs required table,
enum, and seed-count verification unless `--no-verify` is provided.

Production configuration template:

```text
.env.production.example
```

Production readiness requires managed PostgreSQL, OIDC auth, managed secrets,
backup/restore evidence, rate limiting, and provider keys.

Render deployment scaffold:

```text
render.yaml
```

The Render blueprint deploys the FastAPI API as a Python web service, runs
production readiness checks, applies migrations/seeds, and starts Uvicorn.
Set the `sync: false` environment variables in Render from Supabase, Gemini,
and the backup/restore verification record before first production deploy.

Dashboard CORS origins must also be configured:

```text
CORS_ALLOWED_ORIGINS=https://<dashboard-domain>
```

Local dashboard development origins are enabled by default:

```text
http://127.0.0.1:8070,http://localhost:8070,http://127.0.0.1:5173,http://localhost:5173
```

## Validation

Run source-risk and CSV validation tests:

```bash
python -m unittest discover -s tests
python scripts/validate_csv_imports.py
```

## First Endpoints

1. `GET /health`
2. `GET /products`
3. `GET /keywords`
4. `POST /creators/import`
5. `GET /creators`
6. `GET /analysis-jobs`
7. `POST /analysis-jobs`
8. `POST /outreach/{creator_id}/generate-dm`
9. `GET /videos`
10. `POST /videos/import`
11. `GET /comments`
12. `POST /comments/import`
13. `POST /ai/validate-output`
14. `POST /ai/dry-run`
15. `POST /analysis-jobs/run-dry-run`
16. `GET /ai-invocation-logs`
17. `GET /creators/{creator_id}/analysis`
18. `POST /creators/{creator_id}/score`
19. `GET /campaigns`
20. `POST /campaigns`
21. `GET /campaigns/{campaign_id}/candidates`
22. `POST /analysis-jobs/run-creator-score-handoff`
23. `POST /campaigns/{campaign_id}/outreach-drafts`
24. `POST /outreach/claims-check`
25. `POST /outreach/review-decision`
26. `GET /discovery/source-policy`
27. `POST /discovery/plans`
28. `GET /ai/provider-status`
29. `POST /analysis-jobs/run-multimodal`
30. `POST /analysis-jobs/run-recent-posts-screen`
31. `POST /outreach/status-transition`
32. `POST /performance/snapshots`
33. `GET /performance/campaigns/{campaign_id}/summary`
34. `POST /settlements/contracts`
35. `POST /settlements/payouts`
36. `GET /compliance/rules`
37. `POST /compliance/country-claims-check`
38. `GET /ops/readiness`
39. `GET /ops/security-policy`
40. `POST /operations/import-quality-logs`
41. `POST /operations/creator-enrichment`
42. `POST /operations/recent-posts/apply`
43. `POST /operations/campaign-match`
44. `POST /operations/outreach-plan`
45. `POST /operations/outreach-crm/board`
46. `POST /operations/performance-rollup`
47. `GET /providers/tiktok/status`
48. `GET /providers/tiktok/keyword-playbook`
49. `POST /providers/tiktok/discovery-runs`
50. `POST /operations/acquisition-orchestration`

The initial routers are scaffolded with policy validation, placeholder responses
when DB mode is disabled, and repository-backed persistence when
`USE_DATABASE=true`. Database-backed implementation should follow
`outputs/briwell_api_spec_v0.md`.

## Operations Orchestration Layer

`/operations/*` connects the MVP workflow across import QA, profile enrichment,
recent-post screening, campaign matching, outreach planning, CRM board state,
and performance rollup. In local mode these endpoints validate and calculate
the workflow without persistence. In DB mode they persist import quality logs,
creator enrichment results, recent-post screen results, and CRM events through
the `004_operations_orchestration_schema.sql` migration.

`POST /operations/acquisition-orchestration` is the offline-ready operator
runner for steps 2-12 while paid TikTok provider benchmarking is paused. It
accepts creator candidates and recent posts, evaluates import quality, imports
approved data when DB persistence is enabled, runs dry-run recent-20 screening,
plans profile/comment/multimodal/final-review queues, ranks campaign matches,
builds DM outreach plans, checks claims/country compliance, rolls up performance
snapshots, and returns settlement, production-readiness, and handoff sections.
See `docs/offline_operations_2_12.md`.

Import QA defaults to the MX/PE/EC launch cluster, but requests can pass
`expected_countries` to validate a single-market or partial-market upload
without false coverage warnings. When `USE_DATABASE=true` and persistence is
requested, entity IDs such as `creator_id`, `campaign_id`, and `outreach_id`
must be real UUIDs from the database; local dashboard IDs should keep
`persist_result=false`.

## Auth Headers

MVP scaffolding uses simple role headers until a real auth provider is added.

```text
X-User-Role: admin
X-User-Email: operator@example.com
```

Supported roles:

1. admin
2. operator
3. campaign_manager
4. viewer

Write endpoints reject missing or unauthorized roles.

For production, set `AUTH_PROVIDER=oidc`. In OIDC mode, the API ignores
`X-User-Role` and requires `Authorization: Bearer <JWT>`. The JWT is verified
against the configured JWKS URL, issuer, audience, and allowed algorithms.
For Supabase Auth, use asymmetric JWT signing keys and store the Briwell app
role in `app_metadata.briwell_role`.

Recommended Supabase OIDC values:

```text
OIDC_ISSUER_URL=https://<project-ref>.supabase.co/auth/v1
OIDC_AUDIENCE=authenticated
OIDC_JWKS_URL=https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json
OIDC_ROLE_CLAIM=app_metadata.briwell_role
OIDC_ALLOWED_ALGORITHMS=ES256,RS256
```

Verify production gates before deployment:

```bash
python scripts/verify_production_readiness.py --env-file .env.production
```

## Discovery Planning

`POST /discovery/plans` creates country, product, and platform-specific creator
discovery tasks from the MX/PE/EC keyword seed.

Rules currently enforced:

1. Requires `admin`, `operator`, or `campaign_manager`.
2. Discovery plans use keyword seeds for Mexico, Peru, and Ecuador.
3. Allowed collection paths are allowlisted as `manual`, `official_api`, `approved_provider`, and `creator_provided`.
4. Unauthorized scraping paths such as `browser_automation`, `captcha_bypass`, and `public_page_scrape` are listed as blocked.
5. Unknown or unapproved source-type labels are rejected even when they are not explicitly in the blocked list.
6. Plans produce tasks only; they do not crawl TikTok, bypass login, or send messages.
7. Candidate profiles collected from the plan should enter the system through `POST /creators/import`.
8. Discovery plans include `coverage_audit` and `recall_safeguards` so operators can identify false-negative risk before concluding that a country/product lacks good creators.
9. Keyword selection is balanced across discovery, concern, format, and commerce intents when the keyword budget allows.
10. Do not apply hard follower-count cutoffs in the discovery stage; first screen content fit and audience intent.

`GET /discovery/source-policy` returns the allowed and blocked source-type policy
for UI and operator education.

## TikTok Provider Acquisition

TikTok acquisition is provider-led. The MVP does not maintain a direct browser
automation crawler. It normalizes data from paid TikTok data providers into the
same creator, video, recent-20, AI screening, campaign, outreach, performance,
and settlement workflows.

Recommended provider strategy:

1. Apify-first MVP connector for fast live validation.
2. Data365 as the production benchmark candidate.
3. Bright Data as the scale and fallback provider.
4. TikAPI as an experimental fallback only.

Provider endpoints:

```text
GET /providers/tiktok/status
GET /providers/tiktok/keyword-playbook
POST /providers/tiktok/discovery-runs
```

`GET /providers/tiktok/keyword-playbook` returns the LATAM K-Beauty keyword set
optimized for Gen Z and young millennial Spanish-speaking beauty buyers. The
playbook balances:

1. trend intent such as viral TikTok and GRWM searches
2. discovery intent such as core K-beauty product queries
3. concern intent such as oily, mixed, or sensitive skin routines
4. format intent such as honest reviews, try-on, tutorial, and UGC
5. commerce intent such as where-to-buy, recommended, dupe, and affordable searches

Dry-run provider discovery:

```bash
curl -X POST http://127.0.0.1:8030/providers/tiktok/discovery-runs ^
  -H "Content-Type: application/json" ^
  -H "X-User-Role: operator" ^
  -d "{\"provider\":\"apify\",\"countries\":[\"MX\",\"PE\",\"EC\"],\"product_categories\":[\"sunscreen\",\"calming_serum\",\"cleanser\"],\"max_keywords_per_country_category\":8,\"max_results_per_query\":3,\"dry_run\":true}"
```

Live Apify discovery prerequisites:

```text
APIFY_API_TOKEN=<managed-secret>
APIFY_TIKTOK_ACTOR_ID=clockworks/tiktok-scraper
TIKTOK_PROVIDER_DRY_RUN=false
ALLOW_LIVE_TIKTOK_PROVIDER_CALLS=true
TIKTOK_PROVIDER_DAILY_RESULT_LIMIT=2000
```

The backend loads `work/briwell_mvp_app/.env` automatically for local
development. Keep real provider keys in `.env` or the deployment secret manager
only. Do not commit live secrets to GitHub.

Live provider calls return normalized `creator_import_payload` and
`video_import_payloads`. Set `persist_imports=true` only after a small smoke
run passes. In DB mode, persisted creators enter `creator`, recent post
snapshots enter `video`, and operators can immediately run the recent-20 screen.

The first benchmark should compare Apify, Data365, and Bright Data on the same
MX/PE/EC K-beauty keywords using these quality metrics:

1. country match accuracy
2. beauty and K-beauty relevance
3. recent-20 post availability
4. comment and subtitle availability
5. duplicate rate
6. provider failure rate
7. cost per qualified creator
8. pass rate after recent-20 screening

## AI Adapter Scaffold

AI integration starts with a provider-neutral contract:

```text
app/ai/contracts.py
app/ai/adapters.py
app/ai/gemini.py
app/ai/schema_validation.py
app/schemas/analysis.py
```

`MockAIAdapter` validates the source-risk contract locally. Gemini/OpenAI
provider adapters implement the same `AIAdapter.run()` interface.

Current AI rules:

1. AI outputs must validate against task-specific Pydantic schemas.
2. High Risk and Not Allowed source risk inputs are rejected before provider calls.
3. `GeminiTextAdapter` runs in dry-run mode by default.
4. Live Gemini calls require both `GEMINI_API_KEY` and `ALLOW_LIVE_PROVIDER_CALLS=true`.
5. Dry-run output is deterministic and exists for API contract testing only.
6. Recent-20 screening uses Gemini structured output with the `RecentPostsScreenOutput` schema when live calls are enabled.
7. The Gemini REST adapter sends the key through the `x-goog-api-key` header so provider errors do not include the key in query-string logs.

Environment flags:

```text
GEMINI_API_KEY=
GEMINI_API_BASE_URL=https://generativelanguage.googleapis.com/v1beta
AI_DRY_RUN=true
ALLOW_LIVE_PROVIDER_CALLS=false
AI_LIVE_REQUIRE_DATABASE=true
AI_LIVE_DAILY_CALL_LIMIT=50
AI_LIVE_DAILY_COST_LIMIT_USD=2.00
AI_LIVE_PER_CREATOR_DAILY_CALL_LIMIT=3
```

`POST /ai/validate-output` validates a proposed AI JSON result before it is
stored. `POST /ai/dry-run` runs the Gemini adapter in deterministic dry-run
mode so frontend and worker code can integrate without spending API cost.
`GET /ai/provider-status` reports whether live Gemini calls are configured.

## Analysis Worker

`POST /analysis-jobs/run-dry-run` runs one analysis request through the worker
scaffold and returns both the AI result and an invocation log preview.

Rules currently enforced:

1. The worker uses `GeminiTextAdapter` with dry-run enabled by default through configuration.
2. High Risk and Not Allowed source risk inputs are skipped before provider calls.
3. Invocation log status maps to `success`, `failed`, or `skipped`.
4. Token counts are estimates for MVP cost visibility.
5. When `USE_DATABASE=false`, the log is returned as `validated_not_persisted`.
6. When `USE_DATABASE=true`, the worker persists `ai_invocation_log` and updates job status.

CLI runner:

```bash
python scripts/run_analysis_worker.py --input-json path/to/analysis_run_request.json
```

`GET /ai-invocation-logs` is admin-only and returns persisted AI call logs when
database mode is enabled.

`POST /analysis-jobs/run-multimodal` runs a standardized multimodal video
analysis request. It accepts approved caption, transcript, frame description,
and optional asset URL inputs. It does not scrape, download, or bypass TikTok
access controls.

Multimodal output includes:

1. Product visibility score
2. Skincare context score
3. Content quality score
4. Brand safety score
5. Commerce signal score
6. Visible product types
7. Frame observations
8. Detected risk notes

Live Gemini calls remain gated by `AI_DRY_RUN=false`,
`ALLOW_LIVE_PROVIDER_CALLS=true`, and `GEMINI_API_KEY`.

## Recent 20 Posts First-Pass Screen

`POST /analysis-jobs/run-recent-posts-screen` evaluates the latest 20 approved
recent post snapshots for one creator before deeper profile, comment,
multimodal, and scoring analysis.

Rules currently enforced:

1. Accepts at most 20 recent post snapshots.
2. Uses only approved input data supplied through manual, official API, approved provider, or creator-provided paths.
3. High Risk and Not Allowed source risk inputs are rejected before provider calls.
4. Fewer than 20 posts can be validated, but the output requires human review or more recent posts.
5. The screen returns `suitability_decision`, `suitability_score`, product category matches, coverage gaps, and next step.
6. Passing this screen does not approve outreach by itself; it only moves the creator to full analysis.
7. Set `dry_run=false` and `allow_live_provider_calls=true` in the request to run live Gemini analysis.
8. Set `persist_result=true` with a real database UUID `creator_id` to store the result in `recent_posts_screen_result`.
9. Identical persisted screen outputs for the same creator and source risk are reused instead of duplicated; changed outputs are kept as history.
10. Live calls are blocked before provider invocation when daily call, daily cost, or per-creator limits are reached.

Live Gemini request prerequisites:

```text
AI_DRY_RUN=false
ALLOW_LIVE_PROVIDER_CALLS=true
GEMINI_API_KEY=<managed-secret>
USE_DATABASE=true # only required for persist_result=true
```

Guarded live smoke test:

```bash
python scripts/smoke_gemini_recent20_live.py --confirm-live-cost
```

The script refuses to call Gemini unless `--confirm-live-cost`,
`AI_DRY_RUN=false`, `ALLOW_LIVE_PROVIDER_CALLS=true`, and `GEMINI_API_KEY` are
present. Add `--persist-result --creator-id <db-uuid>` only when DB persistence
is intended.

Golden dataset regression:

```bash
python scripts/evaluate_recent20_golden.py
```

The v0 golden dataset lives at `data/golden/recent20_screen_v0.json` and
contains pass, human-review, recheck-later, and claim-risk cases for the
deterministic recent-20 screen.

## Analysis to Score Handoff

`POST /analysis-jobs/run-creator-score-handoff` converts validated AI analysis
outputs into deterministic creator score inputs, then calculates the final score
through the system scoring layer.

Rules currently enforced:

1. High Risk and Not Allowed source risk levels are rejected.
2. `low_medium` and `medium` handoffs require `X-User-Role: admin`.
3. AI outputs never provide `final_score` directly.
4. Profile, comment, final-review, creator snapshot, and video metric inputs are mapped into score dimensions.
5. `final_score` is still calculated by `app/scoring/creator_score.py`.
6. When `USE_DATABASE=false`, the score is validated without persistence.
7. When `USE_DATABASE=true`, the score is persisted to `creator_analysis`.
8. Persisted DB metadata is kept separate from the strict score output schema.

## Creator Scoring

`POST /creators/{creator_id}/score` calculates deterministic creator scores.

Rules currently enforced:

1. API input accepts score dimensions, not `final_score`.
2. `final_score` is calculated by the system from v0.1 scoring weights.
3. `risk_penalty` is subtracted after the weighted base score.
4. `final_score` is clamped to 0-100.
5. Segment classification is deterministic.
6. `score_confidence < 0.7` adds a review reason.
7. When `USE_DATABASE=false`, the score is validated without persistence.
8. When `USE_DATABASE=true`, the score is upserted into `creator_analysis`.

Formula:

```text
Base Score =
Beauty Fit * 0.25
+ Engagement Quality * 0.20
+ Audience Locality * 0.15
+ Commerce Intent * 0.15
+ Content Quality * 0.10
+ Collaboration Probability * 0.10
+ Cost Efficiency * 0.05

Final Score = clamp(Base Score - Risk Penalty, 0, 100)
```

`GET /creators/{creator_id}/analysis` lists persisted score history when
database mode is enabled.

## Campaign Candidate Ranking

`GET /campaigns/{campaign_id}/candidates` ranks creators for a campaign using
the latest persisted creator analysis.

Rules currently enforced:

1. Candidate reads require `admin`, `operator`, or `campaign_manager`.
2. Campaign creation requires `admin` or `campaign_manager`.
3. The candidate query only reads from `eligible_creator_for_outreach`.
4. The latest creator analysis must meet `min_score` and `max_risk_penalty`.
5. `avoid` segment creators are excluded from campaign candidate results.
6. Product matching uses the campaign product category unless overridden.
7. Existing outreach for the same campaign is excluded by default.
8. Ranking tie-breakers are final score, risk penalty, score confidence, then follower count.
9. When `USE_DATABASE=false`, campaign requests validate without persistence.

## Campaign Outreach Workflow

`POST /campaigns/{campaign_id}/outreach-drafts` prepares DM drafts for selected
campaign candidates.

Rules currently enforced:

1. Requires `admin`, `operator`, or `campaign_manager`.
2. Local mode requires `candidate_snapshots` and `product_category`.
3. DB mode validates selected creators against campaign country, product category, score, risk, and existing outreach filters.
4. High Risk, Not Allowed, do-not-contact, and removal-requested creators are skipped.
5. Candidates below `min_score` or above `max_risk_penalty` are skipped.
6. Drafts are returned with `claims_check_status=needs_review`.
7. The response explicitly sets `send_allowed=false`.
8. No TikTok, Instagram, email, or WhatsApp message is sent automatically.

## Analysis Jobs

`POST /analysis-jobs` creates or validates AI jobs for the MVP pipeline.

Rules currently enforced:

1. `high` and `not_allowed` source risk levels are rejected.
2. `low_medium` and `medium` jobs require `X-User-Role: admin`.
3. `low` jobs can be created by `admin` or `operator`.
4. When `USE_DATABASE=false`, requests are validated without persistence.

Example:

```bash
curl -X POST http://127.0.0.1:8000/analysis-jobs ^
  -H "Content-Type: application/json" ^
  -H "X-User-Role: admin" ^
  -d "{\"job_type\":\"profile_analysis\",\"source_risk_level\":\"low\",\"target_entity_type\":\"creator\",\"target_entity_ids\":[\"creator-1\"],\"model_alias\":\"low_cost_text\"}"
```

## DM Drafts

`POST /outreach/{creator_id}/generate-dm` generates Spanish DM draft variants.

Rules currently enforced:

1. DM generation rejects High Risk and Not Allowed creators.
2. DM generation rejects do-not-contact and removal-request creators.
3. At least two draft variants are returned.
4. Drafts are marked `claims_check_status=needs_review`; sending is not automated.
5. When `USE_DATABASE=false`, include `creator_snapshot` in the request.

The local implementation uses deterministic draft generation so API tests can
run without external AI keys. Gemini/OpenAI adapters can replace this behind the
same contract.

## Claims Check

`POST /outreach/claims-check` runs a deterministic pre-send claim check on a DM
message.

Rules currently enforced:

1. Requires `admin`, `operator`, or `campaign_manager`.
2. Product-specific `claims_disallowed` phrases fail the check.
3. Medical, treatment, cure, acne-treatment, and skin-condition claims fail the check.
4. Guaranteed, instant, and permanent result claims fail the check.
5. Cosmetic claims such as wrinkles, spots, whitening, anti-aging, or SPF require review unless explicitly allowed.
6. In DB mode, an `outreach_id` can be checked and the outreach `claims_check_status` can be updated.
7. Passing claims check does not send a message; human approval is still required before any external send.

## Outreach Review Decision

`POST /outreach/review-decision` records the human review gate for a DM draft.

Rules currently enforced:

1. Requires `admin`, `operator`, or `campaign_manager`.
2. `approve` is only allowed when `claims_check_status=passed`.
3. `request_revision` moves the outreach status to `reviewing`.
4. `reject` moves the outreach status to `rejected`.
5. Post-send outreach statuses cannot be changed by this pre-send review endpoint.
6. The response can mark a draft as ready for manual send, but no external send is automated.
7. In DB mode, an `outreach_id` can be reviewed and the outreach status can be updated.

## Campaign Execution

`POST /outreach/status-transition` records campaign execution status changes.

Rules currently enforced:

1. Requires `admin`, `operator`, or `campaign_manager`.
2. `dm_sent` requires prior approval, passed claims check, do-not-contact check, and manual send confirmation.
3. The endpoint records manual send status only; no external message is sent.
4. Reply and negotiation states require a response summary.
5. Accepted terms require proposed terms.

## Performance Tracking

`POST /performance/snapshots` validates or stores campaign performance snapshots.

Rules currently enforced:

1. Requires `admin`, `operator`, or `campaign_manager`.
2. Source types must be compliant collection paths.
3. High Risk and Not Allowed source-risk levels are blocked.
4. Metrics must be non-negative.
5. `GET /performance/campaigns/{campaign_id}/summary` summarizes persisted campaign metrics in DB mode.

## Settlements

`POST /settlements/contracts` validates or stores creator contract terms.
`POST /settlements/payouts` validates or stores payout requests.

Rules currently enforced:

1. Requires `admin` or `campaign_manager`.
2. Contracts require either `creator_id` or `outreach_id`.
3. Blocked payouts require a blocker reason.
4. Approved or paid payouts require an invoice URL.
5. Paid payouts require a tax document URL.

## Country Compliance

`GET /compliance/rules` returns MX, PE, and EC operating rules for product claims.
`POST /compliance/country-claims-check` checks country and product-specific
claim phrases.

Rules currently enforced:

1. Requires `admin`, `operator`, or `campaign_manager`.
2. Country rules are operational safeguards, not legal advice.
3. High-severity matches fail.
4. Medium-severity matches require review.

## Production Readiness

`GET /ops/readiness` and `GET /ops/security-policy` expose production readiness
checks for admins.

Current production blockers still include:

1. Replace MVP header RBAC with a real identity provider.
2. Move from local portable PostgreSQL to managed PostgreSQL.
3. Configure managed secrets.
4. Keep automated backup and restore tests running.
5. Add gateway or middleware rate limits before public exposure.
6. Configure worker monitoring, provider cost alerts, and error alerts.

## Video Imports

`POST /videos/import` validates or stores representative TikTok video metadata.

Rules currently enforced:

1. `high` and `not_allowed` source risk levels are rejected.
2. Automated scrape-like `source_type` values are rejected.
3. Import batches are capped at 50 videos per request.
4. Metrics must be non-negative.
5. When `USE_DATABASE=false`, requests are validated without persistence.

Example:

```bash
curl -X POST http://127.0.0.1:8000/videos/import ^
  -H "Content-Type: application/json" ^
  -H "X-User-Role: operator" ^
  -d "{\"creator_id\":\"creator-1\",\"source_type\":\"manual\",\"source_risk_level\":\"low\",\"items\":[{\"url\":\"https://example.com/video/1\",\"view_count\":12000}]}"
```

## Comment Samples

`POST /comments/import` validates or stores minimal comment samples for analysis.

Rules currently enforced:

1. `high` and `not_allowed` source risk levels are rejected.
2. Import batches are capped at 50 comments per request.
3. Sample method must be `manual`, `official_api`, `approved_provider`, or `creator_provided`.
4. Comment samples marked as containing sensitive data are rejected.
5. Comments are treated as samples, not a full audience dataset.
