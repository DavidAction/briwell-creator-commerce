# Briwell API Spec v0

작성일: 2026-06-17  
대상: Briwell Influencer Intelligence MVP v0.1  
Backend recommendation: FastAPI  
Rule: API must not create or run High Risk collection jobs in MVP v0.1.

## 1. API Principles

1. All write endpoints require authenticated users.
2. Every collection or analysis job must include `source_risk_level`.
3. Allowed source risk levels for MVP v0.1: `low`, `low_medium`, `medium`.
4. `high` and `not_allowed` source risk levels cannot be used to create jobs, videos, comments, or outreach.
5. All AI outputs must be saved as validated JSON with `analysis_version` and model log references.
6. DM generation is allowed, but DM sending is not automated by the system.
7. Do-not-contact and removal-request rules are enforced before DM generation or outreach status changes.

## 2. Common Conventions

### 2.1 Auth

Use bearer token auth.

Roles:

1. `admin`
2. `operator`
3. `campaign_manager`
4. `viewer`

### 2.2 Pagination

List endpoints use:

```text
?limit=50&cursor={cursor}
```

Response:

```json
{
  "items": [],
  "next_cursor": null
}
```

### 2.3 Error Shape

```json
{
  "error": {
    "code": "SOURCE_RISK_NOT_ALLOWED",
    "message": "High Risk collection is not allowed in MVP v0.1.",
    "details": {}
  }
}
```

Common error codes:

| Code | Meaning |
|---|---|
| SOURCE_RISK_NOT_ALLOWED | High or Not Allowed source risk was requested |
| DO_NOT_CONTACT | Creator cannot be contacted |
| CLAIMS_CHECK_REQUIRED | DM cannot be approved before claims check |
| VALIDATION_FAILED | Request schema validation failed |
| NOT_FOUND | Entity not found |
| PERMISSION_DENIED | User role is not allowed |
| AI_SCHEMA_INVALID | AI output failed JSON schema validation |
| BUDGET_EXCEEDED | Campaign or job AI budget exceeded |

## 3. Creators

### GET /creators

Purpose: Search and filter creators.

Roles: admin, operator, campaign_manager, viewer

Query params:

```text
country=MX|PE|EC
product_category=sunscreen|calming_serum|cleanser|sheet_mask|cushion_foundation
segment=viral_micro|beauty_educator|review_creator|commerce_creator|brand_builder|ugc_creator|avoid
min_score=0
max_score=100
max_risk_penalty=30
source_risk_level=low|low_medium|medium
contact_available=true|false
outreach_status=dm_drafted
q=username_or_keyword
limit=50
cursor=...
```

Rules:

1. Default search excludes `quarantined`, `removed`, `do_not_contact`, and High Risk records.
2. Admin-only quarantine views may include High Risk records, but these records cannot be analyzed or contacted.

### GET /creators/{creator_id}

Purpose: Creator detail with latest analysis, videos, comment insights, outreach history.

Roles: all roles

Response includes:

```json
{
  "creator": {},
  "latest_analysis": {},
  "videos": [],
  "comment_insights": {},
  "outreach": [],
  "source_metadata": {}
}
```

### POST /creators/import

Purpose: Import Low/Medium Risk creator candidates from CSV or approved provider output.

Roles: admin, operator

Request:

```json
{
  "source_type": "csv_import",
  "source_risk_level": "low",
  "items": [
    {
      "country": "MX",
      "username": "creator_name",
      "profile_url": "https://...",
      "display_name": "Creator",
      "bio": "",
      "follower_count": 12000,
      "source_url": "https://..."
    }
  ]
}
```

Rules:

1. `source_risk_level` must be `low`, `low_medium`, or `medium`.
2. `high` and `not_allowed` are rejected.
3. Missing source metadata is rejected.

### PATCH /creators/{creator_id}

Purpose: Update creator metadata, status, contact info, or do-not-contact flag.

Roles: admin, operator

Important fields:

```json
{
  "contact_email": "creator@example.com",
  "instagram_url": "https://instagram.com/...",
  "do_not_contact": true,
  "status": "do_not_contact",
  "operator_note": "Asked not to be contacted."
}
```

Rules:

1. Changing `do_not_contact` creates AuditLog.
2. `do_not_contact = true` removes creator from outreach queues.

## 4. Videos and Comments

### POST /videos/import

Purpose: Import video metadata from Low/Medium Risk sources.

Roles: admin, operator

Request:

```json
{
  "creator_id": "uuid",
  "source_type": "manual",
  "source_risk_level": "medium",
  "items": [
    {
      "url": "https://...",
      "caption": "caption text",
      "hashtags": ["kbeauty"],
      "view_count": 10000,
      "like_count": 1200,
      "comment_count": 80
    }
  ]
}
```

Rules:

1. Bulk automated public-page collection is not supported in MVP v0.1.
2. Only approved Low/Medium sources can be imported.

### POST /comments/import

Purpose: Import minimal comment samples.

Roles: admin, operator

Request:

```json
{
  "video_id": "uuid",
  "sample_method": "manual",
  "source_risk_level": "medium",
  "items": [
    {
      "comment_text": "Donde lo compro?",
      "like_count": 4
    }
  ]
}
```

Rules:

1. Store minimal comment samples only.
2. Do not import high-volume scraped comment sets.
3. Reject `source_risk_level = high`.

## 5. Analysis Jobs

### GET /analysis-jobs

Purpose: List AI jobs, status, and cost.

Roles: admin, operator, campaign_manager

Query params:

```text
job_type=profile_analysis
status=queued|running|completed|failed
source_risk_level=low|low_medium|medium
```

### POST /analysis-jobs

Purpose: Create an AI analysis job.

Roles: admin, operator

Request:

```json
{
  "job_type": "profile_analysis",
  "source_risk_level": "low_medium",
  "target_entity_type": "creator",
  "target_entity_ids": ["uuid"],
  "model_alias": "low_cost_text",
  "estimated_cost_usd": 1.25
}
```

Rules:

1. `source_risk_level` must be `low`, `low_medium`, or `medium`.
2. `low_medium` and `medium` jobs require admin approval.
3. `high` and `not_allowed` are rejected.
4. If campaign AI budget is exceeded, return `BUDGET_EXCEEDED`.

### POST /creators/{creator_id}/analyze

Purpose: Analyze one creator.

Roles: admin, operator

Runs:

1. profile analysis
2. comment analysis if comment samples exist
3. video/multimodal analysis if approved video samples exist
4. scoring

Response:

```json
{
  "analysis_job_id": "uuid",
  "status": "queued"
}
```

### POST /creators/batch-analyze

Purpose: Analyze creator batch.

Roles: admin

Rules:

1. Batch size default max: 100 creators.
2. Only creators from eligible Low/Medium Risk sources are accepted.
3. AI costs must be estimated before job creation.

## 6. Creator Analysis

### GET /creators/{creator_id}/analysis

Purpose: List analysis history for a creator.

Roles: all roles

### POST /creators/{creator_id}/score

Purpose: Recalculate deterministic score from existing AI fields and scoring rules.

Roles: admin, operator

Rules:

1. AI does not directly set final_score without deterministic scoring service.
2. Risk Penalty remains separate from Base Score.

## 7. Campaigns

### GET /campaigns

Roles: all roles

Query params:

```text
country=MX
status=active
product_category=sunscreen
```

### POST /campaigns

Roles: admin, campaign_manager

Request:

```json
{
  "name": "MX Sunscreen Pilot",
  "country": "MX",
  "product_id": "uuid",
  "product_category": "sunscreen",
  "campaign_goal": "coupon_conversion",
  "budget": 1500,
  "sales_channel": "shopify",
  "tracking_url": "https://...",
  "coupon_code_prefix": "BRIMXSPF",
  "target_creator_count": 30,
  "target_post_count": 20
}
```

### GET /campaigns/{campaign_id}/candidates

Purpose: Recommended creators for a campaign.

Roles: admin, operator, campaign_manager

Rules:

1. Exclude do-not-contact and quarantined creators.
2. Exclude Risk Penalty 20+.
3. Default sort by Final Score desc, then Risk Penalty asc.

## 8. Outreach

### POST /outreach/{creator_id}/generate-dm

Purpose: Generate DM drafts.

Roles: admin, operator, campaign_manager

Request:

```json
{
  "campaign_id": "uuid",
  "dm_variant": "soft_intro",
  "product_category": "sunscreen",
  "model_alias": "multimodal_default"
}
```

Rules:

1. Reject if creator is do-not-contact.
2. Reject if source risk is High or Not Allowed; do not create an outreach record.
3. Create claims check job after DM generation.
4. Return at least 2 DM draft variants when possible.

### PATCH /outreach/{outreach_id}/status

Purpose: Update outreach status.

Roles: admin, operator, campaign_manager

Request:

```json
{
  "status": "dm_sent",
  "operator_notes": "Sent via Instagram manually."
}
```

Rules:

1. Status `dm_sent` requires `claims_check_status = passed`.
2. Status `dm_sent` requires `do_not_contact_checked_at`.
3. All status changes create AuditLog.

### POST /outreach/{outreach_id}/response-summary

Purpose: Summarize creator response and next action.

Roles: admin, operator

Request:

```json
{
  "response_text": "Gracias, mandame mas informacion.",
  "model_alias": "low_cost_text"
}
```

Response:

```json
{
  "response_summary": "Creator is interested and asked for more details.",
  "next_action": "send_proposal",
  "sentiment": "positive"
}
```

## 9. Products

### GET /products

Roles: all roles

### POST /products

Roles: admin, campaign_manager

Required fields:

1. brand_name
2. product_name
3. product_category
4. country_availability
5. key_claims_allowed
6. claims_disallowed

## 10. Keywords

### GET /keywords

Roles: all roles

Query params:

```text
country=MX
product_category=sunscreen
status=active
```

### POST /keywords

Roles: admin

Request:

```json
{
  "country": "MX",
  "language": "es",
  "keyword": "protector solar coreano",
  "hashtag": "#protectorsolar",
  "product_category": "sunscreen",
  "intent_type": "discovery",
  "priority": 1
}
```

## 11. AI Invocation Logs

### GET /ai-invocation-logs

Purpose: Inspect AI cost, latency, errors, and prompt versions.

Roles: admin

Query params:

```text
analysis_job_id=uuid
model_alias=low_cost_text
target_entity_type=creator
```

## 12. Operator Feedback

### POST /operator-feedback

Purpose: Store human corrections for future scoring/prompt improvement.

Roles: admin, operator, campaign_manager

Request:

```json
{
  "creator_id": "uuid",
  "analysis_id": "uuid",
  "feedback_type": "segment_change",
  "original_value": {"segment": "viral_micro"},
  "corrected_value": {"segment": "review_creator"},
  "notes": "Creator is more review-oriented than viral."
}
```

## 13. Admin Settings

### GET /admin/scoring-rules

Roles: admin

### PATCH /admin/scoring-rules

Roles: admin

Rules:

1. Scoring rule changes create a new `rule_version`.
2. Existing historical analyses are not overwritten.

### GET /admin/model-configs

Roles: admin

### PATCH /admin/model-configs/{model_config_id}

Roles: admin

Rules:

1. Model price verification date is required when changing active models.
2. Deprecated models cannot be selected for new jobs.

## 14. QA Review Log

### Pass 1: PRD Coverage

Verified:

1. Creators, Videos, Comments, Campaigns, Outreach, Products, Keywords, AI Jobs, AI Logs, Feedback, Admin settings are covered.
2. Dashboard wireframe actions have corresponding API endpoints.

### Pass 2: Low/Medium Risk Enforcement

Verified:

1. Job creation rejects High and Not Allowed source risk levels.
2. Video/comment import rejects High Risk data.
3. DM generation rejects High Risk, Not Allowed, do-not-contact, and removal-request creators.

### Pass 3: Engineering Readiness

Verified:

1. Each endpoint has role assumptions.
2. Error shape and common error codes are defined.
3. Score recalculation and AI-generated output are separated.
4. AI cost tracking is exposed through logs.
