# Briwell AI Invocation Log and Worker Step Review v0

작성일: 2026-06-17

상태: AI invocation log persistence scaffold + analysis job dry-run worker 구현 및 검증 완료

## 1. 이번 단계 구현 범위

이번 단계는 AI 호출을 추적하고, queued analysis job을 실행하는 worker의 최소 골격을 구현했다.

구현된 범위:

1. AI invocation log repository
2. AI invocation log admin list API
3. Analysis job status update repository
4. Analysis runner worker
5. Dry-run analysis execution API
6. CLI worker script
7. Token count estimate
8. Invocation status mapping
9. Tests for worker, log preview, role checks, and API routes

## 2. 핵심 정책

### 2.1 Invocation Log

AI 호출 로그 규칙:

1. `ok` result는 `success`
2. source risk 차단 result는 `skipped`
3. provider/schema error result는 `failed`
4. prompt version, target entity, estimated token count, latency, status를 기록
5. DB 비활성 환경에서는 log preview만 반환
6. DB 활성 환경에서는 `ai_invocation_log` 테이블에 저장

### 2.2 Analysis Worker

Worker 규칙:

1. 현재 worker는 dry-run Gemini adapter만 사용
2. 외부 provider 비용은 발생하지 않음
3. High Risk와 Not Allowed input은 provider 호출 전 차단
4. DB가 켜져 있고 `analysis_job_id`가 있으면 job status를 running/completed/failed로 갱신
5. CLI와 API route 모두 같은 `run_analysis()` 서비스를 사용

## 3. 구현 파일

Backend:

1. `app/repositories/ai_invocation_logs.py`
2. `app/repositories/analysis_jobs.py`
3. `app/workers/analysis_runner.py`
4. `app/routers/ai_invocation_logs.py`
5. `app/routers/analysis_jobs.py`
6. `app/main.py`

Scripts:

1. `scripts/run_analysis_worker.py`

Tests:

1. `tests/test_analysis_runner.py`
2. `tests/test_api_smoke.py`

Docs:

1. `README.md`

## 4. 3-Pass Review

### Pass 1: PRD/API Alignment

확인:

1. PRD의 AI invocation cost/log tracking 요구를 반영했다.
2. API Spec의 `GET /ai-invocation-logs`를 구현했다.
3. Analysis job 실행은 자동 대량 실행이 아니라 one-request dry-run worker로 제한했다.
4. AI provider 호출 전 source risk policy를 유지한다.

판정: 통과

### Pass 2: Policy and Cost Control

확인:

1. Dry-run worker라 API 비용이 발생하지 않는다.
2. High Risk와 Not Allowed는 `skipped`로 기록된다.
3. Operator는 log list를 볼 수 없고 admin만 조회 가능하다.
4. Token count는 비용 예측용 estimate로 분리했다.
5. Live provider call은 이번 worker에서 사용하지 않는다.

판정: 통과

### Pass 3: Engineering Readiness

확인:

1. Router, repository, worker service가 분리되어 있다.
2. DB 비활성 환경에서도 worker contract test가 가능하다.
3. DB 활성 환경에서는 `ai_invocation_log`와 `analysis_job` 상태 갱신을 수행할 수 있다.
4. CLI script가 같은 worker service를 사용한다.
5. Test suite가 worker result, log payload, role checks, HTTP route를 커버한다.

보완 필요:

1. 실제 PostgreSQL 환경에서 persistence path integration test 필요
2. 실제 Gemini response fixture 기반 worker test 필요
3. 여러 target을 처리하는 batch worker 필요
4. Creator analysis persistence와 deterministic scoring calculator 필요

판정: 통과

## 5. Validation Result

최신 테스트 기준:

```text
52 passed, 2 skipped
```

Skipped tests:

1. DB connection test
2. Required tables integration test

두 테스트는 로컬 PostgreSQL이 실행 중일 때 `RUN_DB_TESTS=1`로 활성화된다.

## 6. 다음 단계 추천

다음 구현 순서:

1. Creator score deterministic calculator
2. Creator analysis persistence
3. Analysis worker batch execution
4. Claims check job execution
5. Campaign candidate ranking API
