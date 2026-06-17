# Briwell Offline Operations 2-12 Runbook

This runbook covers the work that can proceed before paid TikTok provider
benchmarking is funded. The goal is to make the platform ready to ingest real
provider data later without changing the operator workflow.

## Scope

The paid benchmark step is intentionally excluded:

1. TikTok provider benchmark with paid Apify/Data365/Bright Data volume

The offline-ready flow covers:

2. DB persistence for approved creator and recent-post inputs
3. Recent-20 batch screening
4. AI analysis pipeline planning
5. Multimodal analysis queue planning
6. Operations dashboard integration
7. Campaign matching and outreach planning
8. Performance rollup structure
9. Contract and payout readiness
10. Country and claims compliance checks
11. Production readiness checks
12. External handoff package

## Main Endpoint

Use this endpoint for one-shot dry-run operations:

```text
POST /operations/acquisition-orchestration
```

Recommended local mode:

```json
{
  "source_type": "manual",
  "source_risk_level": "low",
  "product_category": "sunscreen",
  "country": "MX",
  "creator_candidates": [],
  "recent_posts_by_creator": {},
  "persist_imports": false,
  "recent_screen_dry_run": true,
  "persist_recent_screen_results": false,
  "run_campaign_match": true,
  "build_outreach_plan": true
}
```

When PostgreSQL is enabled, set:

```json
{
  "persist_imports": true,
  "persist_recent_screen_results": true
}
```

## What The Endpoint Returns

The response is a complete operator report:

```text
quality_gate
import
enrichment
recent_20_batch
analysis_pipeline
campaign_match
outreach_plan
crm_board
performance
settlement
compliance
production_readiness
handoff_package
next_actions
```

## Operating Rules

1. Only `low`, `low_medium`, and `medium` source-risk inputs are accepted.
2. High-risk and not-allowed collection paths stay blocked.
3. DM drafts are never auto-sent.
4. Outreach requires claims check, human approval, and manual send confirmation.
5. Payout requires accepted contract, delivered content, post URL, invoice or
   receipt, and tax document if required.
6. Live Gemini analysis can be enabled later, but offline dry-run is the default
   for repeatable QA.

## Recommended Sequence Before Paid Benchmark

1. Load or create creator candidates through CSV/manual import.
2. Attach up to 20 recent posts per creator.
3. Run `/operations/acquisition-orchestration`.
4. Review `quality_gate.blocker_count` and `recent_20_batch.queue_counts`.
5. Move `full_analysis_queue` creators into profile, comment, multimodal, score,
   and final-review jobs.
6. Review `campaign_match.items`.
7. Review `outreach_plan.items` and `compliance.checks`.
8. Create contracts and payout records only after creators accept terms.
9. Record performance snapshots once posts go live.
10. Use `production_readiness.recommended_order` before public deployment.

## Verification

Run these commands before handoff:

```powershell
cd work\briwell_mvp_app
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts\validate_csv_imports.py
.venv\Scripts\python.exe scripts\evaluate_recent20_golden.py

cd ..\briwell_dashboard_app
node tests\smoke.mjs
```

For DB integration:

```powershell
$pw = Get-Content ..\postgres_pw.txt
$env:RUN_DB_TESTS='1'
$env:USE_DATABASE='true'
$env:DATABASE_URL="postgresql://briwell:$pw@127.0.0.1:55432/briwell"
.venv\Scripts\python.exe -m pytest tests\test_db_integration.py -q
```

## After Provider Balance Is Funded

Return to step 1 and run a paid provider benchmark using the same MX/PE/EC
K-beauty keyword playbook. Feed the resulting normalized creators and recent
posts into `/operations/acquisition-orchestration` so all downstream workflows
remain identical.
