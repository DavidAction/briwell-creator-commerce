# Briwell MVP v0.1 Implementation Handoff

작성일: 2026-06-17  
상태: PRD 이후 개발 착수 준비 패키지  
핵심 결정: MVP v0.1은 Low/Medium Risk 소스만 사용한다. High Risk 수집은 생성/실행하지 않는다.

## 1. Artifact Index

| File | Purpose |
|---|---|
| `briwell_mvp_v0_1_prd.md` | 전체 PRD, 범위, 리스크, 데이터 모델, 로드맵 |
| `briwell_product_strategy_v0.md` | 제품군, 국가별 캠페인 전략, 허용/금지 표현 |
| `briwell_keyword_seed_v0.csv` | 3개국 x 5개 제품군 x 5개 seed, 총 75개 키워드 |
| `briwell_scoring_rubric_v0.md` | 100점 스코어링 루브릭, 리스크 차감, 자동 제외 기준 |
| `briwell_dashboard_wireframes_v0.md` | 대시보드 화면, 권한, 필터, 비활성 조건 |
| `briwell_database_schema_v0.sql` | PostgreSQL schema, 제약, 트리거, 뷰 |
| `briwell_seed_data_v0.sql` | 스코어링 룰과 AI 모델 레지스트리 seed |
| `briwell_api_spec_v0.md` | MVP API 엔드포인트, 권한, 요청/응답, 에러 규칙 |
| `briwell_ai_prompts_v0.md` | AI 분석/DM/claims check 프롬프트와 JSON schema |
| `briwell_pilot_operations_playbook_v0.md` | Low/Medium Risk 기반 파일럿 운영 SOP |
| `briwell_creator_import_template.csv` | 후보 크리에이터 업로드 템플릿 |
| `briwell_video_import_template.csv` | 승인된 영상 메타데이터 업로드 템플릿 |
| `briwell_comment_sample_template.csv` | 승인된 댓글 샘플 업로드 템플릿 |

## 2. Build Order

권장 개발 순서:

1. PostgreSQL schema 적용
2. seed data 적용
3. keyword CSV import
4. FastAPI 프로젝트 scaffold
5. Auth/role middleware
6. Creator/Product/Keyword 기본 CRUD
7. AnalysisJob/AiInvocationLog 기반 작업 큐
8. Gemini/OpenAI model adapter
9. Scoring service
10. Dashboard frontend
11. Outreach CRM
12. Pilot data import and eval

## 3. Sprint Plan

### Sprint 0: Setup and Contracts

Duration: 1 week

Deliverables:

1. Repo scaffold
2. Environment config
3. DB migration setup
4. SQL schema review
5. API response/error contract
6. AI provider config contract
7. Low/Medium Risk policy test cases

Acceptance:

1. DB schema can be migrated in local/dev.
2. Seed data can be loaded.
3. API healthcheck returns build version.
4. High Risk analysis job creation test fails as expected.

### Sprint 1: Core Data and Admin

Duration: 1-2 weeks

Deliverables:

1. Products CRUD
2. Keywords import/export
3. Creators import/list/detail
4. Source metadata validation
5. Eligible creator view in API
6. AuditLog basic write path

Acceptance:

1. 75 keyword seeds are imported.
2. Creator import rejects missing source metadata.
3. Creator import quarantines or rejects invalid source risk according to API rules.
4. Creator list excludes quarantined/do-not-contact records by default.

### Sprint 2: AI Job Pipeline

Duration: 2 weeks

Deliverables:

1. AnalysisJob model and worker
2. AiInvocationLog
3. Gemini text adapter
4. Gemini multimodal adapter
5. OpenAI transcription/moderation adapter
6. JSON schema validation
7. Cost logging

Acceptance:

1. Profile analysis returns valid JSON.
2. Comment analysis returns valid JSON.
3. Multimodal analysis runs only on approved video samples.
4. High Risk job requests are rejected.
5. AI invocation cost and latency are logged.

### Sprint 3: Scoring and Review Queue

Duration: 1 week

Deliverables:

1. Deterministic scoring service
2. Risk Penalty service
3. Segment classifier
4. Review queue rules
5. OperatorFeedback write path

Acceptance:

1. Base Score weights sum to 100%.
2. Risk Penalty is stored separately.
3. Final Score is clamped to 0-100.
4. score_confidence below 0.7 creates review requirement.

### Sprint 4: Dashboard v0

Duration: 2 weeks

Deliverables:

1. Overview page
2. Creators page
3. Creator detail page
4. Review Queue page
5. Campaigns page
6. Products and Keywords admin pages
7. AI Jobs page

Acceptance:

1. Users can filter creators by country, product category, score, risk, and segment.
2. Creator detail shows source metadata and AI evidence.
3. High Risk records are not eligible for outreach.
4. Review actions create audit logs.

### Sprint 5: Outreach CRM

Duration: 1-2 weeks

Deliverables:

1. DM draft generation
2. Claims check
3. Outreach status pipeline
4. Response summary
5. Do-not-contact gate
6. Campaign candidate list

Acceptance:

1. DM generation is blocked for do-not-contact creators.
2. DM approval requires passed claims check.
3. `dm_sent` status requires manual confirmation.
4. Outreach status changes create audit logs.

### Sprint 6: Pilot

Duration: 2 weeks

Deliverables:

1. Mexico pilot import
2. Peru pilot import
3. Ecuador pilot import
4. 20 creator eval set
5. First outreach campaign
6. Scoring adjustment memo
7. v0.2 decision memo

Acceptance:

1. Low/Medium Risk source metadata exists for all pilot candidates.
2. 360+ candidates have AI detail analysis.
3. 90+ candidates have approved multimodal analysis where data is available.
4. 60+ candidates are operator-approved.
5. 55+ first outreach actions are prepared or sent manually.

## 4. Engineering Guardrails

1. Do not hardcode model IDs in business logic. Use `ai_model_config`.
2. Do not let AI directly set final score. Use deterministic scoring service.
3. Do not create High Risk analysis jobs in v0.1.
4. Do not store high-volume scraped comment datasets.
5. Do not automate TikTok DM sending.
6. Do not generate DM for do-not-contact creators.
7. Do not approve DM before claims check.
8. Do not expose contact info to viewer role.

## 5. Test Cases to Create First

### 5.1 Source Risk Tests

1. Creating analysis job with `low` succeeds.
2. Creating analysis job with `low_medium` requires approval.
3. Creating analysis job with `medium` requires approval.
4. Creating analysis job with `high` fails.
5. Creating video/comment import with `high` fails.

### 5.2 Outreach Gate Tests

1. do-not-contact creator cannot receive DM draft.
2. removal-request creator cannot receive outreach.
3. High Risk creator cannot receive outreach.
4. `dm_sent` fails if claims check is not passed.
5. `dm_sent` fails if do-not-contact check timestamp is missing.

### 5.3 AI Output Tests

1. Profile analysis validates against schema.
2. Comment analysis validates against schema.
3. Multimodal analysis validates against schema.
4. DM generation returns at least two variants.
5. Claims check flags medical/guaranteed claims.
6. Final review includes evidence and confidence.

### 5.4 Scoring Tests

1. Base Score weights sum to 1.0.
2. Risk Penalty is 0-30.
3. Final Score is clamped to 0-100.
4. Risk Penalty 20+ becomes Avoid.
5. Final Score 70+ enters Review Queue.

## 6. Remaining Business Inputs

브리웰에서 제공해야 하는 값:

1. 실제 브랜드/제품/SKU 목록
2. 제품별 가격, 샘플 제공 가능 수량
3. 국가별 배송 가능 여부와 배송 기간
4. 제품별 랜딩 URL 또는 판매 채널
5. 고정비/커미션/쿠폰 정책
6. 제품별 허용/금지 마케팅 표현
7. 캠페인별 AI 분석 예산 상한
8. 운영자별 역할과 권한

## 7. Immediate Next Build Task

다음 실제 개발 작업은 아래 순서가 가장 좋다.

1. `briwell_database_schema_v0.sql`을 migration으로 변환
2. `briwell_seed_data_v0.sql` 적용
3. `briwell_keyword_seed_v0.csv` import script 작성
4. `briwell_creator_import_template.csv` import validation 구현
5. FastAPI 기본 프로젝트 생성
6. `/health`, `/products`, `/keywords`, `/creators/import`, `/creators` 구현
7. source risk validation middleware 구현

## 8. QA Review Log

### Pass 1: Completeness

Verified:

1. PRD, product strategy, keywords, scoring, dashboard, DB, API, prompts are linked into one build package.
2. Sprint plan maps to concrete deliverables and acceptance criteria.
3. Pilot operations playbook and import templates are included.

### Pass 2: Risk Consistency

Verified:

1. Low/Medium Risk only principle is repeated in build guardrails.
2. High Risk is not part of v0.1 execution path.
3. Outreach and claims checks have explicit tests.

### Pass 3: Development Readiness

Verified:

1. First build task is clear.
2. Test cases are defined before implementation.
3. Business inputs are separated from engineering blockers.
