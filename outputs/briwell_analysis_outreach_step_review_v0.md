# Briwell Analysis Jobs and Outreach Step Review v0

작성일: 2026-06-17

상태: Analysis Job API + DM Draft API 구현 및 검증 완료

## 1. 이번 단계 구현 범위

이번 단계는 실제 외부 AI 호출 전에 반드시 고정되어야 하는 운영 계약을 구현했다.

구현된 범위:

1. `GET /analysis-jobs`
2. `POST /analysis-jobs`
3. `POST /outreach/{creator_id}/generate-dm`
4. Analysis Job repository
5. Outreach repository
6. Creator detail lookup repository
7. Deterministic DM draft generator
8. API smoke tests

## 2. 핵심 정책

### 2.1 Analysis Job

분석 작업 생성 규칙:

1. `low` source risk는 `admin`, `operator`가 생성 가능
2. `low_medium`, `medium`은 `admin`만 생성 가능
3. `high`, `not_allowed`는 생성 불가
4. DB가 비활성화된 로컬 환경에서는 `validated_not_persisted`로 검증만 수행
5. DB가 활성화되면 `analysis_job` 테이블에 저장

### 2.2 DM Draft

DM 생성 규칙:

1. `high`, `not_allowed` creator는 DM 생성 불가
2. `do_not_contact=true` creator는 DM 생성 불가
3. `removal_requested_at`이 있는 creator는 DM 생성 불가
4. 최소 2개 Spanish DM draft variant 반환
5. 모든 draft는 `claims_check_status=needs_review`
6. 발송 자동화는 구현하지 않음

## 3. 구현 파일

Backend:

1. `app/routers/analysis_jobs.py`
2. `app/routers/outreach.py`
3. `app/repositories/analysis_jobs.py`
4. `app/repositories/outreach.py`
5. `app/ai/dm.py`
6. `app/repositories/creators.py`
7. `app/main.py`

Tests:

1. `tests/test_api_smoke.py`

Docs:

1. `README.md`

## 4. 3-Pass Review

### Pass 1: PRD/API Alignment

확인:

1. PRD와 API Spec의 `POST /analysis-jobs` 요구사항을 반영했다.
2. PRD와 API Spec의 `POST /outreach/{creator_id}/generate-dm` 요구사항을 반영했다.
3. DM은 초안 생성까지만 자동화하고, 발송은 자동화하지 않았다.
4. claims check 전 상태를 `needs_review`로 유지했다.

보완:

1. 실제 AI provider 호출은 아직 연결하지 않았다.
2. 실제 DB가 없는 환경에서는 persistence 대신 contract validation을 우선했다.

판정: 통과

### Pass 2: Policy and Safety

확인:

1. High Risk와 Not Allowed analysis job 생성이 차단된다.
2. Operator는 Medium Risk job을 생성할 수 없다.
3. do-not-contact creator는 DM draft를 받을 수 없다.
4. High Risk creator는 DM draft를 받을 수 없다.
5. DM 문안은 의료 효능, 매출, 조회수, 수익 보장을 포함하지 않는다.

보완:

1. 실제 provider 연결 시 claims check를 별도 AI job으로 실행해야 한다.
2. 운영자가 수정한 DM은 재검수 루프가 필요하다.

판정: 통과

### Pass 3: Engineering Readiness

확인:

1. 라우터, repository, AI draft generator가 분리되어 있다.
2. DB 비활성 환경에서도 테스트가 가능하다.
3. DB 활성 환경에서는 기존 schema에 맞춰 저장할 수 있다.
4. 새 API smoke tests가 추가되었다.
5. README가 새 endpoints를 반영한다.

보완:

1. 실제 PostgreSQL 컨테이너 또는 managed DB에서 integration test를 한 번 더 실행해야 한다.
2. Gemini adapter와 cost logging은 다음 단계에서 구현해야 한다.

판정: 통과

## 5. Validation Result

최신 테스트 기준:

```text
26 passed, 2 skipped
```

Skipped tests:

1. DB connection test
2. Required tables integration test

두 테스트는 로컬 PostgreSQL이 실행 중일 때 `RUN_DB_TESTS=1`로 활성화된다.

## 6. 다음 단계 추천

다음 구현 순서:

1. Video import API
2. Comment sample import API
3. Creator analysis result schema validation
4. Gemini text adapter
5. Gemini multimodal adapter
6. AI invocation log persistence
7. Claims check job execution
