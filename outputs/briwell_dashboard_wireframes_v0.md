# Briwell Dashboard Wireframes v0

작성일: 2026-06-17  
대상: 내부 운영툴 MVP v0.1  
원칙: Low/Medium Risk 소스만 사용하며, High Risk 수집 작업은 UI에서 생성/실행할 수 없다.

## 1. Dashboard Goals

대시보드는 운영자가 다음 일을 빠르게 하도록 설계한다.

1. 국가별 후보 풀의 규모와 품질을 파악한다.
2. AI 추천 후보를 근거와 함께 검수한다.
3. 제품군별로 적합한 크리에이터를 필터링한다.
4. DM 초안을 검토하고 승인한다.
5. 캠페인별 아웃리치 상태와 응답률을 추적한다.
6. AI 분석 비용과 데이터 소스 리스크를 통제한다.

## 2. Navigation

좌측 내비게이션:

1. Overview
2. Creators
3. Review Queue
4. Campaigns
5. Outreach
6. Products
7. Keywords
8. AI Jobs
9. Settings

권한별 표시:

| Page | Admin | Operator | Campaign Manager | Viewer |
|---|---|---|---|---|
| Overview | view | view | view | view |
| Creators | edit | edit | view | view |
| Review Queue | edit | edit | approve | view |
| Campaigns | edit | view | edit | view |
| Outreach | edit | edit | approve | view |
| Products | edit | view | edit | view |
| Keywords | edit | view | view | view |
| AI Jobs | approve | view | view | view |
| Settings | edit | none | none | none |

## 3. Overview Page

### 3.1 Purpose

국가별 후보 수, 분석 진행률, 아웃리치 상태, AI 비용을 한 화면에서 확인한다.

### 3.2 Layout

```text
+-------------------------------------------------------------------+
| Briwell Influencer Intelligence                  [Date] [User]     |
+----------------+--------------------------------------------------+
| Navigation     | KPI Row                                          |
|                | Candidates | Analyzed | Review Queue | DM Ready  |
|                |--------------------------------------------------|
|                | Country Funnel                                   |
|                | MX: candidates -> analyzed -> approved -> DM sent |
|                | PE: candidates -> analyzed -> approved -> DM sent |
|                | EC: candidates -> analyzed -> approved -> DM sent |
|                |--------------------------------------------------|
|                | Top Recommended Creators                          |
|                |--------------------------------------------------|
|                | AI Cost and Job Status                             |
+----------------+--------------------------------------------------+
```

### 3.3 KPI Cards

| Card | Definition |
|---|---|
| Total Candidates | Low/Medium Risk 후보 전체 수 |
| AI Analyzed | CreatorAnalysis가 생성된 후보 수 |
| Review Queue | 운영자 검수 대기 후보 수 |
| DM Ready | claims check 통과 후 승인 대기 DM 수 |
| Outreach Sent | 1차 아웃리치 완료 수 |
| AI Cost | 기간 내 AI 분석 비용 |

### 3.4 States

Empty state:

```text
No candidates yet.
Import a CSV or add Low/Medium Risk sources from Keywords.
```

Warning state:

```text
High Risk source detected in imported data.
These records are quarantined and excluded from analysis.
```

## 4. Creators Page

### 4.1 Purpose

후보 검색, 필터링, 랭킹 비교를 수행한다.

### 4.2 Filters

필터:

1. Country: MX, PE, EC
2. Product Category: sunscreen, calming_serum, cleanser, sheet_mask, cushion_foundation
3. Segment: Viral Micro, Beauty Educator, Review Creator, Commerce Creator, Brand Builder, UGC Creator, Avoid
4. Final Score range
5. Risk Penalty range
6. Source Risk: Low, Low to Medium, Medium
7. Contact Available
8. Outreach Status
9. Last Analyzed Date
10. Search: username, display name, bio keyword

High Risk and Not Allowed are not selectable as active candidate filters. They appear only in quarantine/admin views.

### 4.3 Table Columns

| Column | Notes |
|---|---|
| Creator | username, display name, platform |
| Country | MX, PE, EC |
| Segment | AI segment |
| Product Match | top recommended product |
| Final Score | 0-100 |
| Risk | 0-30 penalty |
| Followers | latest known |
| Avg Views | recent sample |
| Contact | email/IG/TikTok/WhatsApp |
| Source Risk | Low/Low to Medium/Medium |
| Outreach | status |

### 4.4 Row Actions

1. View Detail
2. Add to Review Queue
3. Generate DM
4. Add to Campaign
5. Mark Do Not Contact

`Generate DM` is disabled when:

1. `do_not_contact = true`
2. `source_risk_level = High`
3. `removal_requested_at` exists
4. `claims_check_status = failed`

## 5. Creator Detail Page

### 5.1 Purpose

한 크리에이터의 추천 근거, 점수, 리스크, DM 초안을 한 화면에서 검토한다.

### 5.2 Layout

```text
+-------------------------------------------------------------------+
| Creator Header: @username | country | segment | final score        |
+-------------------------------------------------------------------+
| Left Column                       | Right Column                    |
| Profile summary                   | Score breakdown                 |
| Contact channels                  | Risk flags                      |
| Source metadata                   | Recommended products            |
| Recent videos                     | AI evidence                     |
| Comment insights                  | DM drafts                       |
| Multimodal insights               | Outreach history                |
+-------------------------------------------------------------------+
```

### 5.3 Required Blocks

1. Profile Summary
2. Source Metadata
3. Score Breakdown
4. AI Evidence
5. Product Match
6. Risk Review
7. Recent Video Summary
8. Comment Insight Summary
9. DM Drafts
10. Operator Feedback

### 5.4 Source Metadata Block

Fields:

1. source_type
2. source_url
3. source_risk_level
4. collected_at
5. last_verified_at

If an imported legacy record has High source risk, it appears only in quarantine/admin views and displays:

```text
Quarantined record. This creator is excluded from analysis and outreach in MVP v0.1.
```

## 6. Review Queue Page

### 6.1 Purpose

AI가 추천하거나 주의 표시한 후보를 사람이 최종 검수한다.

### 6.2 Queue Reasons

1. Final Score 70+
2. score_confidence below 0.7
3. Risk Penalty 10+
4. Product match conflict
5. DM claims check required
6. VIP or fixed-fee candidate

### 6.3 Review Actions

1. Approve for Outreach
2. Request Re-analysis
3. Adjust Score
4. Change Segment
5. Mark Avoid
6. Mark Do Not Contact
7. Add Operator Note

Every action creates an AuditLog entry.

## 7. Campaigns Page

### 7.1 Purpose

제품별 캠페인 후보를 구성하고 결과를 추적한다.

### 7.2 Campaign Create Form

Fields:

1. campaign name
2. country
3. product_id
4. product_category
5. campaign_goal
6. budget
7. sales_channel
8. tracking_url
9. coupon_code_prefix
10. target_creator_count
11. start_date
12. end_date

### 7.3 Campaign Detail

Sections:

1. Campaign Summary
2. Candidate List
3. Outreach Funnel
4. DM Performance
5. Content Posted
6. Sales/Tracking Notes
7. AI Cost by Campaign

## 8. Outreach Page

### 8.1 Purpose

DM 초안, 승인, 발송 상태, 응답 요약을 관리한다.

### 8.2 Outreach Kanban

Columns:

1. Discovered
2. Reviewing
3. Approved
4. Contact Found
5. DM Drafted
6. DM Sent
7. Replied
8. Negotiating
9. Accepted
10. Sample Sent
11. Content Posted
12. Completed
13. Rejected
14. Paused

### 8.3 DM Draft Panel

Shows:

1. DM variant
2. Spanish draft
3. Personalization evidence
4. Product angle
5. Claims check status
6. Do-not-contact check status
7. Approve button
8. Edit button

Approve button is disabled unless:

1. claims_check_status = passed
2. do_not_contact_checked_at exists
3. source_risk_level is Low, Low to Medium, or Medium

## 9. Products Page

### 9.1 Purpose

제품군과 실제 SKU 정보를 관리한다.

Fields:

1. brand_name
2. product_name
3. product_category
4. country_availability
5. key_claims_allowed
6. claims_disallowed
7. target_skin_concerns
8. price_range
9. sample_available
10. landing_url
11. status

## 10. Keywords Page

### 10.1 Purpose

국가별 제품 키워드와 해시태그 seed를 관리한다.

Actions:

1. Import CSV
2. Add Keyword
3. Disable Keyword
4. Export Keyword CSV

High Risk collection cannot be enabled from this page.

## 11. AI Jobs Page

### 11.1 Purpose

AI 분석 작업의 상태, 비용, 실패율을 관리한다.

Job types:

1. profile_analysis
2. comment_analysis
3. transcription
4. multimodal_analysis
5. final_review
6. dm_generation
7. claims_check

### 11.2 Job Create Rules

Allowed source risk levels:

1. Low
2. Low to Medium
3. Medium

Not allowed:

1. High
2. Not Allowed

## 12. Mobile and Responsive Notes

MVP는 desktop-first로 만든다. 모바일은 읽기/승인 정도만 지원한다.

Mobile priority:

1. Overview KPI
2. Creator Detail
3. Review Queue approval
4. Outreach status check

Dense tables은 모바일에서 카드 리스트로 전환한다.

## 13. Accessibility and UX Rules

1. 점수 색상만으로 상태를 구분하지 않는다.
2. 모든 위험/승인 상태에는 텍스트 라벨을 함께 표시한다.
3. DM 승인 버튼은 비활성 사유를 명확히 표시한다.
4. Source Risk는 항상 Creator Detail과 Outreach Panel에 노출한다.
5. 삭제/Do Not Contact 액션은 확인 모달을 사용한다.

## 14. QA Review Log

### Pass 1: Workflow Completeness

검증 결과:

1. PRD의 Overview, Creator Search, Creator Detail, Outreach CRM 요구사항을 모두 화면으로 매핑했다.
2. Campaign, Products, Keywords, AI Jobs까지 개발 착수에 필요한 관리 화면을 추가했다.

### Pass 2: Low/Medium Risk Consistency

검증 결과:

1. High Risk 수집 실행 UI를 제공하지 않도록 명시했다.
2. High Risk 데이터는 quarantine/admin 표시 외 분석/아웃리치에서 제외하도록 명시했다.
3. DM 승인 조건에 source risk check를 포함했다.

### Pass 3: Implementation Readiness

검증 결과:

1. 각 화면의 필터, 컬럼, 액션, 비활성 조건을 정의했다.
2. 권한별 접근 범위를 추가했다.
3. AuditLog가 필요한 액션을 명시했다.
