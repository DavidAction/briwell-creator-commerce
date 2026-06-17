# Briwell Pilot Operations Playbook v0

작성일: 2026-06-17  
대상: 멕시코, 페루, 에콰도르 TikTok K-beauty influencer pilot  
원칙: MVP v0.1은 Low/Medium Risk 수집 경로만 사용한다.

## 1. Purpose

이 문서는 운영자가 파일럿 후보를 수집, 검수, 업로드, 분석, DM 준비까지 진행하는 표준 절차를 정의한다.

핵심 목표:

1. 정책 리스크를 낮춘다.
2. 후보 데이터 품질을 일정하게 유지한다.
3. AI 분석에 필요한 최소 데이터를 확보한다.
4. 아웃리치 전 사람 검수를 보장한다.

## 2. Allowed Collection Paths

### 2.1 Low Risk

허용:

1. 기존 캠페인 응답자 DB
2. 인플루언서가 직접 제공한 미디어킷
3. 운영자가 직접 작성한 CSV
4. 인플루언서가 공개적으로 제공한 business email 또는 Instagram 링크 수동 기록

승인:

1. Operator 실행 가능
2. Admin 사후 검수 가능

### 2.2 Low to Medium Risk

허용:

1. 공식 API
2. 승인된 데이터 제공자
3. Creator Marketplace류 플랫폼 내 검색/내보내기 기능

승인:

1. Admin 사전 승인 필요
2. source metadata 필수

### 2.3 Medium Risk

허용:

1. 공개 TikTok 프로필/해시태그/검색 결과의 수동 리서치
2. Instagram/YouTube 공개 링크 교차 확인
3. 공개 댓글 일부를 수동 샘플링

승인:

1. Admin 승인 필요
2. 수집량 제한
3. 수집자, 수집일, source_url 기록 필수

### 2.4 Not Used in MVP v0.1

MVP v0.1에서는 하지 않는다.

1. 자동화된 공개 페이지 수집
2. 대량 영상 메타데이터 수집
3. 대량 댓글 샘플링
4. 로그인 우회
5. 캡차 우회
6. 비공개 데이터 접근
7. 삭제 콘텐츠 보관
8. 자동 DM 발송

## 3. Candidate Collection SOP

### Step 1: Choose Country and Product

운영자는 먼저 하나의 국가와 제품군을 선택한다.

예:

```text
Country: MX
Product category: sunscreen
Goal: coupon conversion test
```

### Step 2: Use Keyword Seeds

`briwell_keyword_seed_v0.csv`에서 해당 국가/제품군의 priority 1 키워드를 먼저 사용한다.

우선순위:

1. priority 1 discovery
2. priority 1 concern
3. priority 1 format
4. priority 1 commerce
5. priority 2 expansion

### Step 3: Candidate Minimum Fields

후보 등록 최소 필드:

1. country
2. username
3. profile_url
4. source_type
5. source_url
6. source_risk_level
7. collected_at

있으면 좋은 필드:

1. display_name
2. bio
3. follower_count
4. contact_email
5. instagram_url
6. category_tags

### Step 4: Source Risk Label

운영자는 후보별 source risk를 지정한다.

| Source | Label |
|---|---|
| Existing campaign DB | low |
| Creator-provided media kit | low |
| Manual CSV from public profile review | medium |
| Approved provider export | low_medium |
| Official API | low_medium |

High Risk는 선택하지 않는다.

### Step 5: Import CSV

`briwell_creator_import_template.csv` 형식을 사용한다.

Import 후 확인:

1. source metadata 누락 없음
2. country가 MX/PE/EC 중 하나
3. source_risk_level이 low/low_medium/medium 중 하나
4. duplicate username 확인
5. do_not_contact 기본값 false

### Step 6: AI Analysis

분석 순서:

1. profile analysis
2. comment analysis, only if approved comment samples exist
3. video/multimodal analysis, only if approved video/frame/transcript data exists
4. deterministic scoring
5. final review

### Step 7: Human Review

운영자는 Review Queue에서 확인한다.

검수 기준:

1. Final Score
2. Risk Penalty
3. 추천 제품
4. AI evidence
5. source metadata
6. contact availability
7. claims risk

### Step 8: DM Draft and Approval

DM 생성 전 확인:

1. do_not_contact = false
2. removal_requested_at 없음
3. source_risk_level in low/low_medium/medium
4. claims_check_status passed

발송은 시스템 자동화가 아니라 운영자가 수동으로 진행한다.

## 4. Daily Operating Targets

초기 파일럿 기준:

| Country | Daily Candidate Target | Daily Review Target | Daily DM Prep Target |
|---|---:|---:|---:|
| MX | 50 | 10 | 5 |
| PE | 25 | 5 | 3 |
| EC | 15 | 3 | 2 |

운영팀 규모에 따라 조정한다.

## 5. Quality Checklist

후보 승인 전 체크:

1. 대상 국가 적합성 있음
2. 뷰티/스킨케어 관련성 있음
3. 댓글 또는 콘텐츠 근거 있음
4. 연락 가능 경로 있음
5. High Risk 소스 아님
6. 의료/과장 표현 리스크 낮음
7. 제품 추천 이유가 명확함

## 6. Escalation Rules

Admin에게 올릴 조건:

1. source risk 판단이 애매함
2. 크리에이터가 삭제/비공개 요청
3. 댓글에 논란 또는 민감 이슈 발견
4. DM 문안이 claims check에서 failed
5. 고정비 협업 요청
6. VIP 또는 Brand Builder 후보

## 7. Pilot Reporting

주간 리포트 항목:

1. 국가별 후보 등록 수
2. 분석 완료 수
3. Review Queue 승인율
4. DM 준비 수
5. DM 발송 수
6. 응답률
7. 협업 논의 전환율
8. AI 비용 per approved creator
9. 주요 리스크 사례
10. 다음 주 scoring adjustment 제안

## 8. QA Review Log

### Pass 1: Policy Fit

Verified:

1. Low/Medium Risk only rule is operationalized.
2. High Risk collection paths are excluded from MVP v0.1.

### Pass 2: Operator Readiness

Verified:

1. Candidate collection steps are explicit.
2. Required fields and import checks are defined.
3. Daily operating targets are defined.

### Pass 3: AI and Outreach Consistency

Verified:

1. AI analysis only runs on approved available data.
2. DM approval requires do-not-contact and claims checks.
3. Manual sending rule is preserved.
