# Briwell Campaign Candidate Ranking Step Review v0

Created: 2026-06-17

Status: Campaign management and candidate ranking API scaffold implemented and verified.

## 1. Scope Implemented

This step adds the first campaign-level workflow after creator analysis persistence.

Implemented scope:

1. `GET /campaigns`
2. `POST /campaigns`
3. `GET /campaigns/{campaign_id}/candidates`
4. Campaign repository backed by the existing `campaign` table
5. Candidate repository query using `eligible_creator_for_outreach`
6. Latest-score candidate query using `latest_creator_analysis`
7. Deterministic candidate priority labels
8. Ranking tie-breakers
9. API smoke tests and ranking unit tests
10. README update

## 2. Candidate Ranking Logic

Default candidate query:

1. Campaign country match
2. Product category match against `creator_analysis.recommended_products`
3. `final_score >= min_score`, default 70
4. `risk_penalty <= max_risk_penalty`, default 10
5. Exclude `avoid` segment creators
6. Read only from `eligible_creator_for_outreach`
7. Exclude existing outreach for the same campaign by default

Ranking order:

1. Higher final score
2. Lower risk penalty
3. Higher score confidence
4. Higher follower count

Priority labels:

1. `priority_outreach`: final score >= 85 and risk penalty <= 5
2. `outreach_candidate`: final score >= 70 and risk penalty <= 10
3. `human_review`: final score >= 60 and risk penalty <= 15
4. `recheck_later`: final score >= 50 and risk penalty <= 20
5. `store_only`: all remaining cases

## 3. Files Changed

Backend:

1. `app/routers/campaigns.py`
2. `app/repositories/campaigns.py`
3. `app/ranking/campaign_candidates.py`
4. `app/ranking/__init__.py`
5. `app/main.py`

Tests:

1. `tests/test_api_smoke.py`
2. `tests/test_campaign_ranking.py`
3. `tests/test_db_integration.py`

Docs:

1. `README.md`

## 4. Three-Pass Review

### Pass 1: Product and PRD Alignment

Result: Pass

Checks:

1. Campaigns can be created before outreach.
2. Candidate recommendations are tied to campaign country and product category.
3. Ranking uses the persisted creator analysis layer from the previous step.
4. The endpoint is useful for Mexico, Peru, and Ecuador without new schema work.
5. The output is ready for a future human-approved DM workflow.

### Pass 2: Safety and Policy Review

Result: Pass

Checks:

1. Candidate reads use `eligible_creator_for_outreach`, which excludes blocked creators.
2. High Risk and Not Allowed creators remain outside outreach eligibility.
3. `do_not_contact`, removal-requested, quarantined, removed, and avoided creators are excluded by the DB view.
4. `avoid` segment creators are explicitly excluded from candidate results.
5. No automated DM send behavior was added.
6. Existing outreach for the same campaign is excluded by default to prevent duplicate contact.

### Pass 3: Engineering Readiness

Result: Pass

Checks:

1. DB-backed code is isolated in repositories.
2. The ranking layer is pure and unit-testable without PostgreSQL.
3. Default local mode still validates requests without persistence.
4. Query limits are bounded to 1-100.
5. `product_id` is API-validated as UUID before DB insertion.
6. Existing API behavior remains backward compatible.

## 5. Validation Result

Latest validation:

```text
71 passed, 2 skipped
compileall passed
CSV validation passed
HTTP smoke passed
```

Skipped tests:

1. DB connection test
2. Required tables integration test

Reason: They require `RUN_DB_TESTS=1` with a live PostgreSQL database.

## 6. Remaining Gaps

1. Live PostgreSQL integration tests still need a running DB.
2. Candidate API currently ranks from existing analysis rows; the worker-to-score handoff is the next backend step.
3. Candidate results are not yet connected to DM draft generation.
4. No frontend dashboard exists yet for campaign managers.
