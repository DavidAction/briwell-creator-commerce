from decimal import Decimal

from app.workers.scoring_handoff import (
    CreatorScoringHandoffRequest,
    build_creator_score_input,
    run_creator_scoring_handoff,
    score_output_from_persisted_row,
)


def sample_handoff_request(source_risk_level: str = "low") -> CreatorScoringHandoffRequest:
    return CreatorScoringHandoffRequest(
        creator_id="creator-1",
        source_risk_level=source_risk_level,
        creator_snapshot={
            "country": "MX",
            "username": "creator_mx",
            "follower_count": 18000,
        },
        video_metrics={
            "avg_view_count": 25000,
            "engagement_rate": 0.08,
        },
        profile_analysis={
            "status": "ok",
            "creator_type": "beauty_reviewer",
            "primary_country": "MX",
            "language": "es",
            "beauty_relevance": 84,
            "contact_available": True,
            "contact_channels": ["tiktok", "instagram"],
            "sponsorship_experience": "likely",
            "category_tags": ["skincare"],
            "risk_notes": [],
            "evidence": ["Bio and recent content focus on skincare."],
            "missing_data": [],
            "confidence": 0.82,
            "review_required": False,
            "review_required_reason": None,
            "summary": "Strong skincare creator fit.",
        },
        comment_analysis={
            "status": "ok",
            "positive_sentiment_ratio": 0.7,
            "negative_sentiment_ratio": 0.05,
            "purchase_intent_comments": 3,
            "where_to_buy_comments": 2,
            "price_questions": 1,
            "skin_concern_questions": 2,
            "spam_or_low_quality_ratio": 0.05,
            "representative_comments": ["Donde lo compro?", "Precio?"],
            "insights": "Comments show purchase intent and product questions.",
            "evidence": ["Manual comment sample contains where-to-buy questions."],
            "missing_data": [],
            "confidence": 0.8,
            "review_required": False,
            "review_required_reason": None,
        },
        final_review={
            "status": "ok",
            "recommendation": "approve_for_outreach",
            "recommended_products": ["sunscreen"],
            "recommended_campaign_angle": "K-beauty SPF routine with shopping link.",
            "creator_segment": "beauty_educator",
            "strengths": ["Strong skincare relevance"],
            "risks": [],
            "missing_data": [],
            "operator_notes": "Good seed candidate.",
            "evidence": ["Final review approved outreach."],
            "confidence": 0.76,
            "review_required": False,
            "review_required_reason": None,
        },
    )


def test_build_creator_score_input_maps_ai_outputs_to_score_dimensions() -> None:
    score_input = build_creator_score_input(
        sample_handoff_request(),
        source_risk_level="low",
    )

    assert score_input.beauty_fit_score == 84
    assert score_input.audience_locality_score == 92
    assert score_input.risk_score == 6.5
    assert score_input.risk_penalty == 2.27
    assert score_input.recommended_products == ["sunscreen"]
    assert score_input.score_confidence == 0.79
    assert score_input.ai_evidence[0]["source"] == "profile_analysis"


def test_run_creator_scoring_handoff_calculates_score_without_database() -> None:
    result = run_creator_scoring_handoff(sample_handoff_request())

    assert result.status == "scored"
    assert result.persistence_status == "validated_not_persisted"
    assert result.score is not None
    assert result.score.final_score > 75
    assert result.score.segment == "beauty_educator"
    assert result.score.recommended_campaign_angle == "K-beauty SPF routine with shopping link."


def test_run_creator_scoring_handoff_rejects_high_risk_source() -> None:
    result = run_creator_scoring_handoff(sample_handoff_request(source_risk_level="high"))

    assert result.status == "rejected"
    assert result.score is None
    assert result.persistence_status == "not_applicable"
    assert result.review_notes == ["source_risk_not_allowed"]


def test_score_output_from_persisted_row_ignores_repository_metadata() -> None:
    persisted_row = {
        "id": "analysis-1",
        "creator_id": "creator-1",
        "created_at": "2026-06-17T00:00:00Z",
        "analysis_version": "v0.1",
        "beauty_fit_score": Decimal("80.0"),
        "engagement_quality_score": Decimal("70.0"),
        "audience_locality_score": Decimal("90.0"),
        "commerce_intent_score": Decimal("60.0"),
        "content_quality_score": Decimal("75.0"),
        "collaboration_probability_score": Decimal("65.0"),
        "cost_efficiency_score": Decimal("70.0"),
        "risk_score": Decimal("20.0"),
        "risk_penalty": Decimal("5.0"),
        "final_score": Decimal("69.0"),
        "segment": "beauty_educator",
        "recommended_products": ["sunscreen"],
        "recommended_campaign_angle": "Review angle",
        "ai_summary": "Summary",
        "ai_evidence": [{"source": "score"}],
        "score_confidence": Decimal("0.8"),
        "review_required_reason": "human_review_score_band",
    }

    score = score_output_from_persisted_row(persisted_row)

    assert score.final_score == 69
    assert score.segment == "beauty_educator"
