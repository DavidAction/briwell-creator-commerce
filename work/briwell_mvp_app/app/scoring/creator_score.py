from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.analysis import CreatorAnalysisScoreOutput, ProductCategory


SCORING_RULE_VERSION = "v0.1"
SCORING_WEIGHTS = {
    "beauty_fit_score": 0.25,
    "engagement_quality_score": 0.20,
    "audience_locality_score": 0.15,
    "commerce_intent_score": 0.15,
    "content_quality_score": 0.10,
    "collaboration_probability_score": 0.10,
    "cost_efficiency_score": 0.05,
}


class CreatorScoreInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_version: str = SCORING_RULE_VERSION
    beauty_fit_score: float = Field(ge=0, le=100)
    engagement_quality_score: float = Field(ge=0, le=100)
    audience_locality_score: float = Field(ge=0, le=100)
    commerce_intent_score: float = Field(ge=0, le=100)
    content_quality_score: float = Field(ge=0, le=100)
    collaboration_probability_score: float = Field(ge=0, le=100)
    cost_efficiency_score: float = Field(ge=0, le=100)
    risk_score: float = Field(ge=0, le=100)
    risk_penalty: float = Field(ge=0, le=30)
    recommended_products: list[ProductCategory] = Field(default_factory=list, max_length=5)
    recommended_campaign_angle: str | None = None
    ai_summary: str | None = None
    ai_evidence: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    score_confidence: float = Field(ge=0, le=1)
    review_required_reason: str | None = None


def calculate_creator_score(payload: CreatorScoreInput) -> CreatorAnalysisScoreOutput:
    base_score = weighted_base_score(payload)
    final_score = clamp(base_score - payload.risk_penalty, 0, 100)
    segment = classify_segment(payload, final_score)
    review_reason = review_required_reason(payload, final_score, segment)

    return CreatorAnalysisScoreOutput.model_validate(
        {
            **payload.model_dump(),
            "analysis_version": payload.analysis_version,
            "final_score": round(final_score, 2),
            "segment": segment,
            "review_required_reason": review_reason,
        }
    )


def weighted_base_score(payload: CreatorScoreInput) -> float:
    data = payload.model_dump()
    return round(
        sum(float(data[dimension]) * weight for dimension, weight in SCORING_WEIGHTS.items()),
        2,
    )


def classify_segment(payload: CreatorScoreInput, final_score: float) -> str:
    if payload.risk_penalty >= 20 or payload.risk_score >= 80 or final_score < 45:
        return "avoid"
    if (
        payload.engagement_quality_score >= 80
        and payload.content_quality_score >= 65
        and final_score >= 70
    ):
        return "viral_micro"
    if payload.commerce_intent_score >= 75 and payload.collaboration_probability_score >= 60:
        return "commerce_creator"
    if (
        payload.beauty_fit_score >= 80
        and payload.content_quality_score >= 70
        and payload.commerce_intent_score < 75
    ):
        return "beauty_educator"
    if payload.content_quality_score >= 75 and payload.cost_efficiency_score >= 70:
        return "ugc_creator"
    if (
        payload.collaboration_probability_score >= 75
        and payload.content_quality_score >= 70
        and final_score >= 65
    ):
        return "brand_builder"
    return "review_creator"


def review_required_reason(
    payload: CreatorScoreInput,
    final_score: float,
    segment: str,
) -> str | None:
    if payload.review_required_reason:
        return payload.review_required_reason
    if payload.score_confidence < 0.7:
        return "low_score_confidence"
    if payload.risk_penalty >= 15:
        return "risk_penalty_review"
    if segment == "avoid":
        return "avoid_segment"
    if 60 <= final_score < 70:
        return "human_review_score_band"
    return None


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
