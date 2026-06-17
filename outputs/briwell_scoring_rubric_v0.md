# Briwell Creator Scoring Rubric v0

작성일: 2026-06-17  
대상: 멕시코, 페루, 에콰도르 TikTok 뷰티 인플루언서  
전제: MVP v0.1은 Low/Medium Risk 소스만 사용한다. High Risk 수집 경로로 얻은 데이터는 분석/아웃리치에 사용하지 않는다.

## 1. Scoring Overview

최종 점수는 100점 만점의 Base Score에서 Risk Penalty를 차감한다.

```text
Base Score =
Beauty Fit * 0.25
+ Engagement Quality * 0.20
+ Audience Locality * 0.15
+ Commerce Intent * 0.15
+ Content Quality * 0.10
+ Collaboration Probability * 0.10
+ Cost Efficiency * 0.05

Final Score = clamp(Base Score - Risk Penalty, 0, 100)
```

각 dimension은 0-100점으로 먼저 계산한다. 가중합으로 Base Score를 만들고, Risk Penalty는 0-30점 차감한다.

## 2. Score Dimensions

### 2.1 Beauty Fit, 25%

| Score Range | Criteria |
|---|---|
| 0-20 | 뷰티/스킨케어 관련성이 거의 없음 |
| 21-40 | 라이프스타일 계정이며 뷰티 콘텐츠가 드물게 있음 |
| 41-60 | 뷰티 콘텐츠가 있으나 K-뷰티/제품군 적합도가 낮음 |
| 61-80 | 스킨케어, 메이크업, 리뷰 콘텐츠가 꾸준함 |
| 81-100 | K-뷰티 또는 Briwell 우선 제품군과 명확히 맞음 |

강한 가산 신호:

1. 스킨케어 루틴, 제품 리뷰, 사용감 설명이 많음
2. sunscreen, calming serum, cleanser, sheet mask, cushion 중 하나와 명확히 연결됨
3. "K-beauty", "maquillaje coreano", "skincare coreano" 언급

### 2.2 Engagement Quality, 20%

| Score Range | Criteria |
|---|---|
| 0-20 | 댓글/좋아요가 낮거나 스팸성 반응이 많음 |
| 21-40 | 반응은 있으나 질문/구매 의도 댓글이 적음 |
| 41-60 | 평균적인 참여도와 일부 유효 댓글 |
| 61-80 | 제품 질문, 사용감 질문, 구매 위치 질문이 꾸준함 |
| 81-100 | 팔로워 대비 조회수와 댓글 품질이 매우 좋고 구매 의도 댓글이 많음 |

측정 신호:

1. 최근 영상 평균 조회수
2. 팔로워 대비 조회수 비율
3. 댓글 중 질문 비율
4. "donde compro", "precio", "link", "lo necesito" 유형 댓글
5. 스팸/봇 의심 댓글 비율

### 2.3 Audience Locality, 15%

| Score Range | Criteria |
|---|---|
| 0-20 | 대상 국가와 연결 신호가 거의 없음 |
| 21-40 | 스페인어권이지만 국가 특정성이 약함 |
| 41-60 | 국가 해시태그 또는 일부 현지 표현이 있음 |
| 61-80 | 멕시코/페루/에콰도르 현지 오디언스 가능성이 높음 |
| 81-100 | 프로필, 댓글, 도시/국가 태그, 협업 이력상 대상 국가 적합성이 강함 |

사용 가능한 신호:

1. 프로필 위치, 국가 태그
2. 댓글의 현지 표현
3. 국가 해시태그
4. 현지 브랜드/매장/배송 문의
5. Instagram/YouTube 교차 확인

### 2.4 Commerce Intent, 15%

| Score Range | Criteria |
|---|---|
| 0-20 | 구매 유도 경험이 거의 없음 |
| 21-40 | 협찬/리뷰 경험은 있으나 전환 신호가 약함 |
| 41-60 | 제품 리뷰와 링크/쿠폰 경험이 일부 있음 |
| 61-80 | 쿠폰, 링크, 라이브, 가격 문의, 구매 댓글이 꾸준함 |
| 81-100 | 커머스형 콘텐츠와 구매 전환 신호가 강함 |

강한 가산 신호:

1. 쿠폰 코드 사용 경험
2. 링크 인 바이오 또는 제품 태그
3. "donde comprar" 댓글에 답변 경험
4. 라이브/리뷰/언박싱을 통한 판매 경험

### 2.5 Content Quality, 10%

| Score Range | Criteria |
|---|---|
| 0-20 | 제품이 잘 보이지 않거나 설명이 부족함 |
| 21-40 | 콘텐츠 품질이 낮고 브랜드 활용이 어려움 |
| 41-60 | 기본적인 리뷰/루틴 콘텐츠 가능 |
| 61-80 | 제품 시연, 설명, 화면 구성이 안정적 |
| 81-100 | 광고 소재로 재활용 가능한 수준의 영상 품질 |

측정 신호:

1. 제품 클로즈업
2. 텍스처/사용감 설명
3. Before/after 과장 없이 자연스러운 시연
4. 조명, 음성, 자막, 편집 품질
5. 필터 과다 사용 여부

### 2.6 Collaboration Probability, 10%

| Score Range | Criteria |
|---|---|
| 0-20 | 연락처가 없고 협찬 경험도 확인 어려움 |
| 21-40 | 연락 가능성은 낮지만 DM 가능 |
| 41-60 | Instagram/email 등 연락 경로가 있음 |
| 61-80 | 협찬 경험과 연락 경로가 명확함 |
| 81-100 | 협업 문의를 명시하고 응답 가능성이 높음 |

가산 신호:

1. 이메일 또는 Instagram 공개
2. "collab", "PR", "business" 언급
3. 과거 제품 협찬 콘텐츠
4. 최근 활동 빈도 높음

### 2.7 Cost Efficiency, 5%

| Score Range | Criteria |
|---|---|
| 0-20 | 예상 단가가 높고 성과 예측이 낮음 |
| 21-40 | 비용 대비 성과가 불확실함 |
| 41-60 | 평균적인 비용 효율 |
| 61-80 | 샘플/소액 고정비로 테스트 가능 |
| 81-100 | 낮은 비용으로 UGC 또는 전환 실험 가능성이 큼 |

초기에는 실제 단가가 없으므로 추정값으로 계산한다. 실제 협상 데이터가 쌓이면 이 항목은 업데이트한다.

## 3. Risk Penalty

Risk Penalty는 0-30점 차감한다.

| Penalty | Criteria |
|---:|---|
| 0 | 특별한 리스크 없음 |
| 5 | 댓글 품질 낮음, 협찬 표기 불명확, 과한 필터 사용 |
| 10 | 과장 표현 가능성, 저품질 협찬 다수, 브랜드 핏 애매함 |
| 20 | 논란 가능성, 의학적 효능 표현, 민감 콘텐츠 근접 |
| 30 | 아웃리치 제외 수준의 리스크 |

## 4. Auto Exclusion Rules

아래 조건에 해당하면 Final Score와 무관하게 아웃리치 후보에서 제외한다.

1. `do_not_contact = true`
2. `removal_requested_at` 존재
3. High Risk 또는 Not Allowed 소스 기반 데이터
4. 미성년자 대상 계정으로 의심
5. 비공개/삭제 콘텐츠 중심
6. 의료적 치료 효과를 반복적으로 주장
7. 혐오, 성적, 폭력, 불법 콘텐츠 리스크
8. 댓글 대부분이 스팸/봇으로 의심

## 5. Segment Rules

| Segment | Rule |
|---|---|
| Viral Micro | 팔로워는 작지만 최근 조회수/팔로워 비율이 높고 Risk 낮음 |
| Beauty Educator | Beauty Fit, Content Quality, 댓글 질문 품질이 높음 |
| Review Creator | 제품 리뷰/언박싱/사용감 설명 콘텐츠가 많음 |
| Commerce Creator | Commerce Intent와 구매 질문 댓글이 높음 |
| Brand Builder | Content Quality와 신뢰도가 높고 이미지가 좋음 |
| UGC Creator | 계정 파급력보다 영상 소재 제작 품질이 높음 |
| Avoid | Risk Penalty 20 이상 또는 Auto Exclusion 조건 충족 |

## 6. Review Queue Rules

운영자 검수 큐로 보내는 조건:

1. Final Score 70점 이상
2. score_confidence 0.7 미만
3. Risk Penalty 10점 이상
4. 추천 제품과 세그먼트가 불일치
5. DM 생성 전 claims check 필요
6. 고정비 협업 또는 VIP 후보로 분류

## 7. Initial Thresholds

| Action | Threshold |
|---|---|
| Store only | Final Score below 50 |
| Recheck later | Final Score 50-59 |
| Human review | Final Score 60-69 |
| Outreach candidate | Final Score 70-84 and Risk Penalty below 10 |
| Priority outreach | Final Score 85+ and Risk Penalty below 5 |
| Avoid | Risk Penalty 20+ or Auto Exclusion |

## 8. Evidence Requirements

AI 리포트에는 최소 3개 이상의 근거가 있어야 한다.

필수 근거:

1. 콘텐츠 근거: 어떤 영상/프로필/댓글 때문에 추천하는지
2. 제품 적합도 근거: 어떤 제품군과 맞는지
3. 리스크 근거: 리스크가 없거나 있다면 무엇인지

근거가 부족하면 `score_confidence`를 낮추고 운영자 검수로 보낸다.
