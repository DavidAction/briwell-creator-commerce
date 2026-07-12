# Briwell MVP — 프로젝트 마스터 브리핑 (한국어)

> **이 문서의 목적**: claude.ai(또는 다른 AI 챗)에 이 파일 하나만 올리면 Briwell 프로젝트의
> 현재 상태·향후 목표·비용·사용 AI 모델/API를 정확히 파악할 수 있도록 만든 단일 요약본입니다.
> 최종 검증일: 2026-06-27 (Claude Code가 소스 코드를 직접 읽어 작성·교차검증).
> 코드 기준 출처는 `파일:라인`으로 표기. 추정·미검증 항목은 ⚠️로 명시.

---

## 0. 한 줄 요약

한국 화장품(K-beauty)을 **라틴아메리카(멕시코·페루·에콰도르)** 에 파는 Briwell의,
**뷰티 크리에이터 발굴 → 평가 → 컴플라이언스 검수 → 아웃리치 → 성과·정산**까지를 다루는
**운영 콘솔형 MVP**. 백엔드(FastAPI) + 정적 대시보드 + 포터블 PostgreSQL로 구성. 로컬에서 동작 검증됨.

**현재 성격**: "데모"가 아니라 **정책 게이트와 테스트가 붙은 내부 운영용 고급 MVP**. 단, 실제 운영 도구가
되려면 (1) 실데이터 유입 (2) AI 분석 체인 실제 연결 (3) 운영 인증·보안이 남아 있음.

---

## 0.1 최근 적용된 수정 (2026-06-27, Claude Code)

코드 감사에서 나온 격차 중 다음을 구현·검증했습니다 (테스트 176통과/7스킵 유지):

1. **① full-analysis 체인 실배선** — 오케스트레이션이 recent-20 통과 크리에이터에 대해
   프로필 분석(+댓글 분석) → 결정론적 스코어 핸드오프를 **실제 실행**. 이제 `final_score`가
   **시스템 산출값**(operator 입력이 아님). 검증: operator가 99(viral_micro)로 부풀린 점수를
   시스템이 64.49(review_creator)로 정정. `campaign_match.items[].score_source = "system_analysis"`.
   (multimodal·final_review는 자산/운영자 게이트 후속 단계로 유지)
2. **④ Gemini 모델 ID 수정** — 실 ListModels API 대조로 `gemini-3-flash`(미존재)를
   `gemini-3-flash-preview`로 교정(`dm_generation`·`multimodal_default`). 나머지 ID는 유효 확인.
3. **⑥ DmVariant 폴백 수정** — DM 생성기가 enum 4값(soft_intro·product_review·ugc_collaboration·
   commerce_collaboration) 전부 생성. 미지원 variant가 조용히 1번으로 폴백되던 버그 해소.
4. **A TikTok 스크래퍼 정직 재분류 + 기본 OFF** — Apify 스크래핑 결과를 `approved_provider`로
   둔갑시키던 라벨을 정직한 `provider_scrape` source_type으로 변경(`policy.py` allowlist에 추가하여
   파이프라인은 정상 작동, 단 라이선스 provider와 구분). 로컬 `.env`의 TikTok 라이브를 dry-run/OFF로
   되돌림(코드 기본값은 이미 OFF). 법률/ToS 확인은 추후 → 필요 시 차선으로 전환.

남은 핵심: B''(DM은 여전히 템플릿 — 진짜 AI 개인화 생성은 후속),
C(보안: rate limit·전역 예외 핸들러·감사 로깅·OIDC).

## 0.0 제품 정의 확정 (2026-07-04 사용자 지시 — 이 문서 전체보다 우선)

**용도**: 자사(Briwell) 운영 효율화를 위한 **내부 도구**. 타사 판매용 SaaS 아님.
**단계**: 기본 MVP → 상용화(내부 프로덕션) 버전으로 격상.

**6대 뼈대 기능**:
| # | 기능 | 현재 상태 |
|---|---|---|
| 1 | 중남미 K-beauty 적합 인플루언서 **AI 자동 발굴** | 부분 구현(provider 계층·스크린 체인) |
| 2 | 화장품↔크리에이터 **AI 분석·매칭** | 구현(7차원 스코어·캠페인 매칭) |
| 3 | **AI 자동 컨택 + 계약 관리** | 부분(DM 생성만·수동발송). ⚠️ 아래 0.0.1 참고 — 공식 레일 자동화 전제(TikTok Shop) 보류됨 |
| 4 | **Shopify 어필리에이트 + 자동 정산** (크리에이터 커머스) | 미구현(정산 레코드만 존재). ⚠️ 0.0.1 반영 후 **유일한 커머스 엔진**으로 우선순위 상향 |
| 5 | **배송 추적** | 미구현 |
| 6 | **자사 브랜드·제품·재고 인벤토리 관리 + AI 재주문** | 미구현(products 라우터만 존재) |

**아웃리치 정책 재조정(원안, 0.0.1로 일부 수정됨)**: 자동화 금지 게이트는 "오프플랫폼 비공식 DM"에만 유지.
TikTok Shop Affiliate API·Shopify Collabs 등 **플랫폼이 공식 제공하는 초대/협업 레일 경유 자동화는 허용**(ToS 적합) — 단, 아래처럼 전제가 바뀜.

## 0.0.1 커머스 채널 전략 수정 (2026-07-05 사용자 확정 — 위 표·정책보다 우선)

**TikTok Shop 셀러 계정은 당분간 미운영**(승인 난이도가 높아 보류). 대신:
- **Shopify 자사몰**에서 실제 판매·정산이 발생. TikTok은 **콘텐츠 마케팅 + 링크/코드 유입 채널**로만 사용.
- **어트리뷰션**: 크리에이터별 **할인코드**(Shopify PriceRule API 자동 발급)가 1차, 바이오 링크 UTM 트래킹이 2차.
- **Shopify Collabs 비권장** — 신규 크리에이터 가입이 중단된 상태이고 Hyperwallet/USD 중심 지급이라 멕시코·페루·에콰도르 크리에이터 정산 마찰이 큼. 대신 자체 discount-code + append-only `commission_ledger` + 기존 `settlements` 모듈로 구축.
- **아웃리치 자동화 전제 취소**: TikTok Shop Affiliate Seller API의 Targeted Collaboration(일 1,000건 공식 허용)로 DM 인간승인 게이트를 대체하자던 이전 제안은 **TikTok Shop 계정이 없어 무효**. 대체할 공식 자동화 레일이 없으므로 **DM 발송 전 인간승인 게이트는 당분간 유지**. 자동화는 발송 이전 단계(발굴·평가·초안 작성)로 한정.
- 위 6대 기능 표의 pillar 3·4 상태·우선순위는 이 변경을 반영해 재평가 필요.

## 0.0.2 로드맵 A P0 완료 (2026-07-05, Claude Sonnet 5 워크플로우) — 테스트 267→289 통과/12 스킵

내부 API 보안·감사 인프라 4개 항목 구현 + 코드 리뷰에서 나온 6개 확정 결함 수정(커밋 `6e7c680`~`a8145db`, 총 7커밋):
1. **Rate limiting 실구현**(`app/core/rate_limit.py`) — sliding-window(60초) + burst bucket 이중 체크, 클라이언트 IP 키(자기신고 `X-User-Email` 헤더로 우회되던 최초 버전을 리뷰에서 발견·수정). `/health`는 예외.
2. **OIDC 강화**(`app/core/auth.py`) — JWKS 클라이언트 `lru_cache`로 재사용(매 요청 재조회 제거), **미인식 role → 403 거부로 변경**(기존 "조용히 viewer 강등" 격차 C'' 해소).
3. **Postgres 기반 잡큐 인프라**(`db/migrations/006_job_queue_and_audit_events.sql`, `app/repositories/jobs.py`, `app/workers/job_queue.py`) — `FOR UPDATE SKIP LOCKED` 클레임, 재시도/실패 처리. **현재 등록된 job_type은 `audit_event.persist` 1개뿐**(배관 증명용) — 오케스트레이션의 동기 분석 체인을 큐로 옮기는 작업은 의도적으로 후속 과제로 남김. `OUTBOX_WORKER_ENABLED`(기본 false) 명시적 옵트인.
4. **감사 로그 배선**(`app/repositories/audit_events.py`, `GET /ops/audit-log`) — 아웃리치 상태 전환(`app/routers/outreach.py:234-262`)에서 승인·claims·do-not-contact 기록을 append-only `audit_events`에 큐 경유로 기록. admin/operator만 조회 가능.
5. **리뷰에서 발견·수정된 추가 결함**: job queue 워커가 핸들러 예외 시 `conn.rollback()` 누락으로 poisoned transaction 발생 가능하던 버그, audit_events `list_events`의 limit 미검증(음수/0 가능), rate limiter `_clients` dict 무한 증가(lazy eviction 추가), 미사용 `audit_log`(마이그레이션 001) 테이블 제거(`007_drop_unused_audit_log.sql`).

**알려진 한계**(의도적 범위 제한): 잡큐는 아직 단일 job_type의 배관 증명 단계. 오케스트레이션 동기 체인의 비동기 전환은 후속. Rate limit은 in-process(멀티 인스턴스 미공유).

## 0.0.3 대시보드 UI 격상 + 아키텍처 객관 감사 (2026-07-05)

**UI 격상(커밋 `e5ee087`·`18699b9`·`3f804c0`, 스모크 통과·브라우저 검증)**: "경영 현황" 화면을 Linear/Stripe급으로 격상 — 디자인 토큰 전면 개편(색·타이포·8px 스페이싱·hairline elevation), KPI 카드 델타 배지+SVG 스파크라인, "파이프라인 GMV 추이" 히어로 영역차트, API주소·역할셀렉터를 상단바 → **슬라이드 설정 드로어**로 이동, **미리보기/라이브 데이터 상태 배너**. index.html에 `?v=` 캐시버스팅 추가(정적 배포 후 낡은 JS 방지). ⚠️ 나머지 7개 화면은 아직 옛 스타일 — 격상 대상.

**아키텍처 객관 감사(15건 확정, 적대검증 통과 — 응원 아닌 비판 리뷰)**. 최우선 fix_now(대부분 P1 Shopify 커머스와 직결):
- **#6 `revenue_usd`에 통화 컬럼 없음** → MXN/PEN/USD 혼재 시 정산 오보고(LATAM 근본 결함).
- **#5 `commission_ledger`가 환불·부분환불·다중 할인코드 주문에 취약**.
- **#7 할인코드-우선 어트리뷰션이 LATAM TikTok엔 부적합** → 링크/UTM 병행 필요.
- **#11 (프론트) 미리보기 모드가 실제 쓰기와 시각적으로 구분 안 됨** → 커머스/정산 툴에서 위험, 별도 최우선.
- 기타: #8 Shopify order 엔티티 없음, #9 실데이터 파일럿 너무 늦음+PII삭제/백업/관측성 누락, #15 스모크가 문자열 grep뿐.
defer(지금은 문제 아님): #1 full-analysis 동기 LLM 팬아웃(라이브 켜기 전 잡큐 이전), #2 psycopg 풀 없음(라우트가 sync def라 **이벤트루프 블록은 아님**·churn만), #14 vanilla app.js 확장성.

## 0.0.4 커머스 정합성 스키마 선반영 완료 (2026-07-06) — 테스트 323 통과/26 스킵

감사 fix_now #5/#6/#7/#8 해소. 마이그레이션 008 + `app/commerce/`(순수 로직) + `app/repositories/commerce.py` + `app/routers/commerce.py`, 커밋 `7e25731`~`e80b709`(5커밋):
1. **Shopify 주문/환불 미러(#8)** — `shop_order`·`order_refund`. 웹훅-형상 페이로드 수용(실 Shopify API 연동은 후속), `shopify_order_id`/`shopify_refund_id` UNIQUE + upsert로 중복 배달 멱등.
2. **통화-명시 돈 표현(#6)** — 금액 NUMERIC(14,2) + ISO 4217 통화(MXN/PEN/USD) + 기록시점 `fx_rate_usd`. USD는 GENERATED STORED 파생 컬럼(수기 입력 경로 제거). `campaign_performance_snapshot`에도 `revenue_amount`/`revenue_currency`/`fx_rate_usd` 보강 + 트리거로 `revenue_usd` 자동 파생(후방호환).
3. **append-only commission_ledger(#5)** — DB 트리거로 UPDATE/DELETE 차단, accrual/reversal/adjustment 3종, 부분환불 비례배분(누적식·라운딩 드리프트 방지), reversal의 원 accrual 초과 차단, 잔액은 SUM 도출(`creator_commission_balance` 뷰, mutable balance 컬럼 없음).
4. **이중 어트리뷰션(#7)** — 할인코드 1차 + UTM 링크 2차. 코드-UTM 충돌 시 `needs_review` + 운영자 resolve API(confirm=확정 전 환불 소급 상계 / reassign=순잔액 기준 상계+대상 크리에이터 실요율 / reject=기존 accrual 청산).
5. **품질 과정**: 적대 리뷰(Opus 4.8×2+Sonnet 5)가 11건(critical 5) 발견 — reassign 과다회수, 확정 전 환불 영구누락, reject 미청산, limit-50 선형탐색 요율 폴백, 비원자적 accrual 등 — 전부 수정. 이후 라이브 포터블 PG로 DB 통합테스트 14개 검증(초기 6건 실패는 테스트 단정문/픽스처 결함으로 판명·교정, 제약·제품코드는 옳았음).
⚠️ 사전 존재 버그 발견: `audit_events.record_event`/`jobs.enqueue_job`이 dict payload를 psycopg `Jsonb`로 미래핑(라이브 DB에서만 발현). commerce 라우터는 호출부에서 래핑으로 우회, 근본 수정은 별도 태스크.

## 0.0.5 미리보기/실쓰기 구분 안전장치 완료 (2026-07-06, 감사 #11) — 커밋 72e38f6~f7d5560

대시보드의 "쓰기 실패 시 조용히 로컬 미리보기 폴백" 패턴이 만들던 실쓰기/시뮬레이션 혼동 제거. 브라우저 3-상태 실검증 완료:
1. **중앙 쓰기 게이트** — api-client.js `request()`(모든 API의 유일 관문)에 비-GET 게이트. `BriwellApi.setWriteGate()`로 app.js가 등록. 취소 시 `error.cancelled=true` + `cancelled_by_user` payload로 로컬 폴백 오염 차단(각 핸들러의 상태 변형 사이드이펙트도 cancelled 분기).
2. **3-상태 표기** — 전역 배너/필: "라이브 모드 · 쓰기 작업이 실제 서버에 기록됩니다"(is-live) vs "미리보기 모드". 쓰기 버튼 11개에 LIVE/PREVIEW 배지, 순수-계산 버튼(claims-check)은 COMPUTE 배지. 결과 칩: persisted="✓ 실제 서버 DB에 기록됨" / validated_not_persisted="⚠ 검증만 됨 · DB 비활성이라 저장 안 됨" / local_preview="미리보기 · 서버에 반영 안 됨" / cancelled="취소됨 · 아무것도 기록되지 않음".
3. **라이브 쓰기 확인 모달** — METHOD+endpoint+apiBase 표시, ESC/포커스트랩/ARIA, "10분간 다시 묻지 않기"(sessionStorage, try/catch 가드). **fail-closed**: 첫 헬스체크 완료 전엔 무조건 모달. 운영 파이프라인(8스텝)은 시작 시 1회 확인 + 실행 한정 승인 토큰(finally 해제), 중간 취소 시 잔여 스텝 중단.
4. **적대 리뷰 4건 전부 수정** — 초기 로드 레이스(무확인 라이브 쓰기 창), 파이프라인 모달 7연발+취소 무시, sessionStorage 예외 시 가짜 미리보기 표기, COMPUTE/LIVE 배지 혼동. 스모크에 게이트 회귀 체크 추가.
→ Phase3(7개 화면 격상)는 이 패턴 위에서 진행. 신규 쓰기 UI는 data-write-action 태깅 필수.

## 0.0.6 잡큐 JSONB 근본 수정 (2026-07-07) — 테스트 328 통과/26 스킵

0.0.4에서 "근본 수정은 별도 태스크"로 미뤄둔 dict→JSONB 어댑테이션 버그 해소:
1. **`jobs.enqueue_job` Jsonb 래핑** — raw dict가 라이브 psycopg에서 "cannot adapt type 'dict'"로
   실패하던 근본 원인 수정(`app/repositories/jobs.py`). 라이브 DB에서 아웃리치 상태전환의 감사이벤트
   enqueue가 실패하던 경로 해소. 비-DB 회귀 테스트 추가(`tests/test_job_queue.py`).
2. **commerce 라우터 이중 래핑 회귀 수정** — f982966이 `record_event` 내부에 Jsonb 래핑을 넣을 때
   commerce 호출부 2곳(attribution decided/resolved)의 기존 우회 래핑을 제거하지 않아
   `Jsonb(Jsonb(...))` → 라이브 DB에서 `TypeError: not JSON serializable`로 터질 상태였음(재현 확인).
   호출부를 plain dict로 통일, 미사용 Jsonb import 제거.

이로써 잡큐·감사이벤트의 JSONB 경로는 전부 리포지토리 계층에서 단일 래핑으로 정리됨.

## 0.0.7 실 Shopify 연동 + 대시보드 Phase 3 1차 (2026-07-07) — 테스트 352 통과/26 스킵

**A. 실 Shopify 연동 (커밋 d5b387b)** — 0.0.4의 웹훅-형상 mock을 실제 연결 가능 상태로 격상:
1. **웹훅 수신기** `/commerce/webhooks/shopify/{orders,refunds}` — HMAC-SHA256 서명이 인증
   (`SHOPIFY_WEBHOOK_SECRET`). fail-closed: 시크릿 미설정 시 503으로 전체 거부.
   실 Shopify 주문/환불 JSON → 기존 ingest 모델로 변환 후 **동일한 어트리뷰션/원장 경로** 재사용.
   미지원 통화·FX 미설정(`SHOPIFY_FX_RATES`)·미인식 status는 422 거부(가짜 값 저장 금지).
2. **Admin API 클라이언트**(`app/providers/shopify_admin.py`) — PriceRule+DiscountCode 발급.
   dry-run 기본(`SHOPIFY_DRY_RUN`+`ALLOW_LIVE_SHOPIFY_CALLS` 이중 게이트, AI 게이트와 동일 패턴).
   `POST /commerce/discount-codes/issue` — 라이브 발급은 DB 필수(Shopify에만 존재하는 미추적 코드 방지).
3. ⚠️ 운영 잔여: 실제 Shopify 커스텀 앱 생성·웹훅 등록·시크릿 `.env` 설정은 스토어 개설 후 수동 절차.

**B. 대시보드 Phase 3 1차 (스모크+브라우저 검증)**:
1. discovery/candidates/tracking 화면을 content-grid/span 격상 레이아웃으로 정규화.
2. **성과 분석: 통화-명시 매출 입력**(MXN/PEN/USD + 기록시점 FX, USD는 1 고정) — 0.0.4 백엔드
   트리플과 정합. 운영 rollup 프리뷰도 FX 환산 USD 사용(이전: 로컬 통화값을 USD로 오기록).
3. **정산 화면: Shopify 할인코드 발급 패널** 신설 — `/commerce/discount-codes/issue` 연동,
   data-write-action 게이트 준수, dry-run 결과(계획된 요청+차단 사유) 표시.
4. 캠페인 채널 셀렉트를 Shopify 주력/TikTok Shop 보류로 재배열(0.0.1 전략 정합).
5. 스모크에 Phase 3 회귀 단정 추가(통화 트리플·발급 패널·grid 레이아웃).
⚠️ 잔여: 화면별 KPI 메트릭 스트립(JS 배선 필요), 캠페인 퍼널 하드코딩 수치의 실데이터화.

## 0.0.9 대시보드 퍼널 실데이터화 + Shopify go-live 준비 (2026-07-07) — 테스트 354 통과/26 스킵

**A. 캠페인 실행 퍼널 실데이터 배선 (커밋 48b863f)** — 하드코딩 `24/14/9/6/2`를 제거하고
`buildCampaignFunnel()`로 파생. 숏리스트(후보 풀)·초안(스크리닝/준비 수)은 실카운트 앵커,
브랜드세이프/승인/응답은 문서화된 전환율로 파생, 전 단계 단조 비증가 클램프. 브라우저 검증 완료.

**B. Shopify go-live 준비물 (코드로 가능한 부분 완료)** — 실제 go-live는 David의 Shopify 계정
필요(스토어·앱·시크릿)라 코드 밖. 이번에 준비한 것:
1. **웹훅 자동 등록 스크립트** `scripts/register_shopify_webhooks.py` — orders/create·orders/updated·
   refunds/create를 수신 엔드포인트에 멱등 등록. dry-run 기본(라이브 게이트 열려야 실행), 시크릿
   미설정 시 등록 거부(수신기가 503 반환하므로). `--list`로 현재 등록 확인.
2. **go-live 런북** `docs/SHOPIFY_GOLIVE.md` — 커스텀 앱 생성→스코프→토큰→시크릿→웹훅 등록→
   E2E 검증(테스트 주문/환불로 ledger accrual/reversal 확인)→라이브 게이트 flip→롤백까지 단계별.
3. 스크립트 순수 로직(수신 경로 매핑) 회귀 테스트 추가.

⚠️ **David가 할 남은 일**: `docs/SHOPIFY_GOLIVE.md` 따라 스토어에서 앱 생성 + `.env`에 `SHOPIFY_*`
시크릿 입력 + 스크립트로 웹훅 등록 + 테스트 주문 검증. 코드는 준비 완료, 수동 절차만 남음.

## 0.0.10 화면별 KPI 스트립 + Shopify go-live preflight (2026-07-08) — 테스트 360 통과/26 스킵

**A. 대시보드 Phase 3 잔여 완료 — 화면별 KPI 메트릭 스트립 (스모크+브라우저 검증)**
1. candidates/tracking/settlement 화면 상단에 KPI 스트립 신설(`renderScreenKpis()` + 화면별 빌더 3개,
   커맨드 화면 metric-card 스타일 재사용 `.screen-kpis`).
2. 전 수치 실데이터 앵커: 후보 화면은 후보 풀·평균 적합점수·스크리닝·아웃리치 준비
   (buildCommandMetrics 파생), 성과/정산 화면은 **세션 쓰기 로그**(state.sessionSnapshots /
   sessionContracts / sessionDiscountCodes) 집계 — 실제 완료된 쓰기만 카운트. 취소(cancelled)·
   API 거부(error.payload 있음)는 집계 제외, 오프라인 미리보기 폴백만 preview로 구분 집계.
3. 지급 대기/차단 KPI와 지급 테이블은 단일 소스 `PAYOUT_ROWS` 공유(불일치 원천 차단).
4. 브라우저 검증: 스냅샷 저장→성과 KPI 즉시 갱신(1건/12K뷰/$318.6), 계약 저장·할인코드
   발급→정산 KPI 즉시 갱신 확인. 스모크에 회귀 단정 추가(마운트 위치·빌더·세션 로그·
   API 거부 미집계 가드).

**B. Shopify go-live preflight (계정 없이 가능한 부분 완료)**
1. `scripts/shopify_golive_preflight.py` 신설 — 런북 2단계 전제조건을 실행 가능 체크리스트로:
   도메인(*.myshopify.com)/admin 토큰(shpat_)/웹훅 시크릿/API 버전/FX 레이트(파일럿 통화
   MXN·PEN 커버리지)/USE_DATABASE/라이브 게이트를 READY·MISSING·WARN·INFO로 보고.
   **네트워크 호출 0**이라 계정 없이 언제든 안전. `--json` 지원, cp949 콘솔 안전(ASCII 출력).
2. 순수 로직 테스트 6개 추가(354→360). 런북 2단계에 preflight 실행 안내 반영.
3. 실검증: 웹훅 등록 스크립트 dry-run 정상(게이트 닫힘 시 계획만 출력 + 차단 사유 안내),
   preflight가 현 미설정 상태를 정확히 5건 MISSING으로 보고(exit 1).

⚠️ **잔여(코드 밖, 0.0.9와 동일)**: Shopify 스토어/커스텀 앱 생성 → `.env` 시크릿 → preflight
통과 확인 → 웹훅 등록 → 테스트 주문 검증. 계정 생기면 `docs/SHOPIFY_GOLIVE.md` 순서대로.

## 0.0.11 라이브 전환 준비 1차 + 파생 수치 정직화 (2026-07-08) — 테스트 360 통과/26 스킵

**배경 — C(트렌드 탭) 착수 전 비판 평가로 우선순위 재배열.** 평가 결론: (1) 트렌드 탭
tier-1만으로는 핵심 패널(모멘텀 크리에이터 테이블)이 채워지지 않음 — `creator_provided`는
운영자 API 임포트 계약일 뿐 크리에이터 제출 채널이 없고, 실제 아웃리치 0건이라 "탭→발굴→
아웃리치→관계→데이터→탭" 순환 의존. 뉴스 RSS는 시장 신호이지 크리에이터 모멘텀이 아님.
0.0.8의 목업도 리포에 미커밋. (2) 전체 병목은 발굴 폭이 아니라 **라이브 전환**(공개 배포·
관리형 DB·OIDC) — Shopify go-live 런북 스스로 공개 HTTPS+DB를 전제하는데 로드맵 A의 해당
항목들이 계속 밀려 있었음. 재배열: ① 라이브 전환 인프라 → ② 수동 리서치 실데이터 파일럿
(플레이북 Low/Medium 경로, 기존 인테이크 화면으로 충분) → ③ C 축소판(제출 채널→뉴스 패널→
풀 탭은 실데이터 유입 후). 이번 세션 = ①의 코드 부분 + 파생 수치 정직화.

**A. Render 배포 준비 (계정 불필요 부분 완료)**
1. `render.yaml`을 **리포 루트로 이전**(Render 블루프린트는 루트만 인식; `rootDir:
   work/briwell_mvp_app`). 기존 위치(work/briwell_mvp_app/render.yaml)는 블루프린트로
   감지되지 않는 배포 불능 상태였음.
2. **SHOPIFY_* 환경변수 7종 추가** — 기존 블루프린트는 0.0.7 Shopify 통합 이전 작성이라
   전무했음(그대로 배포 시 웹훅 전부 503). dry-run 이중 게이트 기본값으로 fail-closed.
3. 관리형 Postgres 블록(`briwell-postgres`, basic-256mb — 무료 티어는 30일 만료) +
   `DATABASE_URL`을 `fromDatabase`로 주입. `PYTHON_VERSION=3.14.4` 명시.
4. **`docs/DEPLOY_RENDER.md` 런북 신설**: Supabase OIDC(비대칭 JWT 서명키 필수·role claim
   SQL)→백업/복원 증빙(BACKUP_RESTORE_TESTED_AT 게이트)→블루프린트 배포(sync:false 표)→
   검증 curl→대시보드 연결→Shopify 연계→롤백. README/orchestration 참조 경로 갱신.

**B. OIDC 배선 1단계 (대시보드)**
1. 연결 설정 드로어에 **Bearer 토큰(OIDC) 필드** 추가 — api-client에 bearerToken 지원
   (스토리지→`Authorization` 헤더)이 이미 있었는데 입력 UI가 없던 갭 해소. 빈 값 저장 시
   저장된 토큰 삭제(로그아웃). 저장/삭제 브라우저 검증 완료.
2. 프로덕션 API는 헤더 RBAC를 readiness가 차단하므로 이 필드가 배포 후 대시보드 사용의
   전제. 풀 로그인 플로우(Supabase JS)는 후속 작업.

**C. 파생 수치 정직화 (경영 화면 — "그럴듯한 가짜" 방지)**
1. `추정` 태그(.derived-tag): GMV 예측 카드 + 캠페인 퍼널의 전환율 파생 단계(브랜드세이프
   fallback·승인·응답). `buildCampaignFunnel()`이 stage별 `derived` 플래그 반환 — 실측
   브랜드세이프 카운트가 생기면 해당 태그 자동 소멸.
2. 각주(.derived-note): 메트릭 스파크라인·전기 대비 %(현재 값 기반 대표 형상임을 명시),
   GMV 추이 히어로("추정 곡선"), 퍼널(전환율 65/70/35 명시 + 실카운트 단계 구분). 히어로
   델타 배지도 "추정 전기 대비"로 변경.
3. 스모크 회귀 단정 추가, 브라우저 검증 완료.

**D. 커밋 후 비판 재검증에서 잡은 결함 2건 (같은 날 후속 수정)** — 사용자 요청으로 위 작업을
재검증한 결과: (1) 블루프린트에 `OUTBOX_WORKER_ENABLED` 누락 — config 기본값이 false라
배포 시 DB 잡큐가 영원히 미처리될 뻔함 → true로 추가. (2) 배포 런북 5단계 "로컬 서빙도 가능"
문구가 readiness의 `CORS_LOCALHOST_ORIGIN_NOT_ALLOWED_IN_PRODUCTION` 차단과 모순 → 공개
오리진 필수로 정정. 부수: PYTHON_VERSION/Postgres 플랜명 불일치 시 대처, localStorage 토큰
주의 문구 추가. **재발 방지**: "모든 구현 작업 후 커밋 전 비판적 자가 검증" 상시 지침을
HANDOFF 워킹 컨벤션·머신 훅·메모리에 등록(사용자 지시, 재요청 불필요).

## 0.0.12 creator_provided 제출 채널 (2026-07-08) — C 축소판 1단계 완료

우선순위 재배열(0.0.11 배경)의 코드 트랙 첫 항목. 크리에이터가 본인 데이터를 제출하는
합법 유입 채널을 템플릿+대시보드로 구축 — 실데이터 파일럿(수동 아웃리치)과 맞물리는 전제.

1. **제출 템플릿 2종** (`work/briwell_dashboard_app/templates/creator_provided_{profile,posts}_template.csv`)
   — provider 계약(consent_ref·provided_at 포함)과 1:1. Excel 호환 위해 악센트 제거(기존 관례).
2. **스페인어 요청문** `docs/CREATOR_DATA_REQUEST_ES.md` — DM용/이메일용 2종 + 동의 문구 +
   운영자 체크리스트(consent_ref = 동의 메시지 참조, provided_at = 수신 시각, 수동 발송만).
   대시보드에서 DM용 원클릭 복사.
3. **대시보드 패널** (후보 인테이크 → "크리에이터 제공 데이터"): 템플릿 다운로드, 요청문 복사,
   CSV 2종 업로드 → 미리보기(검증) → 정규화 실행. **동의 fail-closed**: consent_ref/provided_at
   없는 행이 있으면 정규화 거부(개별 행 사유 표시). 50명 초과 업로드는 서버 silent truncation
   방지 위해 차단. 프로필에 없는 계정의 게시물은 경고로 표시(서버가 조용히 버리는 것 예방).
4. **배선**: `/providers/creator-provided/import`(순수 정규화 — DB 쓰기 없음이라 쓰기 확인
   allowlist에 등재, compute 배지). 정규화 결과는 applyCreatorProvidedToIntake로 **기존 인테이크
   상태에 주입** — 품질 게이트·최근 20 스크리닝·크리에이터/영상 등록(쓰기 게이트)이 그대로 적용.
   오프라인 시 서버 계약을 미러링한 로컬 정규화 폴백. instagram/youtube 프로필 URL이면
   플랫폼 자동 추론(기존 tiktok 하드코딩 수정), segment=creator_submitted.
5. **검증**: 서버 provider에 대시보드와 동일 형태 payload 실행(live_completed, consent 메타 보존
   확인), 브라우저 E2E(정상 제출→인테이크 반영, 동의 누락→차단, 미매칭 게시물→경고), 스모크
   회귀 단정 다수 추가. 자가 검증에서 잡은 것: splitPipeList 중복 정의→기존 splitList 재사용,
   CSV 템플릿 악센트 제거, >50명 차단.

⚠️ 다음: C 축소판 (b) 발굴 화면 뉴스 RSS 패널(백엔드 fetcher 필요) — 단, David의 Render/Supabase
배포(1순위)와 수동 리서치 파일럿(2순위)이 먼저 움직이면 그쪽 지원 우선.

## 0.0.13 발굴 화면 시장 뉴스 신호 패널 (2026-07-08) — C 축소판 2단계 완료, 테스트 368 통과/26 스킵

C 축소판 (b): 구글 뉴스 **공개 RSS** 기반 LATAM K-뷰티 시장 헤드라인을 발굴 화면에 표시.
합법 소스 레인(안티봇 우회·플랫폼 스크래핑 없음). 시장 신호 전용 — 크리에이터 워크플로우
입력으로는 절대 사용 안 함(`source_type="public_news_rss"`로 구분, 패널에도 명시).

1. **백엔드 fetcher** `app/trends/news_rss.py` — 국가(MX/PE/EC)×제품군 스페인어 쿼리 빌더
   (+국가별 일반 K-beauty 쿼리), stdlib XML 파서, 쿼리당 15분 인프로세스 캐시(요청 예의),
   쿼리당 최대 10건 캡. **하우스 게이팅 패턴 동일**: 드라이런 기본(라벨된 샘플 반환),
   라이브는 `NEWS_RSS_DRY_RUN=false` + `ALLOW_LIVE_NEWS_RSS_CALLS=true` 이중 게이트.
   부분 실패는 live_completed + errors 병기, 전체 실패만 blocked.
2. **엔드포인트** `GET /trends/news` (admin/operator/campaign_manager; viewer 403 확인).
   미허용 국가/카테고리는 필터링.
3. **대시보드 패널** (발굴 화면 하단): 발굴 폼의 시장/제품군 선택을 재사용해 조회, 모드 배지
   (라이브 RSS / 드라이런 샘플 / 라이브 아님)로 데이터 성격 명시, 라이브 게이트 차단 사유 표시.
   오프라인 폴백도 샘플임을 라벨. **외부 피드 XSS 방어**: escapeHtml(따옴표 포함) +
   `safeExternalUrl()` 스킴 가드(http/https 외 href는 `#`), rel=noopener.
4. **설정**: config 2키, .env.example, render.yaml(프로덕션은 라이브 ON — 공개 피드라 안전).
5. **검증**: 순수 로직 테스트 8개(쿼리 빌더·XML 파싱·드라이런 무네트워크·캐시 TTL·전량 실패
   blocked·이중 게이트), TestClient로 엔드포인트/권한 검증, 브라우저 E2E(오프라인 폴백 렌더),
   스모크 단정 추가. 자가 검증에서 잡은 것: javascript:/data: href XSS 벡터 → 스킴 가드 추가.

⚠️ 다음 코드 후보: C 축소판 (c) 풀 트렌드 탭은 **실데이터 유입 후**. 그 전에는 David 트랙
(배포·수동 리서치 파일럿) 지원이 우선.

## 0.0.14 ES 크리에이터 랜딩 확정 — 컨셉 C (2026-07-10)

전략회의(§합의 프로세스: 계획→회의→컨셉 샘플→구현) 절차대로 진행해 **랜딩 확정**.
로드맵 우선순위 2(실데이터 파일럿)의 아웃리치 자산이 준비됨.

1. **결정 로그**: 1차 타겟 = LATAM 스킨케어 크리에이터(ES) / CTA = 지원 폼 단독
   (WhatsApp·mailto 제외) / 화장품 3브랜드만 — 파넬(일레븐코퍼레이션)·에센허브/BRTC(아미
   코스메틱스)·더말(더말코리아; David가 "다말"로 지칭했으나 실존 브랜드는 더말) — 한글안경(안경)은
   제외 / 3안(A 시스템·다크, B 클린뷰티, C 에디토리얼 하이브리드) 풀페이지 비교 후 **C 확정**.
2. **산출물**: `work/briwell_landing_page/index.html`(확정본, 자기완결 단일 파일),
   `concepts/`(3안 아카이브 + 비교 뷰어), `assets/img/products/`(브랜드 공식 제품 사진 14장 +
   SOURCES.md 출처 기록), README.md. 구 WIP는 `_superseded_index_2026-07-09.html`로 보존.
   **KO 회사 페이지도 C 시스템으로 리뉴얼**(2026-07-10, `ko/index.html`, 자기완결; 타겟 =
   브랜드 파트너·심사역; 한글 세리프는 Noto Serif KR; 검증 가능한 사실만 — 테스트 368개·
   fail-closed 동의·인간 승인 게이트; 구판은 `ko/_superseded_ko_2026-07-09.html` 보존,
   landing.css/js는 이제 구판 아카이브 전용).
3. **카피 원칙(코드·컴플라이언스와 정합)**: 운영 약속 금지(David 지시로 "72시간 회신"·"제품 발송"
   제거), Shopify 매장 표현 금지, 허위 수치·커미션율 미기재, 동의 문구는 인테이크 fail-closed
   검증과 일치("Si no diste permiso, el sistema lo rechaza").
4. **정리**: landing.js의 사문화된 live-pulse fetch 제거 — `/trends/news`는
   admin/operator/campaign_manager 전용(0.0.13)이라 공개 페이지가 호출 불가능했음.
5. **검증**: 375/768/1280px 실측 가로 오버플로 0·이미지 깨짐 0, 모바일 통계 스택·CTA 줄바꿈
   수정. ⚠️ 헤드리스 Edge는 창 폭 ~500px 미만을 무시해 375px 캡처가 왜곡됨 — same-origin
   iframe 래퍼(520px 창 + 375px iframe)로 촬영해야 함.
6. **다음(전부 David 결정/계정 대기)**: 지원 폼 생성(`docs/CREATOR_APPLY_FORM_ES.md` 스펙
   완성 — Tally 권장, 응답이 creator_provided CSV로 매핑되도록 설계) → ES CTA 연결(index.html
   `#aplicar` 2곳), 도메인·호스팅(Render static 제안)·수신 이메일 → KO 파트너 문의 CTA 연결
   (`#contacto` 2곳), 브랜드 사진 사용 확인.

## 0.0.15 브랜드 아이덴티티 "The Well" 반영 — ES·KO 전면 리디자인 (2026-07-11)

David가 브랜드의 원천을 공개: **Briwell = Bridge(다리) + Well(우물)** — 사12:3 "기쁨으로
구원의 우물들에서 물을 길으리로다", 이삭의 우물, 생명수. 비전 = 하나의 깊은 우물이 다른
우물들을 차고 넘치게 채운다(한국↔중남미, 착취가 아니라 채움). 이 아이덴티티로 두 페이지를
전면 리빌드 (분석→설계→자기비판→구현 프로세스로 진행).

1. **디자인 시스템 "The Well"**: 깊은 우물 청록 잉크(#0C2E2F) + 생명수 아쿠아(텍스트 #0E7C71/
   장식 #2FD0BC) + 햇빛 골드(#D9A441, 장식 전용) + 석재 페이퍼(#F5F2EA). 시그니처 장치 =
   원형 '우물 입구' 사진 프레임, 동심원 물결(reduced-motion 대응 CSS 애니메이션), 딥 잉크 섹션,
   이중 원 로고 마크(SVG 파비콘 포함).
2. **카피 축**: ES "Que tu contenido rebose."(히어로) / "Sin tu permiso, ni una gota."(동의) ·
   KO "깊은 우물 하나가 다른 우물들을 채웁니다." / "동의 없이는, 한 방울도."
3. **성경 인용 배치 원칙**: KO 브랜드 스토리 섹션에만 사12:3 인용(+이삭의 우물·르호봇 서사,
   동심원 비전 다이어그램 SVG: 서울의 우물→크리에이터의 우물→넘치는 커뮤니티). ES 상업
   페이지는 보편적 물 언어만 — 기존 카피 원칙(운영 약속 금지 등, 0.0.14)은 전부 유지.
4. **자기비판으로 반영**: 은유는 제목·한 줄에만(본문은 구체어), 원형 프레임은 브랜드 사진
   전용(스크린샷은 직각), 텍스트 아쿠아는 대비 확보 변형, 기존 신뢰 자산(시스템 증거·368
   테스트·fail-closed) 전부 유지.
5. **검증**: 375/1280px 실측 오버플로 0·이미지 깨짐 0·콘솔 클린, 캡션이 원형 프레임
   overflow에 잘리는 버그 발견 즉시 수정. 브랜드 아이덴티티는 assistant 메모리에도 저장됨.

## 0.0.16 브랜드 결정 반영 + 대시보드 PWA + 모바일 로드맵 (2026-07-11)

David 브랜드 결정: 공식 표기 **Briwell**, 태그라인 **"Bridge + Well"**, **신앙 표현은 회사 내부
정신으로만**(공개 페이지 성경 인용 금지 → KO 페이지 사12:3 인용을 보편 문장 "기쁨으로 길어 올려,
차고 넘치게 흘려보낸다"로 교체, 이삭 명시도 보편화), 로고·명함·컬러는 추후(13안+서체 7종 쇼케이스
유지, The Well 팔레트 유지 권고 수용).

1. **네이티브 앱 판단**: 지금은 안 만든다 — 사용자 미확정(운영자 1~2명/크리에이터 0명), 진짜
   병목은 배포·파일럿 ops. 트리거 기반 로드맵 채택: ①배포 ②운영 대시보드 PWA ③크리에이터
   포털(모바일 웹, 활동 크리에이터 생기면) ④Expo 네이티브(포털 사용자 규모+푸시 필요 시).
2. **대시보드 PWA (로드맵 2 완료)**: manifest.webmanifest + sw.js(앱셸 network-first, API
   미개입) + 우물 마크 아이콘 3종(192/512/maskable) + 등록 스크립트. 반응형은 기존
   1120/680px 레이어가 이미 견고함을 확인(375px 실렌더 검증). 스모크 통과.
3. **랜딩 반응형 정밀 감사**: ES·KO × 360/414/540/768/1024px 자가측정 감사 페이지로 전수
   확인 — 오버플로 0, 이미지 깨짐 0. 추가 수정 불필요.
4. **워드마크 서체 후보 7종** 쇼케이스 추가(Fraunces/Newsreader/Playfair/Cormorant/Sora/
   Manrope/Space Grotesk — work/briwell_brand/logo-card-concepts.html).
5. **크리에이터 포털(로드맵 3) 설계 확정, 구현 다음 세션**: 로그인 없는 **토큰 개인링크**
   방식(파일럿 규모 표준) — GET /portal/{token}으로 본인 코드·판매 기록·커미션 조회, 모바일
   웹 우선, 백엔드 정산 모델 재사용. 구현 시 368개 테스트 유지가 게이트.

## 0.0.17 크리에이터 셀프서브 포털 (2026-07-12) — 로드맵 3 구현, 테스트 378 통과/26 스킵

로그인 없는 **토큰 개인링크** 방식(파일럿 규모 표준). 크리에이터가 자기 코드·판매 기록·커미션
잔액을 언제든 확인 — "커미션 신뢰"라는 최대 차별점을 셀프서브로 증명하는 표면.

1. **백엔드**: 마이그레이션 009(`creator_portal_token` — 크리에이터당 활성 토큰 1개, 회전=폐기),
   `app/repositories/portal.py`, `app/routers/portal.py`:
   - `POST /portal/tokens` (admin/operator/campaign_manager) — 발급·회전. DB off →
     validated_not_persisted 관례 유지.
   - `DELETE /portal/tokens/{creator_id}` — 폐기(킬스위치).
   - `GET /portal/me?token=` — **공개·토큰 게이트·읽기 전용**. 필드 화이트리스트로 운영자
     이메일·내부 메모·타 크리에이터 데이터 누출 구조적 차단. DB off는 소비자 표면이므로
     503 PORTAL_UNAVAILABLE로 정직하게 실패(운영자 읽기의 빈 배열 관례와 의도적으로 다름).
   - 데이터는 기존 commerce 스키마 재사용: `creator_discount_code`·`commission_ledger`·
     `creator_commission_balance`. 신규 쓰기 경로 없음.
2. **프런트**: `work/briwell_portal_app/index.html` — 자기완결 모바일 웹(ES), The Well
   아이덴티티(포털=기업 인프라 표면). 잔액·코드(복사 버튼)·무브먼트(+적립/−리버설)·에러
   상태(만료 링크/점검 중). `?demo=1` 데모 모드, `?api=` 오리진 오버라이드. 560px 렌더 검증.
3. **테스트**: `tests/test_portal.py` 10개 — RBAC(403), DB off 관례, 404 무효 토큰,
   해피패스 + **누출 방지 단정**(내부 이메일·메모·shopify id가 응답 텍스트에 없음을 검사).
   전체 378 통과/26 스킵, 회귀 0.
4. **배포 시 남은 것**: 포털 페이지 호스팅 오리진의 CORS 허용(프로덕션 CORS 게이트에 추가),
   대시보드에서 토큰 발급 버튼(현재는 API 직접 호출), 프로덕션 URL 형태
   `portal.briwell.co/?t=...` 결정.

## 0.0.18 대시보드 포털 링크 발급 패널 + CORS DELETE 수정 (2026-07-12) — 테스트 379 통과/26 스킵

0.0.17 배포 노트의 계정-독립 잔여 작업(대시보드 토큰 발급 버튼) 구현. 실 브라우저 검증
과정에서 백엔드 CORS 버그를 발견해 함께 수정.

1. **정산 화면 "크리에이터 포털 링크" 패널**: 발급·회전(`POST /portal/tokens`)과 폐기
   (`DELETE`, 킬스위치) 버튼 — 둘 다 라이브 쓰기 확인 게이트 통과(`data-write-action`).
   포털 페이지 주소 입력(localStorage 유지) → `?t=` 개인링크 조립 + 복사 버튼(포털 페이지는
   `qs.get("t")`를 읽음).
2. **정직성 규칙**: persisted일 때만 링크 렌더. validated_not_persisted(DB off)는 "실제 포털
   링크로 동작하지 않습니다"를 명시. API 불통 시 로컬 가짜 토큰 생성 금지(죽은 링크 방지) —
   `api_unreachable`로 정직하게 실패. 전부 스모크 단정으로 고정.
3. **CORS 버그 수정(`app/main.py`)**: allow_methods가 GET/POST/OPTIONS뿐이라 0.0.17의
   `DELETE /portal/tokens`(킬스위치)를 브라우저에서 절대 호출할 수 없었음(preflight 실패).
   실 브라우저 검증에서 발견 → DELETE 추가 + 회귀 테스트(preflight 200, allow-methods에
   DELETE 포함). 378→379 통과/26 스킵.
4. **검증(실 브라우저, 대시보드 8070 + 백엔드 8030 라이브)**: 발급·폐기 라이브 왕복, 쓰기
   확인 모달(POST /portal/tokens 표기)·취소 경로(cancelled_by_user), 링크 조립 3케이스
   (기본 base / 쿼리 포함 base는 `&t=` / 빈 base는 토큰만+안내), 콘솔 에러 0.
   `docs/DEPLOY_RENDER.md`의 CORS_ALLOWED_ORIGINS 행에 포털 오리진도 추가해야 함을 명시.
5. **배포 시 남은 것(0.0.17에서 축소)**: 포털 페이지 호스팅 오리진의 CORS 등록과 프로덕션
   URL 형태(`portal.briwell.co/?t=...`) 결정 — 둘 다 David 계정/도메인 대기.

## 0.0.19 벤더 포털 기획 v0 (2026-07-12) — 결정 대기, 코드 미작성

David 지시: 브랜드사(한국 화장품사)가 클라이언트가 된 후 카탈로그·제품 정보·성분을 직접 올리고
AI가 분석·분류·저장·가공해 업무를 획기적으로 줄이는 **벤더 포털**. 합의 프로세스(계획→전략회의→
컨셉 샘플→구현)에 따라 기획서만 작성: `outputs/briwell_vendor_portal_plan_v0.md`.

- 벤치마킹: Akeneo SDM(모듈형 공급사 온보딩 = 뼈대), Salsify(완성도 스코어), Amazon VC(즉시
  오류 리포트), UMMA(K-beauty B2B 자료 관행), CosIng(EU 공식 INCI 사전 — 무료 공개 CSV, 정규화
  시드), LATAM 규제(COFEPRIS 성분 목록·NOM-141 / DIGEMID NSO / **안데안 Decision 833: 페루
  NSO가 에콰도르에도 상호 인정** → 성분 사전 스크리닝 가치 큼).
- 설계 골자: 업로드(원본 보존·해시) → AI 5단계 파이프라인(추출→INCI 정규화→검증→규제 신호→
  완성도 스코어, 드라이런 기본 듀얼 게이트) → 벤더 확인 → 운영자 승인(인간 게이트) →
  기존 product_catalog 승격. 기존 자산 최대 재사용(Gemini 어댑터·eval harness·claims-check·
  포털 토큰 패턴·fail-closed 검증).
- 결정 포인트 7개가 문서 §9에 정리됨(범위·저장소·접근 A/B안·1호 벤더·규제 신호 시점·UI 방향·
  명칭). **David 피드백·결정 후 Phase 1 착수.**

## 0.0.20 브랜드 파트너 허브 Phase 1 구현 (2026-07-12) — 테스트 427 통과/26 스킵

0.0.19 기획을 David가 승인(명칭 = **브랜드 파트너 허브**, 업로드 = **사진/PDF/자료 3레인 분리**,
나머지 권장안 채택)하여 Phase 1 전체 구현. 브랜드사가 자료를 올리면 AI가 구조화하고 운영자
승인으로 기존 product_catalog에 등록되는 셀프서브 온보딩 파이프라인.

1. **백엔드**: 마이그레이션 010(brand_partner·brand_partner_token·partner_upload·
   partner_product_draft·partner_review_decision — 토큰은 009 포털 패턴 복제, 원본 파일 영구
   보존), `app/partners/` 파이프라인 5모듈(추출→INCI 정규화→검증→규제 신호→완성도 스코어),
   `app/routers/partner_hub.py` 이중 표면:
   - 운영자(`/partners`, RBAC): 등록 / 토큰 발급·회전·폐기 / 검수 큐 / 승인·반려. 승인 시
     초안 → product_catalog 승격(미지원 카테고리 422), 결정은 partner_review_decision에 기록
     (인간 게이트 감사 추적).
   - 파트너(`/partner-hub`, 토큰 게이트): me / uploads(레인별 확장자+매직바이트+크기 검증,
     sha256 기록, 실행 불가 경로 저장) / extract / draft 저장·제출. 필드 화이트리스트로
     internal_memo·타사 데이터·storage_path·모델명 구조적 차단. DB off는 소비자 표면이라
     503 PARTNER_HUB_UNAVAILABLE(포털 관례), 편집 가능 필드 화이트리스트로 임의 키 주입 차단.
2. **AI 파이프라인**: 듀얼 게이트(`PARTNER_AI_DRY_RUN` 기본 true + `ALLOW_LIVE_PARTNER_AI_CALLS`)
   — 드라이런은 업로드 해시 기반 결정적 샘플. 라이브는 Gemini 멀티모달(사진·PDF inlineData,
   CSV 텍스트, xlsx는 Phase 2로 정직하게 표기). INCI 사전(~80종, CosIng 부분집합)과 규제 룰
   (MX/PE/EC 보수적 시드, 출처 기록)은 **코드 시드**(`ingredient_data.py`) — 설계의 DB 테이블
   대신 채택(무DB 동작·드리프트 차단). 미매칭 성분은 추측 없이 unmatched로 정직 표기하되,
   규제 스크리닝은 raw 문자열도 검사해 사전 미스 뒤에 숨지 못하게 함. 모든 규제 결과에
   "법률 자문 아님" 문구 동봉(비협상 제약 6).
3. **프런트**: `work/briwell_partner_hub_app/index.html` — 자기완결 KO 데스크톱 우선, The Well
   아이덴티티. 3분리 업로드 레인, AI 초안 생성, 초안 편집(확신도 표시·완성도 바·규제 칩·검증
   이슈), 제출. `?demo=1` 데모, 에러 상태 2종(무효 링크/점검 중). 대시보드에 "파트너 허브"
   화면 추가(등록·링크 발급/폐기·검수 큐·승인/반려, 전부 쓰기 확인 게이트, 파트너 문자열
   escapeHtml).
4. **테스트**: 47개 신규(파이프라인 단위·RBAC·DB-off 관례·업로드 검증·격리/누출 방지·검수
   플로우) + CORS 회귀 1 = **427 통과/26 스킵**, 대시보드 스모크 통과(파트너 허브 단정 ~20개).
5. **자가 검증에서 잡은 것**: 로컬 CORS 기본값·`.env`·`.env.example`에 포털(8072)·허브(8073)
   오리진 누락 — 브라우저 실검증에서 net::ERR_FAILED로 발견, 셋 다 수정 + 회귀 테스트.
   (conftest가 BRIWELL_SKIP_DOTENV라 테스트만으론 안 잡혔음 — 실브라우저 검증의 가치.)
   업로드 저장 경로 `data/partner_uploads/`는 .gitignore 추가. 의존성 python-multipart 추가.
6. **남은 것**: 실 카탈로그 골든셋(1호 벤더 자료 필요 — David), 라이브 AI 개방은 골든셋 측정
   후, xlsx 파싱·완성도 스코어 정식화·Supabase 계정 전환·R2는 Phase 2~3(기획서 §10).
   배포 시 허브 페이지 오리진 CORS 등록(DEPLOY_RENDER.md 반영됨).

## 0.0.21 파트너 허브 v2 — Newsreader·기타 레인·AI 자동 인제스천 (2026-07-12) — 테스트 438 통과/26 스킵

v2 설계(`outputs/briwell_partner_hub_v2_design.md`)를 David 확정대로 구현. 결정 4건:
①서체 후보 2번 **Newsreader**(허브 한정) ②기타 레인 **문서만** ③분석은 **업로드 즉시 자동**
④모델은 "26-07-12 기준 최고 성능" 재제안 → **Claude Opus 4.8 기본 + Fable 5 에스컬레이션**
확정(Gemini 3.5 Pro는 07-17 출시 예정·미출시라 **출시 후 골든셋 맞대결**로 재평가, 교체는
config 1줄. 3.5 Flash는 속도 티어라 부적합 판정).

1. **서체**: 허브 디스플레이 계층(로고·h1·카드 제목·점수) Fraunces → Newsreader, 본문 Noto
   Sans KR 유지. 허브 한정 — 브랜드 전체 전개는 서체 최종 확정 때.
2. **기타(etc) 레인**: docx·pptx·hwp·hwpx·txt (화이트리스트+매직바이트 — OOXML=PK,
   HWP 5.x=OLE compound·3.0=ASCII 시그니처, txt=NUL 검사). 영상은 보류(결정 기록).
3. **AI 인제스천**(마이그레이션 011 + `app/partners/ingestion.py`): 업로드 저장 즉시
   `partner_asset_ingest` 잡 등록(기존 006 잡큐 재사용, 렌더는 OUTBOX_WORKER_ENABLED=true) →
   분류(유형 8종+needs_review·언어·신뢰도·KO 요약·언급 제품) → 유형별 추출 →
   `partner_asset_profile` 저장(업로드당 1개, 재분석 교체). 인큐 실패해도 업로드는 성공
   (pending="분석 대기" 정직 표시). live 신뢰도 0.7 미만 → needs_review(추측 금지).
   model·usage·prompt_version은 프로필 자체 기록(중앙 invocation_log 통합은 라이브 개방 시).
4. **프로바이더 추상화**: `PARTNER_AI_PROVIDER`(기본 anthropic)·`PARTNER_AI_MODEL`(기본
   claude-opus-4-8)·`PARTNER_AI_ESCALATION_MODEL`(기본 꺼짐, fable-5 지정 시 저신뢰 문서만
   재시도 + refusal 대비 서버사이드 fallbacks→Opus 4.8). Anthropic 경로는 공식 SDK +
   structured outputs(JSON 스키마 강제), PDF/이미지 네이티브, csv/txt 텍스트 인라인,
   docx/pptx/hwp는 파일명 기준 분류에 그침을 요약에 명시(전처리 파서는 후속). Gemini 경로
   유지(config 전환). 듀얼 게이트 관례 동일 — 드라이런 기본, 라이브는 골든셋 측정 후.
   의존성 `anthropic>=0.92.0` 추가. render.yaml·.env.example·DEPLOY_RENDER에
   ANTHROPIC_API_KEY(sync:false·비워도 안전) 반영.
5. **허브 UI**: 4레인 그리드(반응형 2×2→1열), 업로드 표에 "AI 분석" 열(유형 배지+신뢰도%·
   분석 중·확인 필요·분석 실패)과 KO 요약 노트. `/partner-hub/me`가 업로드별 analysis를
   화이트리스트로 동봉(model·error 내부 유지).
6. **테스트**: +11 (etc 레인 수용/거부·매직바이트, 드라이런 분류 결정성·힌트 매핑, 게이트
   기본 폐쇄·프로바이더 키 검사, 오케스트레이터 해피패스/저신뢰 needs_review/실패 기록/
   미존재 업로드, 설정 기본값, 잡핸들러 등록, /me analysis 화이트리스트, 업로드 인큐) =
   **438 통과/26 스킵**. 실브라우저: 4레인·Newsreader·분석 배지·요약 렌더 확인, 콘솔 0.
7. **남은 것**: 라이브 개방 전 골든셋(파넬 실자료) 정확도 측정 — 그 시점에 Anthropic 라이브
   경로(fallbacks 파라미터 포함) 실검증 + 유형별 라이브 추출 프롬프트 확정. 07-17 이후
   Gemini 3.5 Pro 맞대결. docx/pptx/hwp 텍스트 추출 전처리. 운영자 needs_review 큐 화면.

## 0.0.22 파트너 허브 경화 스프린트 — 실DB 검증·보안·데이터·루프 완성 (2026-07-12) — 테스트 469 통과/26 스킵 (DB포함 495)

비판 리뷰(`outputs/briwell_partner_hub_critical_review_v0.md`)의 David 승인 작업 순서를
전부 실행. David 입력 0건 — 코드·공개데이터만으로 가능한 항목만.

1. **P9 실DB 검증**: 이 컴퓨터에 포터블 PostgreSQL 17.10 재구축(EDB 공식 바이너리,
   `work/` gitignore 경로 — 새 컴퓨터마다 로컬 구축 필요, `outputs/start_briwell_postgres_portable.ps1`).
   마이그레이션 001–012 + 시드 전체 적용·검증 통과. **왕복 검증 스크립트**
   `scripts/verify_partner_hub_roundtrip.py` 신설: 파트너 등록 → 토큰 → 업로드 → 인제스천
   워커 → (dedup·파일서빙·assemble) → 초안 → 제출 → 운영자 승인 → product_catalog 실존
   확인까지 실DB에서 전부 통과. 이 과정에서 **기존 DB-모드 버그 1건 발견·수정**:
   `app/repositories/outreach.py` update_status의 enum 파라미터 모호성(text vs
   outreach_status — psycopg AmbiguousParameter, RUN_DB_TESTS 재실행으로 노출) →
   `::outreach_status` 명시 캐스트.
2. **P1 토큰 경화** (마이그레이션 012): brand_partner_token **sha256-at-rest**(평문 저장
   폐지 — 발급 응답에서만 1회 노출), **expires_at 기본 90일**(`PARTNER_TOKEN_TTL_DAYS`,
   조회는 `expires_at > now()` fail-closed). 허브는 로드 즉시 `history.replaceState`로
   주소창·히스토리에서 `?t=` 제거 후 **Authorization: Bearer 헤더**로만 호출(백엔드는
   헤더·쿼리 모두 수용 — 새 링크 첫 진입은 쿼리). 마이그레이션이 평문 시절 활성 토큰을
   전부 revoke(재발급 1클릭). render.yaml·.env.example에 TTL 반영.
3. **P6+P2 파일**: 인증 파일 서빙 2종 — 파트너 `GET /partner-hub/uploads/{id}/file`(토큰,
   소유권은 쿼리 스코프 강제) + 운영자 `GET /partners/uploads/{id}/file`(RBAC). 항상
   `Content-Disposition: attachment`+`nosniff`+`no-store`, MIME은 확장자 화이트리스트
   (클라이언트 제공 content_type 불신). 허브 업로드 표에 **사진 미리보기**(blob→objectURL,
   토큰이 URL에 안 실림). **OOXML 매크로 차단**: docx/pptx/xlsx/hwpx ZIP을 실제 파싱해
   `vbaProject.bin` 포함 시 거부(대소문자 무시), 파싱 불가 ZIP도 거부. **동일 sha256
   파트너별 dedup**: 같은 파일 재업로드 시 기존 기록 반환(`status: duplicate` — 저장·재분석
   비용 0), 허브가 "중복 n건" 정직 표기.
4. **P3 성분 데이터**: EU CosIng 인벤토리 **28,703종**을 리포 시드로
   (`data/cosing_ingredients.csv` 1.7MB, 생성기 `scripts/build_cosing_seed.py`). 출처 정직
   기록: 신규 CosIng 사이트가 벌크 CSV 익명 제공을 중단해 **공식 CSV의 Internet Archive
   스냅샷(2020-12-30, 데이터 2020-12-15)** 사용 — 소스 URL·sha256·스냅샷 시각을 생성기와
   파일 헤더에 명기. `app/partners/cosing_data.py` 지연 로더(첫 정규화 때만 로드, 파일
   없으면 큐레이션 사전 단독으로 정직 동작). 정규화는 2계층: **큐레이션 시드 항상 우선**
   (철자·한글 별칭·기능) → CosIng 폴백, 퍼지는 첫 글자 버킷으로 28k에서도 빠름. 정규화
   결과에 dictionary 메타(큐레이션/cosing 수·버전) 동봉. 규제 룰은 큐레이션 유지(검증된
   LATAM 목록 확장은 별도 — 법적 검증 채널 필요, David).
5. **P5+P10 운영자 루프**: `GET /partners/drafts/{id}` **초안 상세**(전체 초안 + 원본
   파일별 AI 프로필(운영자는 model·error·extracted까지) + 결정 이력) — 대시보드 검수 큐에서
   행 선택 시 "초안 상세 · 원본 대조" 패널 렌더(완성도 구성요소 분해·규제 신호·전성분·
   원본 보기 버튼=blob 새 탭). `GET /partners/asset-profiles/attention` —
   **needs_review·failed 주의 큐**(회사·파일·오류·재분석/원본 버튼). `POST
   /partners/uploads/{id}/reanalyze` — 프로필 pending 리셋 + 잡 재인큐(실패 프로필 수동
   SQL 없이 복구). NUMERIC confidence는 float 직렬화(문자열 %truncation 버그 실브라우저에서
   발견·수정).
6. **P7 assemble**: `POST /partner-hub/assemble` + `app/partners/assemble.py` — done
   프로필에서 **카탈로그가 제품 열거를 소유**(성분표/가격표/사진은 이름 키 매칭으로 보강만,
   제품 발명 금지), 제품별 초안을 기존 enrich 파이프라인으로 N건 생성. 카테고리는 추측하지
   않고 빈 값(advisory). 이미 초안 있는 제품명은 스킵(반복 클릭 멱등). 허브 "분석된
   프로필로 일괄 초안 생성" 버튼 — 실브라우저에서 카탈로그 1부 → 초안 2건 생성 확인.
7. **P13 고지**: 허브 푸터에 제품 내 데이터 처리 고지(용도 한정·외부 AI 처리 가능성
   (Anthropic·Google)·원본 보존·삭제 요청 경로).
8. **검증**: 백엔드 **469 통과/26 스킵**(0.0.21 대비 +31), RUN_DB_TESTS=1 실DB 포함
   **495 통과/0 실패**, 대시보드 스모크 통과(신규 패널 고정 어서션 추가), 왕복 스크립트
   전 단계 통과, 실브라우저 검증(허브: 토큰 URL 제거·미리보기 blob 로드·assemble 2건·고지
   문구 / 대시보드: 검수 큐→상세 패널→쓰기 확인 모달→재분석 queued→워커 처리→주의 큐
   비움). 로컬 `.env`는 DB 모드로 전환(55432 포터블).
9. **남은 것(변동 없음, 전부 David 입력 필요)**: 골든셋(파넬 실자료) → 라이브 AI 개방·
   정확도 실측, 이메일 알림(발신 계정), 검증된 LATAM 규제 목록, 도메인/호스팅, 업로드
   외부 백업(R2). P8(알림)은 발신 계정 없이는 불가라 이번 스프린트에서 제외.

## 0.0.8 트렌드 탭 설계 결정 + 컴플라이언스 판단 (2026-07-07) — 코드 미작성

**A. 트렌드 신호 탭 (크리에이터 서치 하위) — 설계·미리보기 승인 대기, 아직 구현 안 함**
현재 discovery는 `app/discovery/planner.py`의 **키워드 시드 기반 정적 계획**뿐이라 "지금 누가 뜨는지"(모멘텀) 신호가 0. 이를 메우는 "트렌드" 서브탭 설계:
- **tier-1 (오늘 구현 가능, 합법)**: `creator_provided` 인테이크(크리에이터가 자기 통계·링크 제출) + 공개 구글 뉴스 RSS(K-beauty LATAM 쿼리) + oEmbed. tier-1 구현은 곧 **로드맵 우선순위 2(실데이터 유입) 그 자체**라 일석이조.
- **tier-2 (승인/계약 후 라이브)**: 틱톡 공식 API(`tiktok_official` 스켈레톤 존재), 라이선스 벤더(Data365/BrightData, `licensed_vendor` 스켈레톤). 동일 UI에 실데이터로 확장.
- **UI 컨셉**: 소스 레인 상태 바(라이브/대기 시각 구분) + KPI 스트립 + 뜨는 포맷 랭킹 + 공개 뉴스 + 모멘텀 상승 크리에이터 테이블(팔로워 컷오프 없음, 행별 "숏리스트" 연결). 미리보기 목업 제작 완료(대시보드 톤 동일).
- **판단**: 할 가치 확실. 단 Shopify 파일럿 라이브가 더 급하면 그 다음. 두 작업은 배타적이지 않음(트렌드 tier-1 = 실데이터 유입 겸함)이라 병행 가능.

**B. 컴플라이언스 판단 — tikwm 틱톡 우회 수집 거부 (재론의 금지)**
로컬 `trend-viewer` 도구의 틱톡 수집을 이식해달라는 요청이 2회 있었음(게이트 제거 요청 포함). `tikwm`은 틱톡의 X-Bogus·msToken 서명과 TLS 지문 검사를 **우회**하는 제3자 프록시라 비협상 제약 1(무단 스크래핑)·2(안티봇 우회)에 정면 위반. **거부함** — 코드(`app/core/policy.py`) 강제 규칙 위반이자 실사업 리스크(플랫폼 차단·제3자 의존). §0.3에서 이전 세션도 동일 판단(합법 경로만). 트렌드 기능은 위 tier-1/2 합법 레인으로 대체 구현 예정.

## 0.2 최고화 작업 — AI 품질·데이터 파이프라인 (2026-06-27)

"최고 결과"를 막는 병목을 겨냥해 5개 항목 구현(테스트 189통과/7스킵):

1. **AI Evaluation Harness**(`app/evals/creator_eval.py` + `data/golden/creator_eval_set_v0.json`) —
   라벨된 골든셋으로 AI 결정 정확도·과신(calibration_gap)을 측정. **라이브 검증으로 효과 입증**:
   Gemini가 `poor_no_beauty`를 conf 0.95로 오판하는 것을 harness가 포착(틀릴 때 confidence 0.95).
2. **프롬프트 보정**(`gemini.py` CALIBRATION_GUIDANCE) — 과신 억제·점수 앵커 주입. **측정으로 효과 확인**:
   라이브 점수 95/100/conf 0.95 → 82/50/15·conf 0.745로 변별력 확보.
3. **성과 피드백 루프**(`app/scoring/calibration.py`) — 실제 성과와 상관 높은 점수 차원에 가중치 재배분
   제안(상한 재분배로 합=1 유지). 인간 승인 전제(자동 적용 안 함).
4. **실 멀티모달**(`gemini.py` inlineData) — 영상 프레임 실제 이미지(base64)를 Gemini에 전송. 텍스트 설명만이 아닌 실제 화면 분석.
5. **Live Data Intake v1**(`app/operations/intake.py` + `POST /operations/intake-validate`) — 4개 소스 레인을
   단일 검증 계약으로: 정책 결정·필수컬럼·권장컬럼 커버리지·품질게이트. provider_scrape 레인 별도 표기.

다음 최고화 후보: harness 골든셋 확장·라이브 정기 측정, 성과 피드백 실데이터 연결, 멀티프로바이더 라우팅(아래 §3.4).

## 0.3 최신 상태 (2026-07-04) — 합법 provider 계층 + 재설계 결론

- **테스트 267 통과 / 7 스킵** (이전 195 → +72). 대시보드 한국어화·smoke 통과.
- **AI DM 개인화 생성**(gemini-3.5-flash 3-variant 스페인어, 템플릿 폴백), **실측 토큰 비용 관제**(usageMetadata→$2/일 캡),
  멀티모달·최종리뷰 체인 실행, **전역 예외 핸들러**·readiness 실측화 추가.
- **합법 데이터 인테이크 provider 계층**(`app/providers/`): `base.py`(ABC·정규화) + `registry.py` + 4개 provider —
  apify(provider_scrape·기본OFF), **creator_provided**(즉시 사용 가능), **tiktok_official**(공식 API dry-run 스켈레톤; 키·앱 승인 필요),
  **licensed_vendor**(Data365/BrightData·계약 게이트). 라우터 `/providers/status`·`/providers/{name}/discovery-runs`·`/providers/creator-provided/import`.
  마이그레이션 005로 DB CHECK 정합화. **무단 스크래핑/IP우회 없음**(사용자 요청했으나 거부, 합법 경로만).
- **재설계 패널(설계자3+심판2) 결론**: 경로 A(점진 격상, 재사용90%·10주·$80-140/월) **만장일치 승**. 다음 작업 = 로드맵 A
  (관리형 Postgres·OIDC 인증·Postgres 잡큐·감사 영속·rate limit·배포·**creator_provided로 실데이터 파일럿**).
- **모델 운용**: 계획/리뷰 Fable 5 · 구현 **Sonnet 5** · 기계작업 Haiku 4.5.

## 1. 현재 진행 상태 (정직한 평가)

### 1.1 동작 검증 결과 (로컬, 2026-06-27)
| 항목 | 결과 |
|---|---|
| 백엔드 테스트(pytest) | **176 통과 / 7 스킵**(DB 통합, `USE_DATABASE=false`라 스킵) |
| API 엔드포인트 | **48개** 정상 서빙, `/health` ok |
| 권한 인증(RBAC) | 작동(viewer 차단, admin 허용) |
| 대시보드 | 문법 검사·smoke 테스트 통과 |
| 데이터베이스 | 포터블 PostgreSQL 17.10 로컬 구동 가능(`127.0.0.1:55432`) |

### 1.2 성숙도 점수 (10점 만점, 코드 감사 기반)
| 영역 | 점수 | 메모 |
|---|---|---|
| 제품 워크플로우 | 8 | 발굴~정산 골격은 실제로 연결됨 |
| 컴플라이언스·안전장치 | 8 | 인간 승인 게이트·자동 DM 금지가 **코드로 강제됨** |
| 백엔드 API 구조 | 8 | 라우터·리포지토리·워커로 잘 분리 |
| 대시보드 완성도 | 7.5 | 운영자 화면은 있으나 의사결정 지표 보강 여지 |
| **프로덕션 준비도** | **5.5** | 인증·시크릿·rate limit·로깅 미완 |
| **실데이터 준비도** | **5** | 실제 크리에이터 데이터 유입 경로 미완 |

### 1.3 진짜 강점 (유지할 것)
1. **인간 승인 게이트·자동 DM 금지가 코드로 강제됨** — 아웃리치 상태머신(`app/workflows/outreach_status.py`)이
   `dm_sent`로 가려면 `approved` + claims_check 통과 + do-not-contact 확인 + 수동발송 확인을 모두 요구.
   DB 모드에선 라우터가 이 값들을 **저장된 레코드에서 재도출**(`app/routers/outreach.py:182-184`)해 클라이언트 우회 불가.
2. **프로덕션 게이팅 레이어 실재**(`app/core/readiness.py`) — 운영 전환 시 막아야 할 블로커를 정확히 열거.
3. **정책 모듈**(`app/core/policy.py`) — 허용/차단 source type을 allowlist로 관리, 테스트로 덮임.

### 1.4 알려진 격차·리스크 (정직)
| # | 격차 | 위치 | 심각도 |
|---|---|---|---|
| A | TikTok Apify 결과를 정직한 `provider_scrape`로 재분류 + 라이브 기본 OFF(법률 확인은 추후) | `app/providers/tiktok.py`, `app/core/policy.py` | ✅ 수정됨(2026-06-27, 법률 보류) |
| B | 오케스트레이션이 profile/comment/score 분석을 실제 실행하도록 배선 완료 | `app/operations/orchestration.py` | ✅ 수정됨(2026-06-27) |
| B' | 캠페인 매칭이 **시스템 산출 `final_score`** 우선 사용(operator 입력은 폴백). `score_source` 표기 | `app/operations/orchestration.py` | ✅ 수정됨(2026-06-27) |
| B'' | DM 생성기는 여전히 템플릿(이제 4 variant 전부 생성). 진짜 AI 개인화 생성은 후속 | `app/ai/dm.py` | 🟡 부분 |
| C | rate limit·전역 예외 핸들러·감사 로깅 **실구현 완료**(2026-07-05, P0). CSP·HSTS 헤더는 여전히 미부재 | `app/main.py`, `app/core/rate_limit.py`, `app/repositories/audit_events.py` | 🟢 대부분 수정(CSP/HSTS 잔여) |
| C' | readiness가 `security_headers_enabled`/`request_id_middleware_enabled`를 실측(app.state)으로 보고하도록 수정 | `app/core/readiness.py` | ✅ 수정됨(2026-06-27 이전) |
| C'' | OIDC 미인식 role → **403 거부로 변경**(조용한 viewer 강등 제거) | `app/core/auth.py` | ✅ 수정됨(2026-07-05, P0) |
| D | Gemini 모델 ID — `gemini-3-flash`→`gemini-3-flash-preview` 교정(ListModels 대조) | `app/ai/gemini.py` | ✅ 수정됨(2026-06-27) |
| E | `DmVariant` 4값 전부 생성하도록 수정 | `app/ai/dm.py` | ✅ 수정됨(2026-06-27) |

---

## 2. 시스템 구조 (무엇이 만들어졌나)

```
b2b-b2c-1-dm/
├─ work/briwell_mvp_app/      FastAPI 백엔드 (핵심)
│  └─ app/
│     ├─ routers/             48개 엔드포인트(creators, discovery, ai, campaigns, outreach, ...)
│     ├─ repositories/        DB 영속화 계층(USE_DATABASE=true일 때)
│     ├─ workers/             recent-20 스크린, multimodal, 스코어링 핸드오프
│     ├─ workflows/           아웃리치 상태머신
│     ├─ operations/          오케스트레이션(발굴~정산 일괄 실행)
│     ├─ compliance/          claims 검사, 국가 규칙(MX/PE/EC), 아웃리치 리뷰
│     ├─ ai/                  Gemini 어댑터, 스키마 검증, DM 초안
│     ├─ scoring/ ranking/    결정론적 스코어·랭킹
│     ├─ providers/           TikTok provider(Apify 등), K-beauty 키워드
│     └─ core/                config, db, auth, policy, readiness
│  ├─ db/migrations/          001 초기 스키마, 002 실행/추적 스키마
│  └─ tests/                  24개 테스트 파일(176통과)
├─ work/briwell_dashboard_app/  정적 운영자 대시보드(HTML/JS/CSS)
├─ outputs/                   27개 산출 문서(PRD·감사·리뷰·템플릿·SQL)
├─ docs/                      핸드오프·개발 노트
├─ HANDOFF.md / README.md     외부 개발자/AI 인계 문서
└─ render.yaml                Render 블루프린트(API+관리형 Postgres, 0.0.11에서 루트로 이전)
```

### 핵심 업무 흐름 (의도된 가치 루프)
발굴(discovery) → **최근 20개 게시물 스크린**(첫 적합성 게이트) → 전체 분석(프로필·댓글·멀티모달) →
스코어 → 캠페인 매칭 → DM 초안 → **인간 승인** → 수동 발송 기록 → 성과 추적 → 계약·정산.
※ 현재 "전체 분석" 단계는 실제 실행이 아니라 계획만 존재(격차 B).

---

## 3. 사용 AI 모델 / API / 외부 서비스

### 3.1 AI 모델 (코드 `app/ai/gemini.py:13-19` 기준)
| 용도(alias) | 모델 ID (2026-06-27 ListModels 검증) | 비고 |
|---|---|---|
| 저비용 텍스트 | `gemini-3.1-flash-lite` | ✅ 유효(non-preview) |
| 최종 리뷰 | `gemini-3.5-flash` | ✅ 유효(non-preview) |
| DM 생성 | `gemini-3-flash-preview` | ✅ 교정됨(기존 `gemini-3-flash` 미존재). 현재 DM은 템플릿이라 미사용 |
| 멀티모달 | `gemini-3-flash-preview` | ✅ 교정됨. `-preview`라 GA 전 재확인 권장 |
| 최근 게시물 스크린 | `gemini-3.1-flash-lite` | ✅ 유효 |

> 라이브 ListModels로 검증함. 기존 `gemini-3-flash`는 실재하지 않아 라이브 호출 시 404가 발생했을 항목 →
> `gemini-3-flash-preview`로 교정. `-preview` 모델은 GA 모델로 교체 가능하므로 프로덕션 전 재확인 권장.
> dry-run으로 돌면 모델 호출 자체가 없어 영향 없음.

### 3.2 외부 API / 데이터 provider
| 서비스 | 용도 | 상태 | 비고 |
|---|---|---|---|
| **Google Gemini** | 크리에이터 AI 분석·스크린 | 키 설정됨, 라이브 ON | `generativelanguage.googleapis.com/v1beta` |
| **Apify** (`clockworks/tiktok-scraper`) | TikTok 크리에이터/영상 수집 | 토큰 설정됨, 라이브 **기본 OFF** | `provider_scrape`로 정직 분류. 법률/ToS 확인 추후 |
| Data365 | TikTok 대안 provider | **미설정**(스켈레톤만) | 프로덕션 후보 |
| Bright Data | TikTok 확장 provider | **미설정** | 스케일 대안 |
| TikAPI | TikTok 실험 provider | **미설정** | 리스크 높음 |
| OpenAI | (사용 안 함) | 키 비어있음 | 코드 미사용 |

### 3.3 기술 스택
- 백엔드: **FastAPI** + Pydantic v2, psycopg(PostgreSQL), httpx, PyJWT(OIDC용), uvicorn
- DB: **PostgreSQL 17.10**(로컬은 포터블, 프로덕션은 managed 예정)
- 프론트: 순수 HTML/CSS/JS(빌드 없음) + 스모크 테스트(node)
- 배포(준비 완료, 실행 대기): **Render.com**(루트 `render.yaml` 블루프린트 + `docs/DEPLOY_RENDER.md` 런북), Supabase Auth/OIDC(런북 1단계)

---

### 3.4 Gemini 모델 평가 + 타 AI API 비교 (2026-06, 웹조사 기준)

**현재 설정은 합리적인 티어링.** 고볼륨 단계엔 최저가, 최종 판단엔 프리미엄을 씀:

| 용도 | 모델 | 입력/출력($/1M) | 평가 |
|---|---|---|---|
| 스크린·프로필(고볼륨) | gemini-3.1-flash-lite | $0.25 / $1.50 | ✅ 최저가·최고속, 깔때기 입구에 적합 |
| 최종 리뷰(소수·중요) | gemini-3.5-flash | $1.50 / $9.00 | 프리미엄. 비용 민감 시 3-flash-preview로 하향 가능 |
| 멀티모달·DM | gemini-3-flash-preview | $0.50 / $3.00 | 중간 티어 |

**가성비·성능 비교 (경쟁 모델, $/1M in·out):**

| 모델 | 입력/출력 | 강점 | 약점 |
|---|---|---|---|
| **Gemini 3.1 Flash-Lite** | $0.25/$1.50 | 최저가급·최고속·**네이티브 영상/오디오/PDF** | 품질 약간 하위 |
| Gemini 3.5 Flash | $1.50/$9.00 | 프런티어 성능·1M 컨텍스트·네이티브 멀티모달 | 출력 비쌈(가격 상승) |
| GPT-5.4 Mini | $0.75/$4.50 | **품질 최상위**(벤치 1위)·범용 | 텍스트·이미지만(영상 X) |
| Claude Haiku 4.5 | $1.00/$5.00 | 에이전트/툴·캐시 프롬프트 강함 | 텍스트·이미지만(영상 X) |
| DeepSeek V4 | $0.30/$0.50 | **초저가** 대량 분류 | 품질 최하위·지연 |

**판정 — 이 용도(LATAM TikTok 크리에이터 영상 분석, 고볼륨, 스페인어)엔 Gemini가 최적의 primary:**
1. **결정적 이유 = 네이티브 영상 멀티모달**. ④의 실제 영상 프레임 분석은 Gemini만 네이티브 지원(GPT·Claude는 텍스트+이미지만). 제품 핵심이 "영상 콘텐츠 평가"라 이게 승부처.
2. 속도 1위(고볼륨 스크린에 유리) + Flash-Lite 최저가급 + 무료 티어.
3. 단점: 순수 텍스트 판단 품질은 GPT-5.4 Mini·Haiku가 3~7%p 우위, Gemini Flash 출력가 상승 추세.

**최고 시스템을 위한 권고 = 멀티프로바이더 라우팅** (`ai_model_config` 테이블이 google/openai/anthropic 이미 지원):
- 멀티모달·스크린 → **Gemini**(네이티브 영상·속도·가격)
- 최종 리뷰처럼 미묘한 텍스트 판단 → **GPT-5.4 Mini 또는 Claude Haiku**(품질 우위) 후보
- 초대량 1차 분류 → **DeepSeek V4**(초저가)
- 공통 절감: **Batch API -50%, 컨텍스트 캐싱 -90%** 적용

출처: [metacto](https://www.metacto.com/blogs/the-true-cost-of-google-gemini-a-guide-to-api-pricing-and-integration), [artificialanalysis](https://artificialanalysis.ai/articles/gemini-3-5-flash-everything-you-need-to-know), [respan](https://www.respan.ai/blog/fast-model-comparison), [tokenmix](https://tokenmix.ai/blog/gpt-5-4-mini-vs-claude-haiku), [intuitionlabs](https://intuitionlabs.ai/articles/ai-api-pricing-comparison-grok-gemini-openai-claude).

## 4. 비용 구조 & 가드레일

> **정직한 전제**: 아래는 코드/`.env`에 **설정된 상한선**과 과금 구조이며, "실제 청구된 금액"이 아님.
> 현재 파이프라인은 대부분 **dry-run** 기본값이라 **실제 AI 과금은 사실상 $0**에 가깝습니다.

### 4.1 설정된 비용 가드레일 (`.env` 기준)
| 항목 | 값 | 의미 |
|---|---|---|
| `AI_LIVE_DAILY_CALL_LIMIT` | 20 | Gemini 라이브 호출 하루 20회 상한 |
| `AI_LIVE_DAILY_COST_LIMIT_USD` | **$2.00** | Gemini 하루 비용 상한 |
| `AI_LIVE_PER_CREATOR_DAILY_CALL_LIMIT` | 3 | 크리에이터당 하루 3회 |
| `TIKTOK_PROVIDER_DAILY_RESULT_LIMIT` | 2000 | Apify 결과 하루 2,000건 상한 |
| `AI_DRY_RUN` | false | (현재 라이브 허용 상태) |
| `ALLOW_LIVE_PROVIDER_CALLS` | true | (현재 라이브 허용 상태) |

### 4.2 실제 과금이 발생하는 곳 (운영 시)
| 비용원 | 과금 방식 | 현재 |
|---|---|---|
| Google Gemini | 토큰당(Flash 계열=저비용) | dry-run이라 실과금 거의 없음 |
| Apify TikTok 스크래퍼 | 결과/컴퓨트 단위 | 게이트로 통제, 잔액 충전 시 발생 |
| Render.com 호스팅 | 인스턴스/시간 | 배포 전(미발생) |
| Managed PostgreSQL | 인스턴스/스토리지 | 미연결(미발생) |
| **Claude/Anthropic**(개발용) | 사용자 구독(Pro) | 본 개발 세션과 별개 |

> 정확한 단가는 각 서비스 가격표 기준으로 확인 필요. 핵심은 **모든 라이브 호출에 일일 상한이 코드로 걸려 있어
> 폭주 비용이 구조적으로 차단**된다는 점.

---

## 5. 컴플라이언스 / 안전 정책 (비협상 제약)

`HANDOFF.md` 기준 — 코드가 지켜야 하는 절대 규칙:
1. 무단 TikTok 스크래핑 금지  ← Apify lane은 `provider_scrape`로 정직 분류 + 기본 OFF. 법률/ToS 확인은 추후(차선 전환 가능)
2. CAPTCHA 우회 금지
3. 외부 DM 자동 발송 금지  ← ✅ 코드로 강제됨(강점)
4. High Risk / Not Allowed source 레코드를 유효 입력으로 처리 금지
5. 승인 source type만 허용: `manual`, `official_api`, `approved_provider`, `creator_provided`
6. 국가 컴플라이언스 규칙은 법률 자문이 아님(운영 안전장치)
7. 모든 수동 아웃리치 상태 전환 전 인간 승인 필수  ← ✅ 코드로 강제됨(강점)

---

## 6. 향후 목표 / 로드맵 (우선순위)

| 순위 | 목표 | 분류 | 효과 | 노력 |
|---|---|---|---|---|
| 1 | **전체 분석 체인을 오케스트레이션에 실제 배선** (profile→comment→multimodal→스코어 핸드오프). `final_score`를 **시스템이 산출** | 제품 핵심 | "내부 MVP→실운영 도구" 전환 | L |
| 2 | **Live Data Intake v1** — 승인 provider/CSV/creator-provided 실데이터 유입 + 업로드 검증 리포트 | 제품 | 데모→운영 | M~L |
| 3 | **TikTok Apify lane 정직 분류** 또는 ToS-적합 provider 전환(사업/법무 결정 필요) | 컴플라이언스 | 비협상 제약 해소 | M |
| 4 | **보안 보강** — rate limit + 전역 예외 핸들러 + 감사 로깅 추가, security-policy 문서를 코드와 일치 | 보안 | 프로덕션 전제 | M |
| 5 | **Gemini 모델 ID 검증·수정** 후 라이브 스모크 1회 | 버그 | 라이브 동작 보증 | S |
| 6 | **Production Auth** — 헤더 RBAC → Supabase Auth/OIDC | 보안 | 실배포 전제 | M |
| 7 | **Managed PostgreSQL 전환** + 전체 업무 플로우 E2E | 인프라 | 프로덕션 | M |
| 8 | **대시보드 Executive Layer** — 캠페인 의사결정 지표(파이프라인 예측·예산·단계 aging·승인 SLA) 전면화 | UX | 운영자 가치 | M |
| 9 | DmVariant 폴백·프롬프트 인젝션 가드 등 정합성 | 폴리시 | 품질 | S |

**가장 효과 큰 다음 작업**: 순위 1(전체 분석 체인 배선) + 순위 2(실데이터 유입). 이 둘이 되는 순간
콘솔이 "데모"가 아니라 "운영 도구"로 전환됨 (품질 감사 문서의 자체 권고와 일치).

---

## 7. 실행 방법 (로컬)

### 백엔드
```powershell
cd work\briwell_mvp_app
python -m venv .venv          # 최초 1회
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8030 --reload
# API 문서: http://127.0.0.1:8030/docs
```

### 대시보드
```powershell
cd work\briwell_dashboard_app
python -m http.server 8070
# 대시보드: http://127.0.0.1:8070  (API 없으면 Preview 모드로 폴백)
```

### 테스트
```powershell
cd work\briwell_mvp_app
.venv\Scripts\activate
pytest -q                      # 176 통과 / 7 스킵
cd ..\briwell_dashboard_app
node tests\smoke.mjs
```

---

## 8. 저장소 / 핵심 파일 위치

- **GitHub**: `https://github.com/DavidAction/briwell-creator-commerce.git` (origin/main 추적)
- **로컬**: `C:\Users\bynay\Documents\Codex\2026-06-17\b2b-b2c-1-dm`
- 먼저 읽을 문서: `HANDOFF.md`, `README.md`, `outputs/briwell_mvp_v0_1_prd.md`,
  `outputs/briwell_quality_upgrade_audit_v0.md`, `outputs/briwell_cloud_stack_execution_plan_v0.md`
- ⚠️ 업로드 시 제외할 무거운 폴더: `work/postgres_data`(76MB), `work/briwell_mvp_app/.venv`(75MB)

---

*문서 끝. 이 브리핑은 코드 직접 검증 기반이며, ⚠️ 표시 항목은 라이브 전환 전 재확인이 필요합니다.*
