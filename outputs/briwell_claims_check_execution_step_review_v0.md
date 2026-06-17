# Briwell Claims Check Execution Step Review v0

Created: 2026-06-17

Status: Deterministic claims-check execution implemented and verified.

## 1. Scope Implemented

This step adds a pre-send compliance check for DM draft text.

Implemented scope:

1. `app/compliance/claims.py`
2. `POST /outreach/claims-check`
3. Product-specific disallowed claim detection
4. Medical, treatment, cure, acne, and skin-condition claim blocking
5. Guaranteed, instant, and permanent result claim blocking
6. Cosmetic claim review detection
7. Optional DB-mode outreach status update
8. Unit and API smoke tests
9. README and visual review update

## 2. Claims Check Behavior

Result statuses:

1. `passed`: no blocked or review-required claims detected
2. `needs_review`: cosmetic or product claim language needs human review
3. `failed`: blocked or disallowed claim detected

Blocked examples:

1. Cure claims
2. Acne treatment claims
3. Medical skin-condition claims
4. Guaranteed result claims
5. Permanent or instant result claims
6. Product-specific disallowed claims

Review examples:

1. SPF claims not listed in allowed product claims
2. Wrinkle claims
3. Spot or pigmentation claims
4. Whitening claims
5. Anti-aging claims

## 3. Three-Pass Review

### Pass 1: Product and Workflow Alignment

Result: Pass

Checks:

1. Campaign outreach drafts can now be checked before any send step exists.
2. Single DM drafts can be checked directly.
3. Product-specific allowed and disallowed claim lists are supported.
4. The result maps to the existing `claims_check_status` enum.
5. DB mode can update an existing outreach record when `outreach_id` is provided.

### Pass 2: Safety and Policy Review

Result: Pass

Checks:

1. The endpoint does not send messages.
2. Passing claims check still requires human approval before send.
3. Failed checks return `safe_to_send=false`.
4. Review-required checks return `safe_to_send=false`.
5. Medical and guaranteed-result claims are blocked.
6. Cosmetic claims are conservatively routed to review.

### Pass 3: Engineering Readiness

Result: Pass

Checks:

1. Claims logic is isolated in `app/compliance/claims.py`.
2. Route ordering keeps `/outreach/claims-check` ahead of `/{creator_id}/generate-dm`.
3. Text normalization uses `unicodedata` instead of non-ASCII literal replacements.
4. Tests cover pass, fail, review, allowed claim override, missing message, and role rejection.
5. Existing DM generation endpoints remain backward compatible.

## 4. Validation Result

Latest validation:

```text
91 passed, 2 skipped
compileall passed
CSV validation passed
HTTP smoke passed
Zip content verification passed
```

HTTP smoke covered:

1. `GET /health` returned `ok`.
2. Safe collaboration DM returned `passed` with human approval still required.
3. Medical/disallowed claims returned `failed` with `safe_to_send=false`.

Zip verification covered:

1. Required claims-check source and tests are included.
2. Local `.venv` files are excluded.
3. Python cache and pytest cache folders are excluded.

Skipped tests:

1. DB connection test
2. Required tables integration test

Reason: They require `RUN_DB_TESTS=1` with a live PostgreSQL database.

## 5. Remaining Gaps

1. Live PostgreSQL integration tests still need a running DB.
2. Claims rules are deterministic MVP rules, not jurisdiction-specific legal advice.
3. Country-specific cosmetic ad compliance rules for Mexico, Peru, and Ecuador need legal review before production.
4. Human approval UI is not implemented yet.
