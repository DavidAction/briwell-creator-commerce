# Briwell Outreach Review Gate Step Review v0

Created: 2026-06-17

Status: Human review decision gate implemented and verified.

## 1. Scope Implemented

This step adds a pre-send human approval gate for outreach DM drafts.

Implemented scope:

1. `app/compliance/outreach_review.py`
2. `POST /outreach/review-decision`
3. Approval, revision request, and rejection decision handling
4. Approval blocked unless claims check has passed
5. Post-send outreach status changes blocked from this pre-send endpoint
6. Optional DB-mode outreach status update
7. Unit and API smoke tests
8. README and visual review update

## 2. Review Gate Behavior

Supported decisions:

1. `approve`: moves the outreach to `approved`
2. `request_revision`: moves the outreach to `reviewing`
3. `reject`: moves the outreach to `rejected`

Approval rules:

1. `approve` requires `claims_check_status=passed`.
2. `failed`, `needs_review`, and `not_checked` cannot be approved.
3. Post-send statuses such as `dm_sent`, `replied`, or `completed` cannot be changed by this endpoint.
4. A successful approval marks the draft as ready for manual send only.
5. No TikTok, Instagram, email, or WhatsApp message is sent automatically.

## 3. Three-Pass Review

### Pass 1: Product and Workflow Alignment

Result: Pass

Checks:

1. Campaign DM draft creation now has a concrete human review step after claims check.
2. Local mode can validate approval decisions without a database.
3. DB mode can read the stored outreach status and claims-check status by `outreach_id`.
4. Existing `outreach_status` values are reused instead of adding new schema complexity.
5. The response clearly separates human approval from external sending.

### Pass 2: Safety and Policy Review

Result: Pass

Checks:

1. Unchecked, failed, or review-required claims cannot be approved.
2. Viewer role is blocked from review decisions.
3. Post-send outreach records cannot be changed through this pre-send review endpoint.
4. `ready_for_manual_send=true` never means automated sending.
5. The response always includes `external_send_automated=false` and `manual_send_only=true`.

### Pass 3: Engineering Readiness

Result: Pass

Checks:

1. Review logic is isolated in `app/compliance/outreach_review.py`.
2. Static route `/outreach/review-decision` is declared before `/{creator_id}/generate-dm`.
3. API tests cover approve, block, revision, and role rejection paths.
4. Unit tests cover approval, failed claims, revision, and post-send blocking.
5. Existing DM generation and claims-check endpoints remain backward compatible.

## 4. Validation Result

Latest validation:

```text
99 passed, 2 skipped
compileall passed
CSV validation passed
HTTP smoke passed
Zip content verification passed
```

HTTP smoke covered:

1. `GET /health` returned `ok`.
2. Passed claims check plus `approve` returned `approved`.
3. Revision request returned `reviewing`.
4. Failed claims check plus `approve` returned `CLAIMS_CHECK_NOT_PASSED`.
5. Approved drafts were marked ready for manual send only, with external send automation disabled.

Skipped tests:

1. DB connection test
2. Required tables integration test

Reason: They require `RUN_DB_TESTS=1` with a live PostgreSQL database.

## 5. Remaining Gaps

1. Live PostgreSQL integration tests still need a running DB.
2. Actual DM sending is intentionally not implemented.
3. A dashboard UI for human review decisions is not implemented yet.
4. Country-specific legal review is still required before production outreach.
