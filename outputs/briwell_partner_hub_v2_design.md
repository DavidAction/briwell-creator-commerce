# 브랜드 파트너 허브 v2 설계 — 서체 · 기타 레인 · AI 인제스천

작성 2026-07-12 · 상태: **David 확인 대기** (승인 후 구현. Phase 1 = briefing 0.0.20 완료 기준)

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
- 모든 호출은 ai_invocation_log 기록(기존 관례).

## 4. AI 모델 — 무엇을 달 것인가 (David 질문에 대한 답)

용도 = 문서 멀티모달 인제스천(분류+추출). 2026-07 기준 비교:

| 선택지 | 강점 | 약점 | 파일럿 적합성 |
|---|---|---|---|
| **Gemini 2.5 Flash** ← 권장 기본 | PDF·이미지 네이티브 멀티모달, 대용량 컨텍스트(카탈로그 통째), 빠르고 매우 저렴, **기존 어댑터·키·게이트·로그·eval 인프라 그대로** | 최고난도 저화질 스캔·복잡 표는 Pro 대비 약함 | ◎ |
| Gemini 2.5 Pro ← 에스컬레이션 슬롯 | 저화질 스캔·복잡 표 최상급 | Flash 대비 수 배~십수 배 비용 | ○ (선별 사용) |
| Claude Sonnet 5 / Haiku 4.5 | 문서 이해·한국어 추출 품질 우수, PDF 네이티브 | **신규 API 키·어댑터·과금 라인 추가** — 파일럿에 운영 복잡도만 증가 | △ (Phase 3 재평가) |
| 오픈소스 로컬(비전 LLM) | 데이터 외부 미전송 | 파일럿 규모에 GPU 인프라 과투자, 품질 관리 부담 | ✕ |

**권장: Gemini 2.5 Flash 단일로 시작 + 에스컬레이션 슬롯.**
- `PARTNER_AI_MODEL`(기본 `gemini-2.5-flash`) / `PARTNER_AI_ESCALATION_MODEL`(기본 비활성)
  로 config 추상화 — 골든셋 측정에서 특정 유형(예: 저화질 성분표 스캔)이 부족하면 그 유형만
  Pro로 올리고, 장기적으로 Claude 교체·병행도 설정 교체만으로 가능하게.
- 근거: ① 분류+정형 추출은 Flash급으로 충분하다는 것이 업계 일반 관행이고, 부족 여부는
  골든셋으로 **측정해서** 결정(추측 금지). ② 기존 Gemini 인프라(어댑터·듀얼 게이트·
  invocation log·eval harness) 재사용이 파일럿 총비용 최소. ③ HWP는 어떤 모델도 네이티브
  지원이 없어 서버측 텍스트 추출(경량 파서) 후 텍스트로 전달 — 모델 선택과 무관한 전처리.
- **민감정보 유의**: 공급가 등이 외부 API로 전송됨. 파트너 온보딩 문서에 고지(동의) 명시,
  가격 필드 마스킹 옵션은 Phase 2 후보.

## 5. 구현 순서 (승인 후, 테스트 게이트 427 유지)

1. 서체 Newsreader 적용(허브) — 소규모
2. etc 레인(+영상 여부 반영) + 검증·테스트 확장
3. migration 011 + partner_asset_profile 저장소
4. 분류·유형별 추출 모듈(드라이런 결정적 샘플 우선) + `partner_asset_ingest` 잡 배선
5. 조립(assemble) — 프로필 → 복수 제품 초안 제안
6. 파트너 UI(분석 상태·유형 배지·요약·초안 제안) + 대시보드 needs_review 큐
7. 테스트(분류 결정성·유형별 스키마·한도·실패 재시도·pending 정직성) — 목표 470+
8. 브리핑 0.0.21 + HANDOFF + 배포 노트

## 6. 확인 요청 (이 4개만 답하면 착수)

1. **서체**: 2번 = Newsreader 맞는지 / 적용 범위(권장: 이번엔 허브만).
2. **기타 레인**: 문서(docx·pptx·hwp·hwpx·txt)만 vs **영상(mp4·mov, 200MB 상한) 포함**.
3. **모델**: Gemini 2.5 Flash 기본 + Pro 에스컬레이션 슬롯 권장안 승인 여부.
4. **분석 시점**: 업로드 즉시 자동(잡큐 비동기, 권장) vs 파트너 수동 버튼 유지.
