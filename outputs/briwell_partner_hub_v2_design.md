# 브랜드 파트너 허브 v2 설계 — 서체 · 기타 레인 · AI 인제스천

작성 2026-07-12 · 상태: **모델 최종 확정만 대기** (Phase 1 = briefing 0.0.20 완료 기준)

> David 확정 (2026-07-12): ① 서체 = **Newsreader, 허브만** ② 기타 레인 = **문서만**
> (docx·pptx·hwp·hwpx·txt) ③ 분석 시점 = **업로드 즉시 자동**(잡큐 비동기).
> ④ 모델은 "26-07-12 기준 최고 성능으로 재제안" 지시 → §4 재작성(Claude Opus 4.8 +
> Fable 5 에스컬레이션 권장). 이 항목 확정 즉시 구현 착수.

David 지시 3건: ① 서체 후보 2번 적용 ② 사진/PDF/자료 외 **기타 자료** 업로드 ③ 업로드가
DB에 저장될 때 **AI가 자동 분석·분류해 우리에게 최적화된 형식**으로 저장 + 모델 추천.

---

## 1. 서체 — 후보 2번 = Newsreader

쇼케이스(`work/briwell_brand/logo-card-concepts.html`) 순서 기준:
**1 Fraunces(현재) · 2 Newsreader · 3 Playfair Display · 4 Cormorant Garamond · 5 Sora ·
6 Manrope · 7 Space Grotesk.** → 2번 = **Newsreader** (에디토리얼 · 지적이고 단정한 신문
세리프)로 해석. **다른 번호를 의미했다면 확인 시 정정 요청.**

**적용 설계 (허브 한정 권장):**
- 파트너 허브의 디스플레이 계층(워드마크 로고, h1, 카드 제목 `.draft-title`, 점수 숫자
  `.score`, 상태 화면 h2)을 Fraunces → **Newsreader**로 교체. Google Fonts 로드 1줄 교체.
- 본문은 Noto Sans KR 유지(라틴 세리프 헤딩 + 한글 산세리프 본문은 KO 페이지 하우스 페어링).
- **범위 판단**: 0.0.16 결정이 "로고·서체는 추후"이므로 이번 적용은 허브 신규 표면에서의
  실사용 테스트 성격. 랜딩·포털·대시보드·로고 SVG 전개는 **브랜드 서체 최종 확정 때**
  일괄(별도 작업, 홈페이지 테마 투표와 함께 묶는 것을 권장). 전 표면 즉시 적용을 원하면
  범위를 넓혀 진행.

## 2. 기타(etc) 업로드 레인

3레인에 안 들어가는 실무 자료: 회사소개서(PPTX/DOCX), **HWP/HWPX**(한국 브랜드사 표준),
인증서·시험성적서 사본, 보도자료, 영상 소재.

- `kind='etc'` 추가 (migration 011에서 CHECK 제약 확장: photo/pdf/data/etc).
- **허용 확장자(화이트리스트 유지 — 실행파일·스크립트는 구조적으로 차단):**

| 그룹 | 확장자 | 매직바이트 검사 |
|---|---|---|
| 오피스 문서 | .docx .pptx | `PK\x03\x04` (OOXML zip) |
| 한컴 | .hwp | OLE compound `D0 CF 11 E0` / `HWP Document File` 시그니처 |
| 한컴 신형 | .hwpx | `PK\x03\x04` |
| 텍스트 | .txt | NUL 바이트 없음 + 디코딩 가능(UTF-8/CP949) |
| 영상(결정 필요) | .mp4 .mov | `ftyp` 박스 / QuickTime 시그니처 |

- 크기 상한: 문서는 기존 15MB 유지. **영상 포함 시** `PARTNER_UPLOAD_VIDEO_MAX_BYTES`
  (기본 200MB) 별도 상한 + 영상은 AI 분석 대상에서 제외(Phase 1은 메타데이터만 기록 —
  프레임 추출 분석은 후순위). **영상 포함 여부가 결정 포인트.**
- zip 등 압축 파일은 중첩 검사 비용·위험(zip bomb, 이중 확장자) 때문에 **제외 권장**
  (필요해지면 Phase 3에서 서버측 해제·재검사 설계로).
- UI: 4번째 레인 카드 "기타 자료 (소개서·인증서·HWP)" 추가. 파트너 허브·대시보드 문구 갱신.

## 3. AI 인제스천 — 업로드 즉시 자동 분석·분류·정규화 저장

**현재(Phase 1)**: 업로드 = 원본 저장만. 추출은 파트너가 파일을 골라 수동 실행, 결과는 제품
초안 1개. **v2**: 업로드가 저장되는 순간 자동으로 분석 파이프라인이 돌아 "우리에게 최적화된
형식"(아래 스키마)으로 DB에 쌓인다. 운영자는 정리된 프로필을 받고, 제품 초안은 프로필에서
조립된다.

```
업로드 저장(원본 보존·sha256)                              …기존
  → job_queue에 partner_asset_ingest 잡 등록(비동기)        …기존 006 잡큐/워커 재사용
  → [1] 분류(classify): 문서 유형·언어·브랜드·제품 언급·품질/판독성·요약(KO)
  → [2] 유형별 추출(route & extract):
        product_catalog   → 제품 후보 목록(복수) + 페이지 매핑 + 제품별 속성
        ingredient_list   → 제품별 INCI 리스트 → 기존 정규화·규제 스크리닝 즉시 연결
        price_list        → 제품×규격×공급가/소비자가 테이블
        certificate       → 인증 종류·발급기관·대상 제품·유효기간
        brand_intro       → 회사 개요·연혁·수출 이력·채널
        press / other     → 요약 + 키워드만
        (photo 레인)      → 배경 유형(흰배경/연출)·해상도 적합성·제품 매칭 후보
        판독 불가/저신뢰    → doc_type = needs_review → 운영자 큐
  → [3] 정규화 저장: partner_asset_profile (migration 011)
  → [4] 조립(assemble): 프로필이 쌓이면 제품 초안 자동 제안 — 카탈로그의 제품 N개 ×
        성분표 × 가격표를 제품 단위로 묶어 기존 draft 파이프라인(검증·스코어)에 투입.
        파트너 확인 → 운영자 승인 게이트는 그대로(자동 확정 없음).
```

**저장 스키마 (migration 011):**

```
partner_upload.kind CHECK에 'etc' 추가
partner_asset_profile (
  id UUID PK, upload_id FK(UNIQUE — 업로드당 최신 프로필 1개, 재분석은 교체),
  partner_id FK(조회 편의 비정규화),
  doc_type TEXT CHECK (product_catalog|ingredient_list|price_list|certificate|
                       brand_intro|press|photo_asset|video_material|other|needs_review),
  language TEXT, confidence NUMERIC,
  summary_ko TEXT,                    -- "AI 요약" 라벨과 함께만 노출
  extracted JSONB,                    -- 유형별 스키마(버전 필드 포함)
  products_mentioned TEXT[],
  status TEXT CHECK (pending|processing|done|failed),
  error TEXT, model TEXT, prompt_version TEXT, usage JSONB,
  created_at, updated_at
)
인덱스: (partner_id, doc_type), status
```

**실행·안전 설계 (전부 기존 하우스 패턴 재사용):**
- 비동기: `JOB_HANDLERS`에 `partner_asset_ingest` 등록. 워커는 `OUTBOX_WORKER_ENABLED`
  게이트 그대로. 업로드 응답은 즉시 반환, UI에 "분석 중 → 완료(유형 배지+요약)" 상태 표시.
  워커 꺼짐/DB 꺼짐이면 프로필 status=pending으로 정직하게 남고 업로드는 성공(원본 보존).
- AI 게이트: `PARTNER_AI_DRY_RUN`(기본 true) + `ALLOW_LIVE_PARTNER_AI_CALLS` 듀얼 게이트
  그대로. 드라이런 = 파일명·해시 기반 결정적 분류 샘플(테스트·오프라인 동작).
- 비용 상한: 자동 실행은 라이브 비용을 낳으므로 `PARTNER_AI_DAILY_CALL_LIMIT`(기본 100)·
  `PARTNER_AI_DAILY_COST_LIMIT_USD`(기본 2.00) — 기존 AI_LIVE_DAILY_* 관례의 파트너판.
  한도 초과 시 잡은 pending 유지(다음 날 재개), 파트너 UI에는 "분석 대기 중".
- 정직성: confidence 임계(초기 0.7) 미만 → needs_review + 운영자 큐. 요약·추출값은 항상
  "AI 분석" 라벨. 실패는 failed + 사유 저장, 원본으로 언제든 재분석.
- 호출 감사: 이 레인은 model·prompt_version·usage를 **profile 자체에 기록**(자기완결 감사).
  중앙 ai_invocation_log 통합은 라이브 개방 시점 항목(분석잡 FK 관례에 맞춰 배선).

## 4. AI 모델 — 2026-07-12 기준 최고 성능 구성 (David 지시로 재제안)

용도를 정확히 하면: 우리 병목은 순수 OCR이 아니라 **구조화 필드 추출** — 카탈로그 PDF에서
제품 속성, 성분표에서 INCI 리스트, 가격표에서 표 데이터를 스키마에 맞게 뽑는 정확도다.
2026-07 기준 공개 벤치마크 지형: 필드 추출은 Claude 리드(≈97.6% vs Gemini ≈93.8%), 문서가
길수록 격차 확대(50p+ 분할에서 5-8pt). 순수 스캔 OCR·대량 처리 비용은 Gemini 3계열 우세.

| 선택지 | 강점 (우리 용도 기준) | 약점 | 판정 |
|---|---|---|---|
| **Claude Opus 4.8** ← 권장 기본 | 구조화 추출 정확도 최상급 계열, **고해상도 비전 2576px**(성분표 스캔의 작은 INCI 글씨), **structured outputs**(JSON 스키마 강제 — 파싱 실패 원천 차단), PDF 네이티브, 1M 컨텍스트(카탈로그 통째) | $5/$25 per MTok — Gemini Flash급 대비 비쌈 | ◎ |
| **Claude Fable 5** ← 최고난도 에스컬레이션 | 현존 최고 성능 모델. 특히 **열화 이미지 판독**(흐릿·기울어진·구겨진 라벨 스캔)에 특화 학습 — 실물 성분표 사진에 직결 | $10/$50. 안전 분류기 refusal 가능(→ 서버사이드 fallbacks로 Opus 4.8 자동 폴백 내장). 30일 데이터 보존 요건 | ○ (선별) |
| Claude Sonnet 5 | Opus 근접 품질, $3/$15(2026-08-31까지 $2/$10) | 최고 성능 요구에는 한 단계 아래 | 물량 확장 시 |
| Gemini 3.1 Pro / 3 Flash | 대량 처리 비용 최적, 순수 OCR 강함, 기존 어댑터 재사용 | **구조화 필드 추출에서 Claude에 열세** — 우리 병목 지점 | 분류(1단계)만 하이브리드 후보 |

**권장: Claude Opus 4.8 기본 + Claude Fable 5 에스컬레이션 슬롯.**
- `PARTNER_AI_PROVIDER=anthropic` + `PARTNER_AI_MODEL`(기본 `claude-opus-4-8`) /
  `PARTNER_AI_ESCALATION_MODEL`(기본 비활성, 지정 시 `claude-fable-5`) — 신뢰도 임계 미달
  문서만 에스컬레이션. Fable 5 경로에는 refusal 대비 서버사이드 fallbacks(Opus 4.8) 동봉.
- **비용 감각**: 30p 카탈로그 1건 ≈ Opus 4.8 약 $0.4~0.6(600~800원), Fable 5 약 2배.
  파일럿 월 수십 건 = **월 수만 원 이내** — 최고 성능을 선택해도 부담이 사실상 없음.
  인제스천이 비동기 잡큐라 **Batch API(50% 할인)** 적용 여지도 있음(단 배치는 최대 1시간
  지연 — 파트너 UX "분석 중" 표시가 길어질 수 있어 Phase 2 검토).
- **구현 영향**: Anthropic API 키 신규 발급 필요(참고: GEMINI_API_KEY도 실키는 미발급
  상태라 라이브 개방 시 키 1개 발급 부담은 어느 쪽이든 동일). 어댑터는 이미 config
  추상화로 설계 — Anthropic 경로(공식 `anthropic` SDK + structured outputs)를 추가하면
  추출 JSON이 스키마 검증까지 SDK에서 보장되어 파이프라인이 오히려 단순해짐.
  기존 듀얼 게이트·invocation log·eval harness 패턴은 프로바이더 무관이라 그대로 적용.
- HWP는 어떤 모델도 네이티브 미지원 — 서버측 경량 파서로 텍스트 추출 후 전달(모델 무관 전처리).
- **민감정보 유의**: 공급가 등이 외부 API로 전송됨. 파트너 온보딩 문서에 고지(동의) 명시.
  Anthropic API는 입력을 모델 학습에 사용하지 않음; Fable 5는 30일 보존 요건 있음(고지 문구에 포함).
- 물량이 커지는 Phase 3에 재평가: 1단계 분류만 Sonnet 5/Haiku 4.5 또는 Gemini Flash로
  내리는 하이브리드로 비용 최적화(추출 품질은 유지).

## 5. 구현 순서 (승인 후, 테스트 게이트 427 유지)

1. 서체 Newsreader 적용(허브) — 소규모
2. etc 레인(+영상 여부 반영) + 검증·테스트 확장
3. migration 011 + partner_asset_profile 저장소
4. 분류·유형별 추출 모듈(드라이런 결정적 샘플 우선) + `partner_asset_ingest` 잡 배선
5. 조립(assemble) — 프로필 → 복수 제품 초안 제안
6. 파트너 UI(분석 상태·유형 배지·요약·초안 제안) + 대시보드 needs_review 큐
7. 테스트(분류 결정성·유형별 스키마·한도·실패 재시도·pending 정직성) — 목표 470+
8. 브리핑 0.0.21 + HANDOFF + 배포 노트

## 6. 확인 요청 (남은 1개)

1. ~~서체~~ → **확정: Newsreader, 허브만**
2. ~~기타 레인~~ → **확정: 문서만 (docx·pptx·hwp·hwpx·txt)**
3. **모델**: §4 재제안 — **Claude Opus 4.8 기본 + Fable 5 에스컬레이션** 확정 여부.
4. ~~분석 시점~~ → **확정: 업로드 즉시 자동 (잡큐 비동기)**
