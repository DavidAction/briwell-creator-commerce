# Briwell Dashboard Frontend Scaffold Review v0

작성일: 2026-06-17

## 이번 단계 결과

운영 대시보드를 정적 프론트엔드 앱으로 분리했습니다.

위치:

```text
work/briwell_dashboard_app
```

주요 파일:

```text
index.html
styles.css
api-client.js
app.js
vercel.json
package.json
tests/smoke.mjs
README.md
```

## 구현된 화면

1. Command: API health, readiness, 후보 요약, review queue
2. Discovery: MX/PE/EC 국가별 discovery plan 생성
3. Candidates: 후보 목록, 국가/점수/검색 필터, 상세 패널
4. Campaign: 캠페인 생성, outreach draft 준비
5. DM Review: claims check, 승인/반려, manual send gate
6. Tracking: 성과 snapshot 저장
7. Settlement: 계약 조건 저장, payout queue

## API 연결 방식

기본 API:

```text
http://127.0.0.1:8030
```

개발 모드에서는 아래 헤더를 사용합니다.

```text
X-User-Role
X-User-Email
```

운영 모드에서는 Supabase Auth JWT를 붙이는 구조로 확장합니다.

```text
Authorization: Bearer <supabase-jwt>
```

## 백엔드 보완

대시보드가 브라우저에서 API를 호출할 수 있도록 FastAPI CORS 설정을 추가했습니다.

추가된 환경값:

```text
CORS_ALLOWED_ORIGINS
```

운영 readiness는 아래 위험값을 차단합니다.

```text
CORS_ALLOWED_ORIGINS_MISSING
CORS_ALLOWED_ORIGINS_PLACEHOLDER
CORS_LOCALHOST_ORIGIN_NOT_ALLOWED_IN_PRODUCTION
```

## 3회 객관 검수

### 1차 검수: 업무 완성도

판정: MVP 운영 화면으로 적합

확인:

- 후보 검토, 캠페인 생성, DM 검수, 성과, 정산까지 한 화면 체계로 연결됨
- API가 꺼져 있어도 mock mode로 업무 흐름을 눈으로 검토 가능
- API가 켜져 있으면 실제 FastAPI endpoint를 호출하도록 구성됨

보완 필요:

- Supabase Auth 로그인 UI는 아직 미구현
- 실제 DB 데이터가 충분히 쌓인 후 테이블 컬럼과 필터를 더 조정해야 함

### 2차 검수: 안전성/컴플라이언스

판정: 핵심 안전장치 유지

확인:

- 자동 DM 발송 버튼이나 auto-send hook 없음
- claims check와 human approval gate가 분리됨
- source policy와 Low/Medium risk 원칙이 화면에 노출됨
- CORS 운영 설정 placeholder/localhost를 readiness에서 차단함

보완 필요:

- 실제 로그인 후 role claim 기반 화면 권한 제어 필요
- 승인/반려 이력 audit log UI 필요

### 3차 검수: 외주/AI 개발 인수인계

판정: 이어받기 쉬움

확인:

- 의존성 없는 HTML/CSS/JS 구조라 외주 개발자가 빠르게 읽을 수 있음
- `api-client.js`에 백엔드 endpoint 연결이 모여 있음
- `tests/smoke.mjs`로 핵심 파일/화면/endpoint 존재 여부 검증 가능
- `vercel.json`으로 정적 배포 준비 완료

보완 필요:

- 다음 단계에서 React/Next.js 전환 또는 이 정적 앱을 그대로 확장할지 결정 필요
- OpenAPI 기반 TypeScript type generation은 아직 미구현

## 검증 결과

프론트엔드:

```text
dashboard smoke passed
```

백엔드 부분 검증:

```text
75 passed
```

백엔드 전체 검증:

```text
142 passed, 5 skipped
```

컴파일:

```text
compileall passed
```

Production readiness 템플릿 차단:

```text
status: blocked
blockers:
- DATABASE_URL_PLACEHOLDER
- OIDC_CONFIGURATION_MISSING
- OIDC_JWKS_CONFIGURATION_MISSING
- CORS_ALLOWED_ORIGINS_MISSING
- CORS_ALLOWED_ORIGINS_PLACEHOLDER
- BACKUP_RESTORE_TEST_REQUIRED
- GEMINI_API_KEY_MISSING
```

## 다음 추천 단계

1. Supabase Auth 로그인 UI 연결
2. OpenAPI 기반 API client/type generation
3. 실제 campaign/candidate DB 데이터로 화면 E2E 검증
4. Sentry SDK 연동
5. AI 비용/사용량 budget dashboard 추가
