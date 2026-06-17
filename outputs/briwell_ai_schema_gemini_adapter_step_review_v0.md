# Briwell AI Schema and Gemini Adapter Step Review v0

작성일: 2026-06-17

상태: AI output schema validation + Gemini text adapter scaffold 구현 및 검증 완료

## 1. 이번 단계 구현 범위

이번 단계는 실제 Gemini API를 운영에 연결하기 전에 반드시 필요한 AI 계약 계층을 구현했다.

구현된 범위:

1. Profile analysis output schema
2. Comment analysis output schema
3. Final creator review output schema
4. Creator score output schema
5. AI output validation helper
6. Gemini text adapter scaffold
7. Gemini dry-run deterministic output
8. `/ai/validate-output` API
9. `/ai/dry-run` API
10. Tests for schema validation, source-risk rejection, dry-run adapter, and API routes

## 2. 핵심 정책

### 2.1 Schema Validation

모든 AI output은 저장 전 task별 schema를 통과해야 한다.

현재 지원 task:

1. `profile_analysis`
2. `comment_analysis`
3. `final_review`
4. `creator_score`

검증 규칙:

1. 필수 필드 누락 차단
2. 허용 enum 외 값 차단
3. confidence는 0-1 범위
4. 점수는 0-100 범위
5. risk penalty는 0-30 범위
6. evidence는 최소 1개 이상
7. `review_required=true`이면 `review_required_reason` 필수
8. contact available이면 contact channel 필수
9. comment sentiment ratio 합산은 1 이하

### 2.2 Gemini Adapter

Gemini adapter 규칙:

1. 기본값은 dry-run mode
2. dry-run mode는 외부 API 호출 없이 deterministic JSON을 생성
3. live call은 `ALLOW_LIVE_PROVIDER_CALLS=true`일 때만 허용
4. live call은 `GEMINI_API_KEY`가 없으면 실패
5. High Risk와 Not Allowed source risk는 provider call 전에 차단
6. provider output도 schema validation을 통과해야 `ok` result가 된다

## 3. 구현 파일

Backend:

1. `app/schemas/analysis.py`
2. `app/ai/schema_validation.py`
3. `app/ai/gemini.py`
4. `app/routers/ai.py`
5. `app/core/config.py`
6. `app/main.py`

Tests:

1. `tests/test_analysis_schemas.py`
2. `tests/test_ai_adapters.py`
3. `tests/test_api_smoke.py`

Docs:

1. `README.md`
2. `.env.example`

## 4. 3-Pass Review

### Pass 1: PRD and Prompt Alignment

확인:

1. Profile analysis schema가 AI prompt v0의 output fields를 반영한다.
2. Comment analysis schema가 comment prompt v0의 output fields를 반영한다.
3. Final review schema가 final creator review prompt v0의 output fields를 반영한다.
4. Creator score schema는 DB의 `creator_analysis` 필드와 연결 가능하다.
5. AI가 final score를 직접 임의 생성하지 않도록 score schema를 별도 분리했다.

판정: 통과

### Pass 2: Policy and Cost Control

확인:

1. High Risk와 Not Allowed source risk는 Gemini 호출 전에 차단된다.
2. 기본 dry-run mode라 개발 중 API 비용이 발생하지 않는다.
3. live provider call은 명시적 환경변수 없이는 실행되지 않는다.
4. provider key가 없으면 live call이 실패 상태로 반환된다.
5. schema validation 실패 시 저장 가능한 result가 되지 않는다.

판정: 통과

### Pass 3: Engineering Readiness

확인:

1. Adapter interface는 기존 `AIAdapter.run()` 계약을 유지한다.
2. Gemini scaffold는 `AnalysisResult`로 표준화된 결과를 반환한다.
3. API route에서 output validation을 직접 호출할 수 있다.
4. Dry-run route로 frontend/worker integration을 먼저 진행할 수 있다.
5. 테스트가 schema, adapter, HTTP route를 모두 커버한다.

보완 필요:

1. 실제 Gemini API response fixture 기반 테스트 추가
2. AI invocation log persistence 구현
3. Analysis job worker와 adapter 연결
4. 실제 PostgreSQL 환경에서 DB-backed analysis result 저장 테스트

판정: 통과

## 5. Validation Result

최신 테스트 기준:

```text
45 passed, 2 skipped
```

Skipped tests:

1. DB connection test
2. Required tables integration test

두 테스트는 로컬 PostgreSQL이 실행 중일 때 `RUN_DB_TESTS=1`로 활성화된다.

## 6. 다음 단계 추천

다음 구현 순서:

1. AI invocation log repository and API
2. Analysis job worker scaffold
3. Creator score deterministic calculator
4. Creator analysis persistence
5. Claims check job execution
