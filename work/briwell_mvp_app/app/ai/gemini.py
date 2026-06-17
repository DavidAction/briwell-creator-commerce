import json
from typing import Any

import httpx

from app.ai.adapters import AIAdapter, rejected_for_source_risk
from app.ai.contracts import AnalysisRequest, AnalysisResult
from app.ai.schema_validation import AnalysisSchemaError, validate_analysis_output
from app.core.config import settings


MODEL_BY_ALIAS = {
    "low_cost_text": "gemini-3.1-flash-lite",
    "final_review": "gemini-3.5-flash",
    "dm_generation": "gemini-3-flash",
    "multimodal_default": "gemini-3-flash",
}


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
                    "parts": [{"text": self._build_prompt(request)}],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
            },
        }
        response = httpx.post(
            url,
            params={"key": self.api_key},
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        text = body["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("Gemini response JSON must be an object.")
        return parsed

    def _build_prompt(self, request: AnalysisRequest) -> str:
        return json.dumps(
            {
                "instruction": (
                    "You are Briwell's K-beauty influencer analyst for Mexico, "
                    "Peru, and Ecuador. Return valid JSON only. Use only the "
                    "provided data. Do not invent missing facts."
                ),
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
        if request.task_type == "final_review":
            return _dry_run_final_review(request.payload)
        raise AnalysisSchemaError(f"unsupported_analysis_task:{request.task_type}")


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
