from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.db import database_enabled
from app.core.policy import PolicyError, require_allowed_source_risk
from app.repositories import creator_analyses as creator_analysis_repository
from app.schemas.analysis import (
    CommentAnalysisOutput,
    CreatorAnalysisScoreOutput,
    CreatorProfileAnalysisOutput,
    FinalCreatorReviewOutput,
    ProductCategory,
)
from app.scoring.creator_score import CreatorScoreInput, calculate_creator_score, clamp


class CreatorScoringHandoffRequest(BaseModel):
    creator_id: str = Field(min_length=1)
    source_risk_level: str = Field(min_length=1)
    creator_snapshot: dict[str, Any] = Field(default_factory=dict)
    video_metrics: dict[str, Any] = Field(default_factory=dict)
    profile_analysis: CreatorProfileAnalysisOutput | None = None
    comment_analysis: CommentAnalysisOutput | None = None
    final_review: FinalCreatorReviewOutput | None = None
    persist_score: bool = True


class CreatorScoringHandoffResult(BaseModel):
    status: Literal["scored", "rejected"]
    creator_id: str
    source_risk_level: str
    persisted_analysis_id: str | None = None
    score_input: dict[str, Any] | None = None
    score: CreatorAnalysisScoreOutput | None = None
    persistence_status: Literal["persisted", "validated_not_persisted", "not_applicable"]
    review_notes: list[str] = Field(default_factory=list)


def run_creator_scoring_handoff(
    request: CreatorScoringHandoffRequest,
) -> CreatorScoringHandoffResult:
    try:
        source_risk_level = require_allowed_source_risk(request.source_risk_level)
    except PolicyError as exc:
        return CreatorScoringHandoffResult(
            status="rejected",
            creator_id=request.creator_id,
            source_risk_level=request.source_risk_level,
            persistence_status="not_applicable",
            review_notes=[str(exc)],
        )

    score_input = build_creator_score_input(request, source_risk_level=source_risk_level)
    score = calculate_creator_score(score_input)

    if database_enabled() and request.persist_score:
        persisted = creator_analysis_repository.upsert_creator_analysis(
            creator_id=request.creator_id,
            payload=score.model_dump(),
        )
        score = score_output_from_persisted_row(persisted)
        persisted_analysis_id = str(persisted.get("id")) if persisted.get("id") else None
        persistence_status = "persisted"
    else:
        persisted_analysis_id = None
        persistence_status = "validated_not_persisted"

    return CreatorScoringHandoffResult(
        status="scored",
        creator_id=request.creator_id,
        source_risk_level=source_risk_level,
        persisted_analysis_id=persisted_analysis_id,
        score_input=score_input.model_dump(),
        score=score,
        persistence_status=persistence_status,
        review_notes=review_notes_for_handoff(request),
    )


def score_output_from_persisted_row(row: dict[str, Any]) -> CreatorAnalysisScoreOutput:
    score_payload = {
        field_name: row[field_name]
        for field_name in CreatorAnalysisScoreOutput.model_fields
        if field_name in row
    }
    return CreatorAnalysisScoreOutput.model_validate(score_payload)


def build_creator_score_input(
    request: CreatorScoringHandoffRequest,
    source_risk_level: str,
) -> CreatorScoreInput:
    risk_score = risk_score_from_analysis(request, source_risk_level=source_risk_level)
    return CreatorScoreInput(
        beauty_fit_score=beauty_fit_score(request),
        engagement_quality_score=engagement_quality_score(request),
        audience_locality_score=audience_locality_score(request),
        commerce_intent_score=commerce_intent_score(request),
        content_quality_score=content_quality_score(request),
        collaboration_probability_score=collaboration_probability_score(request),
        cost_efficiency_score=cost_efficiency_score(request),
        risk_score=risk_score,
        risk_penalty=round(clamp(risk_score * 0.35, 0, 30), 2),
        recommended_products=recommended_products(request),
        recommended_campaign_angle=recommended_campaign_angle(request),
        ai_summary=ai_summary(request),
        ai_evidence=ai_evidence(request),
        score_confidence=score_confidence(request),
        review_required_reason=review_required_reason(request),
    )


def beauty_fit_score(request: CreatorScoringHandoffRequest) -> float:
    if request.profile_analysis:
        return round(request.profile_analysis.beauty_relevance, 2)
    if request.final_review and request.final_review.recommendation == "approve_for_outreach":
        return 70
    return 50


def engagement_quality_score(request: CreatorScoringHandoffRequest) -> float:
    score = 50.0
    if request.comment_analysis:
        comment = request.comment_analysis
        score = (
            45
            + comment.positive_sentiment_ratio * 30
            - comment.negative_sentiment_ratio * 20
            + min(comment.purchase_intent_comments, 8) * 3
            - comment.spam_or_low_quality_ratio * 25
        )

    engagement_rate = numeric_metric(request.video_metrics, "engagement_rate")
    if engagement_rate is not None:
        metric_score = clamp(engagement_rate * 1000, 0, 100)
        score = (score + metric_score) / 2

    return round(clamp(score, 0, 100), 2)


def audience_locality_score(request: CreatorScoringHandoffRequest) -> float:
    snapshot_country = request.creator_snapshot.get("country")
    profile_country = request.profile_analysis.primary_country if request.profile_analysis else None
    if profile_country in {"MX", "PE", "EC"} and snapshot_country == profile_country:
        return 92
    if profile_country in {"MX", "PE", "EC"}:
        return 82
    if snapshot_country in {"MX", "PE", "EC"}:
        return 72
    return 42


def commerce_intent_score(request: CreatorScoringHandoffRequest) -> float:
    score = 35.0
    if request.comment_analysis:
        comment = request.comment_analysis
        score += min(comment.purchase_intent_comments, 8) * 5
        score += min(comment.where_to_buy_comments, 5) * 4
        score += min(comment.price_questions, 5) * 3
    if request.profile_analysis and request.profile_analysis.creator_type == "commerce_creator":
        score += 15
    if request.final_review and request.final_review.recommendation == "approve_for_outreach":
        score += 10
    return round(clamp(score, 0, 100), 2)


def content_quality_score(request: CreatorScoringHandoffRequest) -> float:
    base = 55.0
    if request.profile_analysis:
        base = 50 + request.profile_analysis.beauty_relevance * 0.3

    avg_view_count = numeric_metric(request.video_metrics, "avg_view_count")
    if avg_view_count is not None:
        if avg_view_count >= 100_000:
            view_score = 92
        elif avg_view_count >= 30_000:
            view_score = 82
        elif avg_view_count >= 10_000:
            view_score = 70
        elif avg_view_count >= 2_000:
            view_score = 58
        else:
            view_score = 42
        base = (base + view_score) / 2

    return round(clamp(base, 0, 100), 2)


def collaboration_probability_score(request: CreatorScoringHandoffRequest) -> float:
    score = 35.0
    if request.profile_analysis:
        if request.profile_analysis.contact_available:
            score += 25
        if request.profile_analysis.sponsorship_experience == "likely":
            score += 15
        elif request.profile_analysis.sponsorship_experience == "confirmed":
            score += 25
    if request.final_review:
        if request.final_review.recommendation == "approve_for_outreach":
            score += 10
        elif request.final_review.recommendation == "avoid":
            score -= 25
    return round(clamp(score, 0, 100), 2)


def cost_efficiency_score(request: CreatorScoringHandoffRequest) -> float:
    follower_count = numeric_metric(request.creator_snapshot, "follower_count")
    if follower_count is None:
        return 55
    if follower_count < 1_000:
        return 45
    if follower_count <= 100_000:
        return 85
    if follower_count <= 500_000:
        return 70
    return 55


def risk_score_from_analysis(
    request: CreatorScoringHandoffRequest,
    source_risk_level: str,
) -> float:
    score = {"low": 5, "low_medium": 15, "medium": 30}.get(source_risk_level, 50)
    if request.profile_analysis:
        score += min(len(request.profile_analysis.risk_notes) * 5, 20)
        score += min(len(request.profile_analysis.missing_data) * 3, 15)
        if request.profile_analysis.review_required:
            score += 8
    if request.comment_analysis:
        score += min(len(request.comment_analysis.missing_data) * 3, 15)
        score += request.comment_analysis.spam_or_low_quality_ratio * 30
        if request.comment_analysis.review_required:
            score += 8
    if request.final_review:
        score += min(len(request.final_review.risks) * 5, 20)
        score += min(len(request.final_review.missing_data) * 3, 15)
        if request.final_review.recommendation == "avoid":
            score += 30
        if request.final_review.review_required:
            score += 8
    return round(clamp(score, 0, 100), 2)


def recommended_products(
    request: CreatorScoringHandoffRequest,
) -> list[ProductCategory]:
    if request.final_review and request.final_review.recommended_products:
        return request.final_review.recommended_products

    tags = []
    if request.profile_analysis:
        tags = [tag.lower() for tag in request.profile_analysis.category_tags]
    if any("clean" in tag for tag in tags):
        return ["cleanser"]
    if any("mask" in tag for tag in tags):
        return ["sheet_mask"]
    if any("makeup" in tag or "cushion" in tag for tag in tags):
        return ["cushion_foundation"]
    if any("calm" in tag or "sensitive" in tag for tag in tags):
        return ["calming_serum"]
    return ["sunscreen"]


def recommended_campaign_angle(request: CreatorScoringHandoffRequest) -> str:
    if request.final_review:
        return request.final_review.recommended_campaign_angle
    country = request.creator_snapshot.get("country", "LatAm")
    product = recommended_products(request)[0]
    return f"K-beauty {product} review angle for {country} beauty audience."


def ai_summary(request: CreatorScoringHandoffRequest) -> str:
    parts: list[str] = []
    if request.profile_analysis:
        parts.append(request.profile_analysis.summary)
    if request.comment_analysis:
        parts.append(request.comment_analysis.insights)
    if request.final_review and request.final_review.operator_notes:
        parts.append(request.final_review.operator_notes)
    return " ".join(parts)[:1500] if parts else "Score generated from limited analysis inputs."


def ai_evidence(request: CreatorScoringHandoffRequest) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    if request.profile_analysis:
        evidence.append(
            {
                "source": "profile_analysis",
                "evidence": request.profile_analysis.evidence,
                "confidence": request.profile_analysis.confidence,
            }
        )
    if request.comment_analysis:
        evidence.append(
            {
                "source": "comment_analysis",
                "evidence": request.comment_analysis.evidence,
                "confidence": request.comment_analysis.confidence,
            }
        )
    if request.final_review:
        evidence.append(
            {
                "source": "final_review",
                "evidence": request.final_review.evidence,
                "confidence": request.final_review.confidence,
            }
        )
    return evidence


def score_confidence(request: CreatorScoringHandoffRequest) -> float:
    values: list[float] = []
    if request.profile_analysis:
        values.append(request.profile_analysis.confidence)
    if request.comment_analysis:
        values.append(request.comment_analysis.confidence)
    if request.final_review:
        values.append(request.final_review.confidence)
    if not values:
        return 0.55
    return round(sum(values) / len(values), 2)


def review_required_reason(request: CreatorScoringHandoffRequest) -> str | None:
    reasons = review_notes_for_handoff(request)
    return ";".join(reasons) if reasons else None


def review_notes_for_handoff(request: CreatorScoringHandoffRequest) -> list[str]:
    reasons: list[str] = []
    if not any([request.profile_analysis, request.comment_analysis, request.final_review]):
        reasons.append("insufficient_analysis_inputs")
    if request.profile_analysis and request.profile_analysis.review_required:
        reasons.append(request.profile_analysis.review_required_reason or "profile_review_required")
    if request.comment_analysis and request.comment_analysis.review_required:
        reasons.append(request.comment_analysis.review_required_reason or "comment_review_required")
    if request.final_review and request.final_review.review_required:
        reasons.append(request.final_review.review_required_reason or "final_review_required")
    return reasons


def numeric_metric(payload: dict[str, Any], key: str) -> float | None:
    value = payload.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
