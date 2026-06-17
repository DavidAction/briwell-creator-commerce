# Briwell Campaign Outreach Workflow Step Review v0

Created: 2026-06-17

Status: Campaign candidate to outreach draft workflow implemented and verified.

## 1. Scope Implemented

This step connects campaign candidate ranking to human-approved DM draft preparation.

Implemented scope:

1. `POST /campaigns/{campaign_id}/outreach-drafts`
2. Batch preparation for selected campaign candidates
3. Local-mode support through `candidate_snapshots`
4. DB-mode validation through `eligible_creator_for_outreach` and `latest_creator_analysis`
5. Campaign candidate score and risk filters before draft preparation
6. DM draft generation through the existing deterministic draft builder
7. Claims-check pending state in every prepared item
8. Explicit `send_allowed=false`
9. API smoke tests
10. README and visual review update

## 2. Workflow Behavior

Request behavior:

1. In DB mode, pass selected `creator_ids`.
2. In local mode, pass `candidate_snapshots` and `product_category`.
3. Optional filters: `min_score`, `max_risk_penalty`, and `exclude_existing_outreach`.
4. Optional DM settings: `dm_variant`, `product_name`, and `model_alias`.

Response behavior:

1. Eligible creators are returned under `items`.
2. Blocked or ineligible creators are returned under `skipped`.
3. Each prepared item includes `outreach`, `selected_draft`, `drafts`, and `claims_check_job`.
4. Claims check remains `needs_review`.
5. No message send action is performed.

## 3. Three-Pass Review

### Pass 1: Product and Workflow Alignment

Result: Pass

Checks:

1. Candidate ranking can now feed outreach draft preparation.
2. Campaign managers can prepare multiple selected candidates in one request.
3. Local MVP mode remains usable without PostgreSQL.
4. Product category and product name are carried into Spanish DM drafts.
5. Prepared drafts are ready for a future operator review UI.

### Pass 2: Safety and Policy Review

Result: Pass

Checks:

1. High Risk and Not Allowed creators are skipped.
2. Do-not-contact and removal-requested creators are skipped.
3. Candidates below score threshold are skipped.
4. Candidates above risk penalty threshold are skipped.
5. Drafts are marked `claims_check_status=needs_review`.
6. Response explicitly states `send_allowed=false`.
7. No external DM, email, WhatsApp, or social message is sent.

### Pass 3: Engineering Readiness

Result: Pass

Checks:

1. New DB query reuses existing candidate eligibility views.
2. Local-mode candidate snapshots are validated by Pydantic.
3. Existing single-creator DM endpoint remains backward compatible.
4. Existing candidate ranking endpoint remains backward compatible.
5. Tests cover success, blocked candidates, low-score skip, viewer rejection, and missing product category.

## 4. Validation Result

Latest validation:

```text
83 passed, 2 skipped
compileall passed
CSV validation passed
HTTP smoke passed
```

Skipped tests:

1. DB connection test
2. Required tables integration test

Reason: They require `RUN_DB_TESTS=1` with a live PostgreSQL database.

## 5. Remaining Gaps

1. Live PostgreSQL integration tests still need a running DB.
2. Claims-check jobs are represented as queued previews; automated claims-check execution is not implemented yet.
3. Human approval UI is not implemented yet.
4. No external DM sending integration is implemented or allowed in MVP v0.1.
