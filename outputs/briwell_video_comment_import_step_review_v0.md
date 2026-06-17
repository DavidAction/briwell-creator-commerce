# Briwell Video and Comment Import Step Review v0

작성일: 2026-06-17

상태: Video Import API + Comment Sample Import API 구현 및 검증 완료

## 1. 이번 단계 구현 범위

이번 단계는 AI 분석 파이프라인의 입력 데이터가 되는 영상 메타데이터와 댓글 샘플을 안전하게 수집, 검증, 저장할 수 있는 API를 구현했다.

구현된 범위:

1. `GET /videos`
2. `POST /videos/import`
3. `GET /comments`
4. `POST /comments/import`
5. Video repository
6. Comment sample repository
7. Collection source type policy
8. API smoke tests
9. README endpoint 문서 갱신

## 2. 핵심 정책

### 2.1 Video Import

영상 import 규칙:

1. `low`, `low_medium`, `medium` source risk만 허용
2. `high`, `not_allowed` source risk는 차단
3. `public_page_scrape`, `bulk_scrape`, `browser_automation`, `captcha_bypass`, `login_bypass` 등 자동 스크래핑성 source type 차단
4. 요청당 최대 50개 video item 허용
5. 조회수, 좋아요, 댓글 수, 공유 수, 저장 수, 영상 길이는 음수 불가
6. DB 비활성 환경에서는 `validated_not_persisted`로 contract validation만 수행

### 2.2 Comment Sample Import

댓글 샘플 import 규칙:

1. `low`, `low_medium`, `medium` source risk만 허용
2. 요청당 최대 50개 comment sample 허용
3. `sample_method`는 `manual`, `official_api`, `approved_provider`, `creator_provided`만 허용
4. `contains_sensitive_data=true`인 댓글 샘플은 차단
5. 댓글은 전체 수집 데이터가 아니라 분석용 최소 샘플로 취급

## 3. 구현 파일

Backend:

1. `app/routers/videos.py`
2. `app/routers/comments.py`
3. `app/repositories/videos.py`
4. `app/repositories/comments.py`
5. `app/core/policy.py`
6. `app/main.py`

Tests:

1. `tests/test_api_smoke.py`
2. `tests/test_policy.py`
3. `tests/test_db_integration.py`

Docs:

1. `README.md`

## 4. 3-Pass Review

### Pass 1: PRD/API Alignment

확인:

1. PRD와 API Spec의 `POST /videos/import` 요구사항을 반영했다.
2. PRD와 API Spec의 `POST /comments/import` 요구사항을 반영했다.
3. 영상과 댓글 모두 Low/Medium Risk 소스만 허용한다.
4. 댓글은 고용량 전체 스크래핑이 아니라 최소 샘플만 허용하도록 batch cap을 두었다.

판정: 통과

### Pass 2: Policy and Safety

확인:

1. High Risk와 Not Allowed 데이터가 차단된다.
2. 자동 스크래핑성 source type이 차단된다.
3. 민감정보가 포함된 댓글 샘플이 차단된다.
4. 댓글 sample method가 제한되어 무분별한 출처 입력을 줄였다.
5. DM/아웃리치로 바로 연결되지 않고 AI 분석 전 입력 데이터로만 저장된다.

판정: 통과

### Pass 3: Engineering Readiness

확인:

1. Router와 repository가 분리되어 있다.
2. DB 비활성 환경에서도 API contract tests가 실행된다.
3. DB 활성 환경에서는 기존 `video`, `comment_sample` 테이블에 저장할 수 있다.
4. 새 API endpoints가 `app/main.py`에 연결되었다.
5. README와 DB integration expected table list가 갱신되었다.

보완 필요:

1. 실제 PostgreSQL 환경에서 `RUN_DB_TESTS=1` integration test 필요
2. 다음 단계에서 video/comment 데이터를 사용하는 Gemini analysis adapter 필요
3. AI invocation log와 analysis job worker 연결 필요

판정: 통과

## 5. Validation Result

최신 테스트 기준:

```text
34 passed, 2 skipped
```

Skipped tests:

1. DB connection test
2. Required tables integration test

두 테스트는 로컬 PostgreSQL이 실행 중일 때 `RUN_DB_TESTS=1`로 활성화된다.

## 6. 다음 단계 추천

다음 구현 순서:

1. Creator analysis result schema validation
2. Gemini text adapter scaffold
3. Gemini multimodal adapter scaffold
4. AI invocation log persistence
5. Claims check job execution
