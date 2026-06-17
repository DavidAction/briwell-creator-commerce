import pytest
from pydantic import ValidationError

from app.scoring.creator_score import (
    CreatorScoreInput,
    calculate_creator_score,
    classify_segment,
    weighted_base_score,
)


def test_weighted_base_score_uses_v0_weights() -> None:
    payload = CreatorScoreInput(
        beauty_fit_score=80,
        engagement_quality_score=70,
        audience_locality_score=90,
        commerce_intent_score=60,
        content_quality_score=75,
        collaboration_probability_score=65,
        cost_efficiency_score=70,
        risk_score=20,
        risk_penalty=5,
        score_confidence=0.82,
    )
    assert weighted_base_score(payload) == 74.0


def test_calculate_creator_score_clamps_final_score_and_classifies_segment() -> None:
    payload = CreatorScoreInput(
        beauty_fit_score=90,
        engagement_quality_score=85,
        audience_locality_score=85,
        commerce_intent_score=70,
        content_quality_score=80,
        collaboration_probability_score=75,
        cost_efficiency_score=80,
        risk_score=15,
        risk_penalty=4,
        recommended_products=["sunscreen"],
        recommended_campaign_angle="K-beauty sunscreen review",
        ai_summary="Strong beauty creator fit.",
        ai_evidence=[{"source": "profile_analysis", "evidence": ["skincare bio"]}],
        score_confidence=0.86,
    )
    score = calculate_creator_score(payload)
    assert score.final_score == 78.25
    assert score.segment == "viral_micro"
    assert score.review_required_reason is None
    assert score.recommended_products == ["sunscreen"]


def test_calculate_creator_score_marks_low_confidence_for_review() -> None:
    payload = CreatorScoreInput(
        beauty_fit_score=70,
        engagement_quality_score=65,
        audience_locality_score=70,
        commerce_intent_score=65,
        content_quality_score=65,
        collaboration_probability_score=65,
        cost_efficiency_score=65,
        risk_score=20,
        risk_penalty=3,
        score_confidence=0.62,
    )
    score = calculate_creator_score(payload)
    assert score.review_required_reason == "low_score_confidence"


def test_calculate_creator_score_avoids_high_risk_candidate() -> None:
    payload = CreatorScoreInput(
        beauty_fit_score=90,
        engagement_quality_score=85,
        audience_locality_score=85,
        commerce_intent_score=80,
        content_quality_score=80,
        collaboration_probability_score=75,
        cost_efficiency_score=80,
        risk_score=85,
        risk_penalty=22,
        score_confidence=0.9,
    )
    score = calculate_creator_score(payload)
    assert score.segment == "avoid"
    assert score.review_required_reason == "risk_penalty_review"


def test_creator_score_input_rejects_direct_final_score() -> None:
    with pytest.raises(ValidationError):
        CreatorScoreInput(
            beauty_fit_score=80,
            engagement_quality_score=70,
            audience_locality_score=90,
            commerce_intent_score=60,
            content_quality_score=75,
            collaboration_probability_score=65,
            cost_efficiency_score=70,
            risk_score=20,
            risk_penalty=5,
            score_confidence=0.82,
            final_score=99,
        )


def test_classify_segment_detects_commerce_creator() -> None:
    payload = CreatorScoreInput(
        beauty_fit_score=75,
        engagement_quality_score=60,
        audience_locality_score=80,
        commerce_intent_score=85,
        content_quality_score=60,
        collaboration_probability_score=80,
        cost_efficiency_score=70,
        risk_score=20,
        risk_penalty=5,
        score_confidence=0.8,
    )
    assert classify_segment(payload, final_score=70) == "commerce_creator"
