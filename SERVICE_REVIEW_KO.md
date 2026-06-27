# Briwell 서비스 평가 보고서 & 리뷰 (한국어)

작성일: 2026-06-27 · 작성: Claude Code (소스 직접 검증·라이브 테스트 기반) · 테스트 189 통과/7 스킵

---

## 1. 서비스 한 줄 정의 & 주요 역할

**Briwell Creator Commerce Intelligence** — 한국 화장품(K-beauty)을 **라틴아메리카(멕시코·페루·에콰도르)** 에
파는 Briwell을 위해, 뷰티 크리에이터를 **발굴 → 평가 → 검수 → 섭외 → 성과추적 → 정산**까지 한 화면에서
운영하는 **크리에이터 커머스 운영 콘솔(MVP)**.

주요 역할 3가지:

1. **AI 필터** — 안전한 데이터로 "캠페인에 맞는 크리에이터"를 걸러내는 깔때기(최근 20개 게시물 스크린 + 7차원 점수).
2. **안전벨트** — 스크래핑·DM 자동발송·화장품 클레임 규제를 **코드와 DB로 강제**하는 컴플라이언스 게이트.
3. **운영 워크플로우** — 발굴부터 정산까지 전 과정을 하나의 흐름으로 묶는 오퍼레이션 레이어.

## 2. 무엇을 하는가 (전체 흐름)

```
데이터 인테이크 검증 → 최근 20개 게시물 스크린(첫 적합성 게이트) → 전체분석(프로필+점수, AI)
 → 캠페인 매칭(시스템 산출 점수) → DM 초안 → 인간 승인 → 수동 발송 기록 → 성과 롤업 → 계약·정산
```

이 전 과정을 한 번의 API 호출(`POST /operations/acquisition-orchestration`)로 일괄 실행할 수 있습니다.

## 3. 주요 기능

- **백엔드(FastAPI)**: 49개 API 엔드포인트 — 발굴·키워드·크리에이터·영상·댓글·AI잡·캠페인·아웃리치·컴플라이언스·성과·정산·운영준비
- **운영자 대시보드**: Creator Discovery · Talent Intelligence · Campaign Studio · Brand Safety Desk · Performance Analytics · Contracts & Payouts
- **AI 분석(Google Gemini)**: 최근20 스크린 · 프로필 · 멀티모달(영상 프레임 실제 이미지) · 최종리뷰
- **결정론적 스코어링**: 7개 차원(뷰티적합·인게이지먼트·지역성·커머스의도·콘텐츠품질·협업확률·비용효율) + 세그먼트
- **컴플라이언스 게이트**: 소스 allowlist · 클레임 검사 · 국가 규칙(MX/PE/EC) · do-not-contact · 인간 승인 · 자동 DM 금지 — **DB 레벨 트리거까지 이중 방어**
- **AI 평가 harness** *(신규)*: 라벨된 골든셋으로 AI 결정 정확도·과신 측정
- **성과 피드백 루프** *(신규)*: 실제 성과와 상관 높은 차원에 가중치 재보정 제안(인간 승인 전제)
- **데이터 인테이크 검증** *(신규)*: 4개 소스 레인 단일 검증(`POST /operations/intake-validate`)
- **데이터베이스**: PostgreSQL 스키마·마이그레이션·시드·인덱스·뷰, 로컬 포터블 PostgreSQL 17.10

## 4. 객관적 평가

**한 줄 평가**: 정책 게이트 + 테스트(189통과) + **AI 품질 측정장치**까지 갖춘 "운영 가능한 고급 MVP".
다만 실제 인플루언서 데이터·운영용 인증·프로덕션 인프라는 아직 미완이라, 정확히는 "내부 검증용 운영 도구" 단계.

| 영역 | 점수(10) | 메모 |
|---|---|---|
| 제품 워크플로우 | 8.5 | 발굴~정산 전 과정이 실제로 연결·실행됨 |
| 컴플라이언스·안전 | 8.5 | 앱+DB 이중 강제, 비협상 제약 준수 |
| API·DB 구조 | 9 | ENUM·CHECK·FK·트리거·인덱스·뷰 완비, SQL 인젝션 안전 |
| AI 품질 | 6.5 | 라이브 작동 + **측정 가능해짐**(harness), 다만 보정 여지 |
| 대시보드 완성도 | 7.5 | 운영 화면 존재, 의사결정 지표 강화 여지 |
| 프로덕션 준비 | 5.5 | 인증·rate limit·감사로깅·시크릿 매니저 미완 |
| 실데이터 준비 | 5 | 실 크리에이터 데이터 유입 경로 미완 |

## 5. 장점 / 단점

**장점**
1. 컴플라이언스를 **말이 아니라 코드+DB 구조로** 강제(인간 승인·자동 DM 금지·위험소스 차단).
2. 캠페인 점수가 **시스템 산출 + 출처 투명**(`score_source`) — operator가 점수를 조작해 통과시킬 수 없음.
3. AI 품질을 **객관적으로 측정**(골든셋 harness) — "좋아졌는지"를 숫자로 확인 가능.
4. Gemini 라이브 AI가 **실제로 작동함**을 검증(모델 ID 교정 완료).
5. 테스트 189개로 회귀 방어.
6. 켜기/끄기 바로가기 + 다른 PC 셋업 자동화로 운영 편의 확보.

**단점 (정직)**
1. 실제 크리에이터 데이터가 아직 **0** (합성/dry-run 중심).
2. DM이 **정적 템플릿**(진짜 AI 개인화 생성은 후속).
3. 인증이 **개발용 헤더 RBAC** (OIDC 실연결 미완).
4. **rate limit·감사 로깅·전역 예외 핸들러** 미완(프로덕션 전제).
5. Apify가 **FREE 플랜**(스케일 한계) + 스크래핑 **법률/ToS 확인 보류**.
6. 국가 규칙 **12개로 얇음**(실 규제 룰셋 필요).
7. 멀티모달 코드는 완성됐으나 **실제 영상 자산 수집 파이프라인 미연결**.

## 6. 이 서비스로 나올 수 있는 결과

**지금 가능(데모·검증 단계)**
- 합성/제공 데이터로 발굴→스크린→점수→매칭→DM초안→성과→정산 **전 과정 시연**.
- AI 결정 품질의 **정확도·과신 객관 측정**(예: 라이브 Gemini가 부적합 크리에이터를 confidence 0.95로 오판하는 것을 harness가 포착).
- 컴플라이언스 위반 입력(스크래핑·고위험 소스·규제 클레임)의 **자동 차단** 시연.

**실데이터 연결 시 가능(운영 단계)**
- MX/PE/EC 실제 크리에이터 후보 **랭킹 + 적합도 점수**.
- 브랜드 세이프티 **자동 1차 필터**(위험 콘텐츠 사전 차단).
- 캠페인별 **파이프라인·성과·ROAS 추적**.
- 정산 가드(**인보이스/세금문서 확인 전 지급 차단**).

**아직 안 되는 것 (정직)**
- 실제 DM **자동 발송**(의도적으로 금지 — 수동 발송 기록만).
- 실시간 **대량 스크래핑**(법률/ToS 확인 보류, 라이브 기본 OFF).
- 프로덕션 멀티테넌트·실인증 운영(아직 내부 검증용).

## 7. 사용 방법 (구체)

**A. 켜기** — 바탕화면 **"Briwell 켜기"** 더블클릭 → API·대시보드 두 창이 뜨고 브라우저에 대시보드 자동 오픈.
(또는 프로젝트 폴더의 `START_Briwell.bat`)

**B. 접속 주소**
- 대시보드: `http://127.0.0.1:8070`
- API 문서(Swagger): `http://127.0.0.1:8030/docs`

**C. 전형적 작업 순서**
1. **데이터 인테이크 검증** — `POST /operations/intake-validate` (소스/필수컬럼/품질 사전 점검)
2. **최근 20 스크린** — `POST /analysis-jobs/run-recent-posts-screen` (첫 적합성 게이트)
3. **일괄 오케스트레이션** — `POST /operations/acquisition-orchestration` (스크린~매칭~아웃리치~정산 한 번에)
4. 매칭 결과 확인 → DM 초안 → `POST /outreach/claims-check` → 리뷰 승인 → 수동 발송 기록
5. 성과 입력 → 성과 롤업

> 권한 헤더: `X-User-Role: admin | operator | campaign_manager | viewer` (개발 모드). viewer는 읽기만.

**D. AI 품질 측정(harness)** — 백엔드 폴더에서:
```powershell
.venv\Scripts\python.exe -c "from app.evals.creator_eval import compare_modes; import json; print(json.dumps(compare_modes(), ensure_ascii=False, indent=1))"
```
골든셋을 dry-run(휴리스틱) vs 라이브 Gemini로 비교해 정확도·과신을 출력.

**E. 끄기** — 바탕화면 **"Briwell 끄기"** 더블클릭 (또는 `STOP_Briwell.bat`).

## 8. 켜고 끄기 바로가기

| 위치 | 켜기 | 끄기 |
|---|---|---|
| **바탕화면** | `Briwell 켜기` | `Briwell 끄기` |
| 프로젝트 폴더 | `START_Briwell.bat` | `STOP_Briwell.bat` |

검증됨: 켜기 → API/대시보드 HTTP 200, 끄기 → 두 서버 프로세스 종료(연결 거부 확인).

## 9. 다른 컴퓨터에서 사용

자세한 내용은 `docs/USE_ON_OTHER_COMPUTER.md`. 요약:

1. **사전 설치**: Git, Python 3.11+ (Node.js는 대시보드 검증용 선택)
2. **클론**:
   ```powershell
   git clone https://github.com/DavidAction/briwell-creator-commerce.git
   cd briwell-creator-commerce
   ```
3. **1회 셋업**(venv·의존성·.env 생성):
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
   ```
4. **실행**: `START_Briwell.bat` 더블클릭 (또는 `scripts\start_local_stack_windows.ps1`)

> ⚠️ **API 키 주의**: `.env`의 Gemini·Apify 키는 보안상 git에 포함되지 않습니다. 새 PC에서는 기본적으로
> **dry-run(안전 모드)** 으로 동작합니다. 라이브 AI를 쓰려면 새 PC의 `work\briwell_mvp_app\.env`에 본인 키를 넣으세요.
> 데이터베이스 없이도 동작합니다(`USE_DATABASE=false` 기본).

---

*본 보고서는 코드 직접 검증·라이브 테스트 기반입니다. 추가 맥락은 `PROJECT_BRIEFING_KO.md` 참조.*
