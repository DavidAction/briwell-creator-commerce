# Briwell Analysis to Score Handoff Step Review v0

Created: 2026-06-17

Status: AI analysis output to creator scoring handoff implemented and verified.

## 1. Pre-Step Review

Reviewed the two previous implementation steps before adding new code:

1. Creator scoring and persistence
2. Campaign candidate ranking

Findings:

1. The campaign candidate ranking flow remained aligned with MVP policy.
2. The creator scoring API still correctly blocks direct `final_score` input.
3. Candidate ranking still excludes `avoid` segment creators.
4. No automated DM send behavior was introduced.
5. One DB-mode robustness gap was found in the new handoff path: persisted `creator_analysis` rows contain repository metadata that should not be validated directly against the strict score output schema.

Fix applied:

1. Added `score_output_from_persisted_row()` to strip DB metadata before schema validation.
2. Added a regression test using Decimal values and extra DB fields.

## 2. Scope Implemented

This step connects validated AI analysis outputs to deterministic creator scoring.

Implemented scope:

1. `app/workers/scoring_handoff.py`
2. `POST /analysis-jobs/run-creator-score-handoff`
3. Mapping from profile analysis to score dimensions
4. Mapping from comment analysis to engagement and commerce dimensions
5. Mapping from final review to products, campaign angle, and review notes
6. Mapping from creator snapshot and video metrics to audience/content/cost dimensions
7. Source-risk enforcement before scoring
8. Optional DB persistence to `creator_analysis`
9. Unit and API tests
10. README update

## 3. Handoff Logic

Input sources:

1. `profile_analysis`
2. `comment_analysis`
3. `final_review`
4. `creator_snapshot`
5. `video_metrics`

Generated score dimensions:

1. `beauty_fit_score`
2. `engagement_quality_score`
3. `audience_locality_score`
4. `commerce_intent_score`
5. `content_quality_score`
6. `collaboration_probability_score`
7. `cost_efficiency_score`
8. `risk_score`
9. `risk_penalty`
10. `recommended_products`
11. `recommended_campaign_angle`
12. `ai_summary`
13. `ai_evidence`
14. `score_confidence`
15. `review_required_reason`

Critical rule:

AI outputs do not set `final_score`. The handoff builds component inputs only.
`final_score` is still calculated by the deterministic system scoring layer.

## 4. Three-Pass Review

### Pass 1: Product and Workflow Alignment

Result: Pass

Checks:

1. The flow now supports analysis to score to campaign candidate ranking.
2. The endpoint can operate without a live DB for local MVP development.
3. The same handoff can later receive live Gemini outputs.
4. Profile, comment, and final-review evidence is preserved in `ai_evidence`.
5. The output can be used immediately by candidate ranking once persisted.

### Pass 2: Safety and Policy Review

Result: Pass

Checks:

1. High Risk and Not Allowed handoffs are blocked.
2. `low_medium` and `medium` handoffs require admin approval at the API layer.
3. No outreach or DM send action is created by this step.
4. Review-required reasons are preserved from upstream AI analysis.
5. Low-confidence or limited-input cases remain reviewable rather than silently approved.

### Pass 3: Engineering Readiness

Result: Pass

Checks:

1. Handoff logic is isolated in a worker module.
2. The scoring formula remains centralized in `app/scoring/creator_score.py`.
3. Repository metadata is stripped before strict score schema validation.
4. Decimal values from PostgreSQL are accepted in the persistence path.
5. Tests cover worker logic, API behavior, high-risk rejection, and admin approval.

## 5. Validation Result

Latest validation:

```text
78 passed, 2 skipped
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
2. The handoff currently accepts analysis outputs in the request body; the next refinement can fetch latest persisted analysis outputs automatically.
3. Multimodal/video analysis is represented through `video_metrics`; frame-level multimodal scoring still needs a dedicated output schema.
4. Candidate results are not yet connected to DM draft generation in one workflow.
