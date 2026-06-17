# Briwell Quality Upgrade Audit v0

작성일: 2026-06-17

## 객관 평가

현재 Briwell MVP는 단순 와이어프레임이 아니라, 정책 게이트와 테스트가 붙은 운영 콘솔형 MVP 단계다. 다만 외부 운영자가 보기에는 아직 `local preview`, 실제 provider 데이터, 운영 인증, 실시간 DB 환경이 구분되어 있어 "내부 검증용 고급 MVP"로 보는 것이 정확하다.

평가:

1. Product workflow: 8/10
2. Compliance and safety guardrails: 8/10
3. Backend API structure: 8/10
4. Dashboard executive polish: 7.5/10
5. Production readiness: 5.5/10
6. Real data readiness: 5/10

## 이번 감사에서 보완한 항목

1. Collection source type을 blocklist 중심에서 allowlist 중심으로 강화했다.
2. 승인 source type은 `manual`, `official_api`, `approved_provider`, `creator_provided` 네 가지로 고정했다.
3. Discovery source-policy와 discovery planner가 같은 정책 상수를 사용하도록 정리했다.
4. 대시보드의 개발자스러운 `Mock Mode` 표현을 `Preview Mode`와 `local_preview`로 교체했다.
5. `example.com` 샘플 URL을 채널/게시물 맥락에 맞는 TikTok/Instagram 형태로 교체했다.
6. Operations Pipeline fallback 결과에 `api_status`와 `api_error`를 남겨 API 실패를 숨기지 않게 했다.
7. Smoke test에 `Mock Mode`, `example.com` 재유입 방지 검증을 추가했다.

## 클래스를 더 올리는 다음 핵심 방안

1. Live Data Intake
   - 승인 provider export, 수동 CSV, creator-provided 자료를 같은 intake contract로 표준화한다.
   - CSV 템플릿과 샘플 파일을 제공하고, 업로드 전 컬럼 검증 리포트를 생성한다.

2. AI Evaluation Harness
   - Gemini 실제 응답 fixture를 저장해 dry-run 결과와 live 결과를 비교한다.
   - 점수 일관성, 제품군 매칭 정확도, 브랜드 세이프티 false positive/false negative를 추적한다.

3. Production Auth
   - 대시보드 localStorage 기반 bearer token 저장을 Supabase Auth 세션 흐름으로 교체한다.
   - 운영자 역할별 화면 접근과 API 권한을 실제 계정 기준으로 묶는다.

4. Real PostgreSQL E2E
   - managed PostgreSQL 환경에서 import -> recent 20 screen -> match -> outreach -> performance rollup 전체 E2E를 통과시킨다.
   - 현재 DB 테스트는 충분히 좋은 기반이지만, 전체 업무 플로우 E2E는 아직 강화 여지가 있다.

5. Dashboard Executive Layer
   - API 상태보다 캠페인 의사결정 지표를 더 전면화한다.
   - country/product별 pipeline forecast, budget allocation, creator stage aging, pending approval SLA를 추가한다.

6. Media and Multimodal Readiness
   - 영상 프레임/스크립트/자막/제품 노출을 provider 또는 creator-provided asset 기준으로 ingest한다.
   - unauthorized scraping 없이도 분석 가능한 asset evidence chain을 만든다.

7. Operations Observability
   - API error, AI cost, queue failure, import rejection reason, payout blocker를 운영 로그로 모은다.
   - 대시보드에 "Data Quality", "Compliance", "AI Cost", "Campaign Ops" 네 개 운영 상태를 분리 표시한다.

## 다음 단계 추천

가장 효과가 큰 다음 작업은 `Live Data Intake v1`이다. 이유는 실제 인플루언서 데이터를 넣고 검수하는 순간부터 현재 콘솔이 데모가 아니라 운영 도구로 전환되기 때문이다.

권장 순서:

1. CSV 템플릿과 sample 파일 생성
2. 업로드 validation report 고도화
3. 실제 creator/profile/recent-post import E2E DB 테스트
4. Gemini live fixture 기반 recent 20 screen 검증
5. 대시보드에 Data Quality Scorecard 추가
