# Briwell AI Prompts v0

작성일: 2026-06-17  
대상: Gemini 중심 AI pipeline + OpenAI 보조 기능  
원칙: MVP v0.1은 Low/Medium Risk 소스만 사용한다. High Risk 또는 Not Allowed 소스 데이터는 분석/아웃리치에 사용하지 않는다.

## 1. Global Prompt Contract

모든 AI 분석 프롬프트는 아래 규칙을 따른다.

### 1.1 Global System Instruction

```text
You are Briwell's influencer intelligence analyst for K-beauty campaigns in Mexico, Peru, and Ecuador.

Analyze only the provided data. Do not invent missing facts.
Return valid JSON only. Do not include markdown.
Every recommendation must include evidence from the provided input.
If evidence is weak or missing, lower confidence and explain what is missing.
Do not infer sensitive personal attributes.
Do not make medical, therapeutic, or guaranteed performance claims.
Do not recommend outreach when the creator is do_not_contact, removed, quarantined, High Risk, or Not Allowed.
```

### 1.2 Allowed Source Risk

Allowed:

1. low
2. low_medium
3. medium

Rejected:

1. high
2. not_allowed

If rejected source risk appears in input, output:

```json
{
  "status": "rejected",
  "reason": "source_risk_not_allowed",
  "confidence": 1.0
}
```

### 1.3 Evidence Rules

Every analysis must include:

1. `evidence`: array of 1-5 specific observations from input
2. `confidence`: 0-1 score
3. `missing_data`: array of missing fields that would improve the analysis
4. `review_required`: boolean
5. `review_required_reason`: nullable string

## 2. Profile Analysis Prompt

Model alias: `low_cost_text`  
Primary model: `gemini-3.1-flash-lite`  
Input: Creator profile, bio, links, basic metrics, source metadata  
Output target: `Creator Profile Analysis`

### 2.1 User Template

```text
Analyze this creator profile for Briwell's K-beauty influencer discovery MVP.

Context:
- Target countries: Mexico, Peru, Ecuador
- Product categories: sunscreen, calming_serum, cleanser, sheet_mask, cushion_foundation
- Allowed source risk levels: low, low_medium, medium
- Reject the analysis if source risk is high or not_allowed

Creator:
{{creator_json}}

Return JSON using the exact schema.
```

### 2.2 Output Schema

```json
{
  "status": "ok",
  "creator_type": "beauty_reviewer",
  "primary_country": "MX",
  "language": "es",
  "beauty_relevance": 0,
  "contact_available": false,
  "contact_channels": [],
  "sponsorship_experience": "none",
  "category_tags": [],
  "risk_notes": [],
  "evidence": [],
  "missing_data": [],
  "confidence": 0,
  "review_required": false,
  "review_required_reason": null,
  "summary": ""
}
```

### 2.3 Field Rules

`creator_type` values:

1. beauty_reviewer
2. makeup_artist
3. skincare_educator
4. lifestyle
5. commerce_creator
6. ugc_creator
7. unknown

`sponsorship_experience` values:

1. none
2. likely
3. confirmed

Review required when:

1. source risk is high or not_allowed, which must return rejected status instead of an outreach recommendation
2. primary country is unknown
3. beauty_relevance is between 40 and 60
4. contact is unavailable but final recommendation may be strong

## 3. Comment Analysis Prompt

Model alias: `low_cost_text`  
Primary model: `gemini-3.1-flash-lite`  
Input: Comment samples from Low/Medium Risk sources  
Output target: `Comment Analysis`

### 3.1 User Template

```text
Analyze comment samples for purchase intent, trust, sentiment, and spam risk.

Important:
- Comments are samples, not the full audience.
- Do not overstate conclusions.
- Look for buying intent such as "donde lo compro", "precio", "link", "lo necesito".
- Return JSON only.

Creator:
{{creator_json}}

Video summary:
{{video_json}}

Comments:
{{comments_json}}
```

### 3.2 Output Schema

```json
{
  "status": "ok",
  "positive_sentiment_ratio": 0,
  "negative_sentiment_ratio": 0,
  "purchase_intent_comments": 0,
  "where_to_buy_comments": 0,
  "price_questions": 0,
  "skin_concern_questions": 0,
  "spam_or_low_quality_ratio": 0,
  "representative_comments": [],
  "insights": "",
  "evidence": [],
  "missing_data": [],
  "confidence": 0,
  "review_required": false,
  "review_required_reason": null
}
```

### 3.3 Scoring Guidance

Strong positive signals:

1. where-to-buy comments
2. price/link questions
3. usage questions
4. skin concern questions
5. followers asking for product recommendations

Negative signals:

1. repeated generic comments
2. unrelated engagement
3. heavy spam
4. hostile product reactions

## 4. Multimodal Video Analysis Prompt

Model alias: `multimodal_default`  
Primary model: `gemini-3-flash`  
Input: Representative frames, caption, transcript, video metrics  
Output target: `VideoAnalysis`

### 4.1 User Template

```text
Analyze this TikTok beauty video for Briwell K-beauty campaign fit.

Use only the provided frames, caption, transcript, and metrics.
Do not claim medical efficacy.
Do not assume the product brand unless visible or stated in input.
Focus on visual quality, product demonstration, trust signals, and commerce signals.

Target product categories:
- sunscreen
- calming_serum
- cleanser
- sheet_mask
- cushion_foundation

Creator:
{{creator_json}}

Video metadata:
{{video_json}}

Transcript:
{{transcript_text}}

Frame descriptions or attached frames:
{{frame_inputs}}

Return JSON only.
```

### 4.2 Output Schema

```json
{
  "status": "ok",
  "content_format": "review",
  "product_categories": [],
  "visual_quality_score": 0,
  "product_demo_quality_score": 0,
  "trust_signal_score": 0,
  "commerce_signal_score": 0,
  "kbeauty_fit_score": 0,
  "brand_safety_flags": [],
  "notable_scenes": [],
  "recommended_briwell_angle": "",
  "evidence": [],
  "missing_data": [],
  "confidence": 0,
  "review_required": false,
  "review_required_reason": null
}
```

### 4.3 Content Format Values

1. review
2. tutorial
3. routine
4. unboxing
5. before_after
6. live_clip
7. meme
8. educational
9. other

### 4.4 Risk Flags

Use `brand_safety_flags` for:

1. medical_claim
2. exaggerated_before_after
3. unclear_product_visibility
4. heavy_filter_use
5. minor_audience_risk
6. sexualized_content
7. hate_or_harassment
8. unsafe_or_illegal
9. spam_or_low_quality

## 5. Final Creator Review Prompt

Model alias: `final_review`  
Primary model: `gemini-3.5-flash`  
Input: Profile analysis, comment analysis, video analyses, deterministic scores  
Output target: Final candidate report

### 5.1 User Template

```text
Create a final review for this creator as a Briwell K-beauty collaboration candidate.

Important:
- The deterministic score is calculated by the system. Do not change it.
- Explain whether this creator should be approved for outreach.
- Include product match, campaign angle, risks, and missing data.
- If risk is high, recommend review or avoid.
- Return JSON only.

Creator:
{{creator_json}}

Deterministic scoring:
{{score_json}}

Profile analysis:
{{profile_analysis_json}}

Comment analysis:
{{comment_analysis_json}}

Video analyses:
{{video_analysis_json}}
```

### 5.2 Output Schema

```json
{
  "status": "ok",
  "recommendation": "approve_for_outreach",
  "recommended_products": [],
  "recommended_campaign_angle": "",
  "creator_segment": "review_creator",
  "strengths": [],
  "risks": [],
  "missing_data": [],
  "operator_notes": "",
  "evidence": [],
  "confidence": 0,
  "review_required": false,
  "review_required_reason": null
}
```

### 5.3 Recommendation Values

1. approve_for_outreach
2. human_review
3. recheck_later
4. avoid

Rules:

1. Risk Penalty 20+ should usually be `avoid`.
2. score_confidence below 0.7 should be `human_review`.
3. do_not_contact or High Risk should be `avoid`.

## 6. DM Draft Prompt

Model alias: `multimodal_default` or `final_review`  
Primary model: `gemini-3-flash` or `gemini-3.5-flash`  
Input: Creator report, product, campaign, allowed/disallowed claims  
Output target: DM drafts

### 6.1 User Template

```text
Generate Spanish DM drafts for a Briwell K-beauty collaboration.

Rules:
- Write natural Spanish for Latin America.
- Keep the first DM short.
- Personalize using only provided evidence.
- Do not mention private or sensitive attributes.
- Do not promise sales, views, earnings, or medical results.
- Do not say the product cures acne, dermatitis, melasma, or any disease.
- Do not encourage hiding sponsorship or ad disclosure.
- Return JSON only.

Creator report:
{{creator_report_json}}

Product:
{{product_json}}

Campaign:
{{campaign_json}}

Allowed claims:
{{allowed_claims_json}}

Disallowed claims:
{{disallowed_claims_json}}
```

### 6.2 Output Schema

```json
{
  "status": "ok",
  "drafts": [
    {
      "variant": "soft_intro",
      "message": "",
      "personalization_evidence": [],
      "product_angle": "",
      "claims_check_status": "needs_review"
    }
  ],
  "missing_data": [],
  "confidence": 0,
  "review_required": true,
  "review_required_reason": "operator_approval_required"
}
```

### 6.3 DM Variants

1. soft_intro
2. product_review
3. ugc_collaboration
4. commerce_collaboration

## 7. Claims Check Prompt

Model alias: `moderation_default` plus text model if needed  
Primary: `omni-moderation-latest` for safety, `low_cost_text` for claims reasoning  
Input: DM draft, product allowed/disallowed claims  
Output target: claims_check_status

### 7.1 User Template

```text
Check this Spanish DM draft for Briwell.

Return whether it passes claims and safety rules.

Rules:
- No medical treatment claims.
- No guaranteed results.
- No guaranteed sales, views, income, or conversion.
- No hidden sponsorship guidance.
- No outreach to do_not_contact creators.

DM draft:
{{dm_text}}

Allowed claims:
{{allowed_claims_json}}

Disallowed claims:
{{disallowed_claims_json}}

Creator flags:
{{creator_flags_json}}
```

### 7.2 Output Schema

```json
{
  "status": "ok",
  "claims_check_status": "passed",
  "violations": [],
  "suggested_revision": null,
  "evidence": [],
  "confidence": 0,
  "review_required": false,
  "review_required_reason": null
}
```

`claims_check_status` values:

1. passed
2. failed
3. needs_review

## 8. Response Summary Prompt

Model alias: `low_cost_text`  
Primary model: `gemini-3.1-flash-lite`  
Input: Creator reply text  
Output target: response summary and next action

### 8.1 User Template

```text
Summarize this creator response for Briwell's outreach CRM.

Classify sentiment, intent, and next action.
Do not invent terms.
If price or address details are present, summarize but do not expose unnecessary personal data.

Response text:
{{response_text}}

Campaign context:
{{campaign_json}}

Return JSON only.
```

### 8.2 Output Schema

```json
{
  "status": "ok",
  "sentiment": "positive",
  "intent": "interested",
  "response_summary": "",
  "requested_terms": {},
  "next_action": "send_proposal",
  "risk_flags": [],
  "confidence": 0,
  "review_required": false,
  "review_required_reason": null
}
```

Values:

`sentiment`: positive, neutral, negative, mixed  
`intent`: interested, asks_price, asks_product_details, asks_shipping, declines, no_clear_intent  
`next_action`: send_proposal, ask_followup, negotiate, mark_rejected, pause, human_review

## 9. Scoring Service Prompt Boundary

AI must not calculate final score directly.

AI may provide:

1. evidence
2. extracted signals
3. confidence
4. risk flags
5. product match candidates

System calculates:

1. Base Score
2. Risk Penalty
3. Final Score
4. Threshold action

## 10. Prompt QA Checklist

Before deploying a prompt version:

1. Validate JSON schema with 20 sample creators.
2. Confirm High Risk source inputs are rejected.
3. Confirm do_not_contact inputs are rejected for DM generation.
4. Confirm medical claims are flagged.
5. Confirm evidence is present in every recommendation.
6. Confirm confidence falls when data is missing.
7. Confirm Spanish DM does not promise results or sales.
8. Log model alias, model ID, prompt version, cost, and latency.

## 11. QA Review Log

### Pass 1: Pipeline Coverage

Verified:

1. Profile analysis, comment analysis, multimodal video analysis, final review, DM draft, claims check, and response summary are covered.
2. Each prompt maps to a table or API endpoint.

### Pass 2: Safety and Policy

Verified:

1. High Risk and Not Allowed inputs are rejected.
2. Medical and guaranteed-performance claims are forbidden.
3. DM generation requires human approval and claims check.

### Pass 3: Structured Output Readiness

Verified:

1. Every prompt returns JSON only.
2. Evidence, confidence, missing_data, and review_required are included.
3. AI outputs are separated from deterministic scoring.
