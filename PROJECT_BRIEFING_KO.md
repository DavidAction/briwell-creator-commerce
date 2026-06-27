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
| C | **rate limit·전역 예외 핸들러·CSP·HSTS·감사 로깅 전부 부재**인데 `/ops/security-policy`는 "감사 로깅 영속화"를 단언 | `app/main.py` | 🟡 보안 |
| C' | readiness가 `security_headers_enabled`/`request_id_middleware_enabled`를 **하드코딩 True**로 보고(실측 안 함) | `app/core/readiness.py:57-58` | 🟡 |
| C'' | OIDC 경로 미검증(테스트가 monkeypatch), 미인식 role을 거부 대신 **조용히 viewer로 강등** | `app/core/auth.py:189` | 🟡 |
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
└─ render.yaml                Render.com 배포 설정(예정)
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
- 배포(예정): **Render.com**(`render.yaml`), Supabase Auth/OIDC(예정)

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
