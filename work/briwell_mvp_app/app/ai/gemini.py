import json
from typing import Any

import httpx

from app.ai.adapters import AIAdapter, rejected_for_source_risk
from app.ai.contracts import AnalysisRequest, AnalysisResult
from app.ai.schema_validation import AnalysisSchemaError, validate_analysis_output
from app.core.config import settings
from app.schemas.analysis import ANALYSIS_OUTPUT_SCHEMAS


# Model ids verified against the live Gemini ListModels API on 2026-06-27.
# `gemini-3-flash` does NOT exist; the available gen-3 flash model is
# `gemini-3-flash-preview`. `gemini-3.1-flash-lite` and `gemini-3.5-flash`
# are valid non-preview models. Re-verify before enabling production live calls.
MODEL_BY_ALIAS = {
    "low_cost_text": "gemini-3.1-flash-lite",
    "final_review": "gemini-3.5-flash",
    "dm_generation": "gemini-3-flash-preview",
    "multimodal_default": "gemini-3-flash-preview",
    "recent_posts_screen": "gemini-3.1-flash-lite",
}


# Calibration guidance injected into every live prompt to counter the observed tendency of
# flash models to return inflated scores and over-high confidence. Keeps AI judgments
# discriminating so the evaluation harness can measure real signal.
CALIBRATION_GUIDANCE = (
    "Calibration: be conservative and discriminating, not generous. Scores are 0-100; "
    "confidence is 0-1. Reserve scores above 85 and confidence above 0.85 ONLY for cases with "
    "strong, explicit, consistent evidence across multiple posts. When evidence is thin, mixed, "
    "or partial, lower BOTH the score and the confidence. A typical real creator falls in the "
    "45-75 range; do not default to high scores or high confidence. Score anchors: 85-100 = "
    "exceptional, clearly proven fit; 70-84 = strong fit; 55-69 = moderate/uncertain; 40-54 = "
    "weak; below 40 = poor. If evidence is insufficient for a confident call, set "
    "review_required=true and keep confidence at or below 0.6."
)


class GeminiTextAdapter(AIAdapter):
    """Gemini adapter scaffold with dry-run schema validation by default."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        dry_run: bool | None = None,
        allow_live_provider_calls: bool | None = None,
        timeout_seconds: float = 30,
    ) -> None:
        self.api_key = settings.gemini_api_key if api_key is None else api_key
        self.base_url = (base_url or settings.gemini_api_base_url).rstrip("/")
        self.dry_run = settings.ai_dry_run if dry_run is None else dry_run
        self.allow_live_provider_calls = (
            settings.allow_live_provider_calls
            if allow_live_provider_calls is None
            else allow_live_provider_calls
        )
        self.timeout_seconds = timeout_seconds

    def run(self, request: AnalysisRequest) -> AnalysisResult:
        rejected = rejected_for_source_risk(request)
        if rejected is not None:
            return rejected

        if self.dry_run:
            return self._result_from_output(
                request=request,
                output=self._dry_run_output(request),
            )

        if not self.allow_live_provider_calls:
            return self._error_result(
                request=request,
                error_code="live_provider_calls_disabled",
                message="Live provider calls are disabled. Set ALLOW_LIVE_PROVIDER_CALLS=true.",
            )

        if not self.api_key:
            return self._error_result(
                request=request,
                error_code="provider_api_key_missing",
                message="GEMINI_API_KEY is required for live Gemini calls.",
            )

        try:
            output = self._call_gemini(request)
            return self._result_from_output(request=request, output=output)
        except (httpx.HTTPError, ValueError, KeyError, AnalysisSchemaError) as exc:
            return self._error_result(
                request=request,
                error_code="provider_call_failed",
                message=str(exc),
            )

    def _call_gemini(self, request: AnalysisRequest) -> dict[str, Any]:
        model_id = MODEL_BY_ALIAS.get(request.model_alias, request.model_alias)
        url = f"{self.base_url}/models/{model_id}:generateContent"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": self._build_parts(request),
                }
            ],
            "generationConfig": self._generation_config(request),
        }
        response = httpx.post(
            url,
            headers={"x-goog-api-key": self.api_key},
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        text = self._extract_text(body)
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("Gemini response JSON must be an object.")
        return parsed

    def _generation_config(self, request: AnalysisRequest) -> dict[str, Any]:
        schema_model = ANALYSIS_OUTPUT_SCHEMAS.get(request.task_type)
        if schema_model is None:
            return {"responseFormat": {"text": {"mimeType": "APPLICATION_JSON"}}}
        return {
            "responseFormat": {
                "text": {
                    "mimeType": "APPLICATION_JSON",
                    "schema": _schema_for_gemini(schema_model.model_json_schema()),
                }
            }
        }

    def _extract_text(self, body: dict[str, Any]) -> str:
        candidates = body.get("candidates") or []
        if not candidates:
            raise ValueError("Gemini response did not include candidates.")
        parts = ((candidates[0].get("content") or {}).get("parts") or [])
        text = "".join(str(part.get("text") or "") for part in parts if "text" in part)
        if not text:
            raise ValueError("Gemini response did not include text content.")
        return text

    def _build_parts(self, request: AnalysisRequest) -> list[dict[str, Any]]:
        """Build Gemini content parts: the text prompt plus any inline image frames.

        For multimodal_analysis, real video frame images supplied as base64 are sent as
        inlineData parts so Gemini actually sees the content instead of only a text
        description of it. Non-multimodal tasks send the text prompt alone.
        """
        parts: list[dict[str, Any]] = [{"text": self._build_prompt(request)}]
        if request.task_type == "multimodal_analysis":
            for image in _collect_inline_images(request.payload):
                parts.append(
                    {"inlineData": {"mimeType": image["mime_type"], "data": image["data"]}}
                )
        return parts

    def _build_prompt(self, request: AnalysisRequest) -> str:
        if request.task_type == "recent_posts_screen":
            return _build_recent_posts_screen_prompt(request)
        return json.dumps(
            {
                "instruction": (
                    "You are Briwell's K-beauty influencer analyst for Mexico, "
                    "Peru, and Ecuador. Return valid JSON only. Use only the "
                    "provided data. Do not invent missing facts."
                ),
                "calibration": CALIBRATION_GUIDANCE,
                "task_type": request.task_type,
                "prompt_version": request.prompt_version,
                "source_risk_level": request.source_risk_level,
                "payload": request.payload,
            },
            ensure_ascii=True,
        )

    def _result_from_output(
        self,
        request: AnalysisRequest,
        output: dict[str, Any],
    ) -> AnalysisResult:
        validated = validate_analysis_output(request.task_type, output)
        data = validated.model_dump()
        return AnalysisResult(
            status="ok",
            model_alias=request.model_alias,
            prompt_version=request.prompt_version,
            output=data,
            evidence=list(data.get("evidence", [])),
            missing_data=list(data.get("missing_data", [])),
            confidence=float(data.get("confidence", 0)),
            review_required=bool(data.get("review_required", False)),
            review_required_reason=data.get("review_required_reason"),
        )

    def _error_result(
        self,
        request: AnalysisRequest,
        error_code: str,
        message: str,
    ) -> AnalysisResult:
        return AnalysisResult(
            status="error",
            model_alias=request.model_alias,
            prompt_version=request.prompt_version,
            output={"status": "error", "message": message},
            confidence=0,
            review_required=True,
            review_required_reason=message,
            error_code=error_code,
        )

    def _dry_run_output(self, request: AnalysisRequest) -> dict[str, Any]:
        if request.task_type == "profile_analysis":
            return _dry_run_profile_analysis(request.payload)
        if request.task_type == "comment_analysis":
            return _dry_run_comment_analysis(request.payload)
        if request.task_type == "multimodal_analysis":
            return _dry_run_multimodal_analysis(request.payload)
        if request.task_type == "recent_posts_screen":
            return _dry_run_recent_posts_screen(request.payload)
        if request.task_type == "final_review":
            return _dry_run_final_review(request.payload)
        raise AnalysisSchemaError(f"unsupported_analysis_task:{request.task_type}")


def _build_recent_posts_screen_prompt(request: AnalysisRequest) -> str:
    return json.dumps(
        {
            "instruction": (
                "Analyze the creator's latest approved recent posts for Briwell's LATAM K-beauty "
                "creator commerce workflow. Return valid JSON only and match the provided schema. "
                "Use only the supplied captions, transcripts, hashtags, public metrics, creator "
                "snapshot, and product context. Do not browse, infer private demographics, or invent "
                "missing data. Treat medical, treatment, guaranteed-result, unsafe, or non-cosmetic "
                "claims as brand-safety risk notes."
            ),
            "calibration": CALIBRATION_GUIDANCE,
            "decision_policy": {
                "pass_to_full_analysis": (
                    "Use only when recent content strongly fits beauty/skincare/K-beauty, has no "
                    "material brand-safety risk, has enough recent posts, and should proceed to "
                    "profile, comment, and multimodal analysis before outreach."
                ),
                "human_review": (
                    "Use for borderline fit, missing transcripts/metrics, fewer than expected posts, "
                    "or any claim/safety uncertainty requiring an operator."
                ),
                "recheck_later": "Use when the creator may fit later but current recent content is weak or incomplete.",
                "avoid": "Use when recent posts show clear brand-safety, non-cosmetic, or unsuitable collaboration risk.",
            },
            "scoring_contract": {
                "all_scores": "0-100 numeric values",
                "ratios": "0-1 numeric values",
                "confidence": "0-1 numeric value",
                "matched_product_categories": [
                    "sunscreen",
                    "calming_serum",
                    "cleanser",
                    "sheet_mask",
                    "cushion_foundation",
                ],
            },
            "task_type": request.task_type,
            "prompt_version": request.prompt_version,
            "source_risk_level": request.source_risk_level,
            "payload": request.payload,
        },
        ensure_ascii=True,
        default=str,
    )


def _collect_inline_images(payload: dict[str, Any], limit: int = 8) -> list[dict[str, str]]:
    """Extract base64 image frames from a multimodal payload for inline Gemini parts.

    Each frame_sample may carry ``image_base64`` (raw base64, no data URI prefix) and an
    optional ``image_mime_type``. Capped to keep request size and cost bounded.
    """
    images: list[dict[str, str]] = []
    for frame in payload.get("frame_samples") or []:
        if not isinstance(frame, dict):
            continue
        data = frame.get("image_base64")
        if not data:
            continue
        images.append(
            {
                "mime_type": str(frame.get("image_mime_type") or "image/jpeg"),
                "data": str(data),
            }
        )
        if len(images) >= limit:
            break
    return images


def _schema_for_gemini(schema: dict[str, Any]) -> dict[str, Any]:
    """Trim Pydantic JSON Schema to the subset expected by Gemini structured output."""
    if isinstance(schema, dict):
        cleaned: dict[str, Any] = {}
        for key, value in schema.items():
            if key in {"title", "default"}:
                continue
            if key == "const":
                cleaned["enum"] = [value]
                continue
            cleaned[key] = _schema_for_gemini(value)
        return cleaned
    if isinstance(schema, list):
        return [_schema_for_gemini(item) for item in schema]
    return schema


def _dry_run_profile_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    creator = payload.get("creator", payload)
    country = creator.get("country") if creator.get("country") in {"MX", "PE", "EC"} else "unknown"
    contact_channels: list[str] = []
    if creator.get("instagram_url"):
        contact_channels.append("instagram")
    if creator.get("contact_email"):
        contact_channels.append("email")
    if creator.get("profile_url"):
        contact_channels.append("tiktok")

    bio = str(creator.get("bio") or "")
    beauty_relevance = 70 if any(term in bio.lower() for term in ("beauty", "skincare", "makeup", "kbeauty")) else 45

    return {
        "status": "ok",
        "creator_type": "beauty_reviewer" if beauty_relevance >= 60 else "unknown",
        "primary_country": country,
        "language": creator.get("language", "es"),
        "beauty_relevance": beauty_relevance,
        "contact_available": bool(contact_channels),
        "contact_channels": contact_channels,
        "sponsorship_experience": "likely" if "ad" in bio.lower() or "collab" in bio.lower() else "none",
        "category_tags": ["skincare"] if beauty_relevance >= 60 else [],
        "risk_notes": [],
        "evidence": ["Dry-run profile fields were provided."],
        "missing_data": [] if country != "unknown" else ["country"],
        "confidence": 0.72 if country != "unknown" else 0.55,
        "review_required": country == "unknown" or 40 <= beauty_relevance <= 60,
        "review_required_reason": "profile_context_limited" if country == "unknown" or 40 <= beauty_relevance <= 60 else None,
        "summary": "Dry-run profile analysis placeholder validated against schema.",
    }


def _dry_run_comment_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    comments = payload.get("comments", [])
    comment_texts = [str(item.get("comment_text", item)) for item in comments[:5]]
    where_to_buy = sum(1 for text in comment_texts if "donde" in text.lower() or "link" in text.lower())
    price_questions = sum(1 for text in comment_texts if "precio" in text.lower())

    return {
        "status": "ok",
        "positive_sentiment_ratio": 0.5 if comment_texts else 0,
        "negative_sentiment_ratio": 0,
        "purchase_intent_comments": where_to_buy + price_questions,
        "where_to_buy_comments": where_to_buy,
        "price_questions": price_questions,
        "skin_concern_questions": 0,
        "spam_or_low_quality_ratio": 0,
        "representative_comments": comment_texts,
        "insights": "Dry-run comment analysis placeholder validated against schema.",
        "evidence": ["Dry-run comment samples were provided."],
        "missing_data": [] if comment_texts else ["comments"],
        "confidence": 0.7 if comment_texts else 0.4,
        "review_required": not comment_texts,
        "review_required_reason": "comment_samples_missing" if not comment_texts else None,
    }


def _dry_run_multimodal_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    video = payload.get("video", payload)
    transcript = str(video.get("transcript") or payload.get("transcript") or "")
    caption = str(video.get("caption") or "")
    frame_samples = payload.get("frame_samples", [])
    combined_text = f"{caption} {transcript}".lower()

    product_terms = {
        "sunscreen": ("spf", "protector", "bloqueador", "solar"),
        "calming_serum": ("serum", "calmante", "barrera", "rojeces"),
        "cleanser": ("limpiador", "limpieza", "cleanser"),
        "sheet_mask": ("mascarilla", "mask"),
        "cushion_foundation": ("cushion", "base", "maquillaje"),
    }
    visible_product_types = [
        category
        for category, terms in product_terms.items()
        if any(term in combined_text for term in terms)
    ]
    product_visibility = 70 if visible_product_types else 35
    if frame_samples:
        product_visibility += 10

    detected_risks: list[str] = []
    if any(term in combined_text for term in ("cura", "trata acne", "dermatitis")):
        detected_risks.append("potential_medical_or_treatment_claim")

    brand_safety_score = 55 if detected_risks else 82
    review_required = bool(detected_risks) or not frame_samples

    return {
        "status": "ok",
        "product_visibility_score": min(product_visibility, 100),
        "skincare_context_score": 78 if "skin" in combined_text or "piel" in combined_text else 55,
        "content_quality_score": 72 if frame_samples else 50,
        "brand_safety_score": brand_safety_score,
        "commerce_signal_score": 65 if any(term in combined_text for term in ("link", "comprar", "codigo", "descuento")) else 40,
        "audio_transcript_available": bool(transcript),
        "visible_product_types": visible_product_types[:5],
        "frame_observations": [
            str(item.get("description", item)) for item in frame_samples[:5]
        ],
        "detected_risks": detected_risks,
        "scene_summary": "Dry-run multimodal analysis based on provided caption, transcript, and frame descriptions.",
        "suggested_campaign_angle": "Use as a product review or routine demonstration if human review confirms visual fit.",
        "evidence": ["Dry-run multimodal inputs were provided."],
        "missing_data": [] if frame_samples else ["frame_samples"],
        "confidence": 0.72 if frame_samples else 0.52,
        "review_required": review_required,
        "review_required_reason": "multimodal_review_required" if review_required else None,
    }


def _dry_run_recent_posts_screen(payload: dict[str, Any]) -> dict[str, Any]:
    posts = list(payload.get("recent_posts", []))[:20]
    expected_post_count = int(payload.get("expected_post_count") or 20)
    post_count = len(posts)
    texts = [
        " ".join(
            [
                str(post.get("caption") or ""),
                str(post.get("transcript") or ""),
                " ".join(str(tag) for tag in post.get("hashtags", [])),
            ]
        ).lower()
        for post in posts
    ]

    beauty_terms = (
        "beauty",
        "belleza",
        "skincare",
        "skin care",
        "piel",
        "maquillaje",
        "rutina",
        "spf",
        "protector",
        "serum",
        "limpiador",
        "mascarilla",
    )
    kbeauty_terms = ("kbeauty", "k-beauty", "coreano", "coreana", "korean")
    commerce_terms = ("link", "codigo", "código", "descuento", "comprar", "tienda", "precio", "donde")
    risk_terms = ("cura", "curar", "trata acne", "dermatitis", "melasma", "resultado garantizado")
    product_terms = {
        "sunscreen": ("spf", "protector", "bloqueador", "solar"),
        "calming_serum": ("serum", "calmante", "barrera", "rojeces"),
        "cleanser": ("limpiador", "limpieza", "cleanser", "doble limpieza"),
        "sheet_mask": ("mascarilla", "mask"),
        "cushion_foundation": ("cushion", "base", "maquillaje"),
    }

    def ratio_for(terms: tuple[str, ...]) -> float:
        if not texts:
            return 0.0
        matched = sum(1 for text in texts if any(term in text for term in terms))
        return matched / len(texts)

    beauty_ratio = ratio_for(beauty_terms)
    kbeauty_ratio = ratio_for(kbeauty_terms)
    commerce_ratio = ratio_for(commerce_terms)
    risk_matches = sorted({term for text in texts for term in risk_terms if term in text})
    matched_categories = [
        category
        for category, terms in product_terms.items()
        if any(any(term in text for term in terms) for text in texts)
    ]

    view_counts = [int(post.get("view_count") or 0) for post in posts if post.get("view_count") is not None]
    consistency_score = min(100.0, 45.0 + beauty_ratio * 35.0 + min(post_count, expected_post_count) / expected_post_count * 20.0)
    if view_counts:
        sorted_views = sorted(view_counts)
        median_view = sorted_views[len(sorted_views) // 2]
        if median_view >= 10000:
            consistency_score = min(100.0, consistency_score + 6.0)

    skincare_relevance_score = min(100.0, beauty_ratio * 70.0 + kbeauty_ratio * 20.0 + (10.0 if matched_categories else 0.0))
    commerce_signal_score = min(100.0, commerce_ratio * 85.0 + 10.0)
    brand_safety_score = 55.0 if risk_matches else 88.0
    suitability_score = round(
        skincare_relevance_score * 0.34
        + consistency_score * 0.26
        + commerce_signal_score * 0.18
        + brand_safety_score * 0.17
        + min(post_count, expected_post_count) / expected_post_count * 5.0,
        2,
    )

    coverage_gaps: list[str] = []
    if post_count < expected_post_count:
        coverage_gaps.append("recent_posts_below_20")
    if not any(post.get("transcript") for post in posts):
        coverage_gaps.append("transcripts_missing")
    if not matched_categories:
        coverage_gaps.append("product_category_signal_missing")
    if commerce_ratio == 0:
        coverage_gaps.append("commerce_intent_signal_missing")

    review_required = bool(risk_matches) or post_count < expected_post_count or 50 <= suitability_score < 75
    if risk_matches:
        decision = "human_review"
        next_step = "operator_review"
        review_reason = "brand_safety_precheck_risk"
    elif post_count < expected_post_count:
        decision = "human_review"
        next_step = "collect_more_recent_posts"
        review_reason = "insufficient_recent_posts"
    elif suitability_score >= 75:
        decision = "pass_to_full_analysis"
        next_step = "run_full_profile_comment_multimodal_analysis"
        review_reason = None
    elif suitability_score >= 50:
        decision = "human_review"
        next_step = "operator_review"
        review_reason = "borderline_recent_content_fit"
    else:
        decision = "recheck_later"
        next_step = "do_not_prioritize"
        review_reason = None

    evidence = [
        f"Analyzed {post_count} recent posts from approved inputs.",
        f"Beauty content ratio: {beauty_ratio:.2f}.",
    ]
    if matched_categories:
        evidence.append(f"Matched product categories: {', '.join(matched_categories[:5])}.")

    return {
        "status": "ok",
        "post_count_analyzed": post_count,
        "expected_post_count": expected_post_count,
        "suitability_decision": decision,
        "suitability_score": suitability_score,
        "beauty_content_ratio": round(beauty_ratio, 3),
        "kbeauty_signal_ratio": round(kbeauty_ratio, 3),
        "skincare_relevance_score": round(skincare_relevance_score, 2),
        "commerce_signal_score": round(commerce_signal_score, 2),
        "consistency_score": round(consistency_score, 2),
        "brand_safety_precheck_score": brand_safety_score,
        "matched_product_categories": matched_categories[:5],
        "recent_post_observations": [
            "Recent content screen uses captions, transcripts, hashtags, and public metrics provided through approved sources.",
            "Pass decisions should continue to profile, comment, and multimodal analysis before outreach.",
        ],
        "coverage_gaps": coverage_gaps,
        "risk_notes": risk_matches,
        "next_step": next_step,
        "evidence": evidence[:5],
        "missing_data": coverage_gaps,
        "confidence": 0.78 if post_count >= expected_post_count and not coverage_gaps else 0.58,
        "review_required": review_required,
        "review_required_reason": review_reason if review_required else None,
    }


def _dry_run_final_review(payload: dict[str, Any]) -> dict[str, Any]:
    score = payload.get("score", {})
    final_score = float(score.get("final_score", 0) or 0)
    risk_penalty = float(score.get("risk_penalty", 0) or 0)
    if risk_penalty >= 20:
        recommendation = "avoid"
        segment = "avoid"
    elif final_score >= 75:
        recommendation = "approve_for_outreach"
        segment = "review_creator"
    else:
        recommendation = "human_review"
        segment = "review_creator"

    return {
        "status": "ok",
        "recommendation": recommendation,
        "recommended_products": ["sunscreen"],
        "recommended_campaign_angle": "Dry-run K-beauty product review angle.",
        "creator_segment": segment,
        "strengths": ["Profile and score inputs were provided."],
        "risks": [] if risk_penalty < 20 else ["Risk penalty is high."],
        "missing_data": [],
        "operator_notes": "Dry-run final review placeholder.",
        "evidence": ["Dry-run final review used deterministic score input."],
        "confidence": 0.7,
        "review_required": recommendation != "approve_for_outreach",
        "review_required_reason": "human_review_recommended" if recommendation != "approve_for_outreach" else None,
    }
