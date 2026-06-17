# Briwell Creator Scoring and Persistence Step Review v0

작성일: 2026-06-17

상태: Deterministic creator score calculator + creator analysis persistence scaffold 구현 및 검증 완료

## 1. 이번 단계 구현 범위

이번 단계는 AI가 추천 근거와 component signal을 제공하더라도 최종 점수는 시스템이 계산하도록 scoring layer를 구현했다.

구현된 범위:

1. Deterministic creator score calculator
2. v0.1 scoring weight formula
3. Segment classification rule
4. Review-required reason rule
5. Creator analysis repository
6. `GET /creators/{creator_id}/analysis`
7. `POST /creators/{creator_id}/score`
8. Tests for scoring math, final score rejection, schema validation, and API routes

## 2. 핵심 정책

### 2.1 Scoring Formula

시스템 계산 공식:

```text
Base Score =
Beauty Fit * 0.25
+ Engagement Quality * 0.20
+ Audience Locality * 0.15
+ Commerce Intent * 0.15
+ Content Quality * 0.10
+ Collaboration Probability * 0.10
+ Cost Efficiency * 0.05

Final Score = clamp(Base Score - Risk Penalty, 0, 100)
```

규칙:

1. API input은 `final_score`를 허용하지 않는다.
2. `final_score`는 시스템이 계산한다.
3. `risk_penalty`는 0-30 범위다.
4. `final_score`는 0-100으로 clamp된다.
5. 계산 결과는 `CreatorAnalysisScoreOutput` schema로 검증된다.

### 2.2 Segment Classification

현재 deterministic segment:

1. `avoid`
2. `viral_micro`
3. `commerce_creator`
4. `beauty_educator`
5. `ugc_creator`
6. `brand_builder`
7. `review_creator`

위험 신호가 높거나 final score가 낮으면 `avoid`로 분류된다.

### 2.3 Persistence

DB mode:

1. `creator_analysis`에 upsert
2. `creator_id + analysis_version` 기준으로 중복 갱신
3. 분석 히스토리는 `GET /creators/{creator_id}/analysis`로 조회

Local mode:

1. DB 저장 없이 `validated_not_persisted`
2. 계산 결과와 schema validation만 수행

## 3. 구현 파일

Backend:

1. `app/scoring/creator_score.py`
2. `app/repositories/creator_analyses.py`
3. `app/routers/creators.py`
4. `app/schemas/analysis.py`

Tests:

1. `tests/test_creator_scoring.py`
2. `tests/test_analysis_schemas.py`
3. `tests/test_api_smoke.py`
4. `tests/test_db_integration.py`

Docs:

1. `README.md`

## 4. 3-Pass Review

### Pass 1: PRD/API Alignment

확인:

1. PRD의 "AI가 final score를 직접 만들지 않는다" 요구를 반영했다.
2. API Spec의 `POST /creators/{creator_id}/score`를 구현했다.
3. API Spec의 `GET /creators/{creator_id}/analysis`를 구현했다.
4. Seed data의 v0.1 scoring weights와 동일한 가중치를 사용한다.

판정: 통과

### Pass 2: Safety and Quality

확인:

1. `final_score` 직접 입력이 차단된다.
2. 점수 component 범위는 0-100으로 제한된다.
3. risk penalty 범위는 0-30으로 제한된다.
4. low confidence는 review reason을 생성한다.
5. high risk score 또는 high risk penalty는 `avoid` segment로 분류된다.

판정: 통과

### Pass 3: Engineering Readiness

확인:

1. Scoring service와 repository가 분리되어 있다.
2. DB 비활성 환경에서도 scoring contract test가 가능하다.
3. DB 활성 환경에서는 `creator_analysis` persistence path가 준비되어 있다.
4. Creator score output schema와 DB columns가 매핑된다.
5. Test suite가 math, schema, API route를 커버한다.

보완 필요:

1. 실제 PostgreSQL 환경에서 upsert integration test 필요
2. Analysis worker 결과와 scoring API 자동 연결 필요
3. Campaign candidate ranking API 필요
4. Operator feedback 기반 score adjustment flow 필요

판정: 통과

## 5. Validation Result

최신 테스트 기준:

```text
62 passed, 2 skipped
```

Skipped tests:

1. DB connection test
2. Required tables integration test

두 테스트는 로컬 PostgreSQL이 실행 중일 때 `RUN_DB_TESTS=1`로 활성화된다.

## 6. 다음 단계 추천

다음 구현 순서:

1. Campaign candidate ranking API
2. Analysis worker to scoring handoff
3. Claims check job execution
4. Operator feedback API
5. Basic frontend dashboard scaffold
