import pytest

from app.ai.schema_validation import AnalysisSchemaError, validate_analysis_output


def test_profile_analysis_schema_accepts_valid_output() -> None:
    validated = validate_analysis_output(
        "profile_analysis",
        {
            "status": "ok",
            "creator_type": "beauty_reviewer",
            "primary_country": "MX",
            "language": "es",
            "beauty_relevance": 82,
            "contact_available": True,
            "contact_channels": ["tiktok"],
            "sponsorship_experience": "likely",
            "category_tags": ["skincare"],
            "risk_notes": [],
            "evidence": ["Bio mentions skincare reviews."],
            "missing_data": [],
            "confidence": 0.84,
            "review_required": False,
            "review_required_reason": None,
            "summary": "Strong skincare review fit.",
        },
    )
    assert validated.model_dump()["primary_country"] == "MX"


def test_profile_analysis_schema_rejects_contact_without_channel() -> None:
    with pytest.raises(AnalysisSchemaError):
        validate_analysis_output(
            "profile_analysis",
            {
                "status": "ok",
                "creator_type": "beauty_reviewer",
                "primary_country": "MX",
                "language": "es",
                "beauty_relevance": 82,
                "contact_available": True,
                "contact_channels": [],
                "sponsorship_experience": "likely",
                "category_tags": ["skincare"],
                "risk_notes": [],
                "evidence": ["Bio mentions skincare reviews."],
                "missing_data": [],
                "confidence": 0.84,
                "review_required": False,
                "review_required_reason": None,
                "summary": "Strong skincare review fit.",
            },
        )


def test_comment_analysis_schema_rejects_impossible_sentiment_ratios() -> None:
    with pytest.raises(AnalysisSchemaError):
        validate_analysis_output(
            "comment_analysis",
            {
                "status": "ok",
                "positive_sentiment_ratio": 0.8,
                "negative_sentiment_ratio": 0.5,
                "purchase_intent_comments": 2,
                "where_to_buy_comments": 1,
                "price_questions": 1,
                "skin_concern_questions": 0,
                "spam_or_low_quality_ratio": 0,
                "representative_comments": ["Donde lo compro?"],
                "insights": "Strong purchase intent.",
                "evidence": ["Where-to-buy comment present."],
                "missing_data": [],
                "confidence": 0.8,
                "review_required": False,
                "review_required_reason": None,
            },
        )


def test_final_review_schema_rejects_unknown_recommendation() -> None:
    with pytest.raises(AnalysisSchemaError):
        validate_analysis_output(
            "final_review",
            {
                "status": "ok",
                "recommendation": "send_dm_now",
                "recommended_products": ["sunscreen"],
                "recommended_campaign_angle": "Review angle.",
                "creator_segment": "review_creator",
                "strengths": ["Good fit."],
                "risks": [],
                "missing_data": [],
                "operator_notes": "",
                "evidence": ["Score is strong."],
                "confidence": 0.8,
                "review_required": False,
                "review_required_reason": None,
            },
        )


def test_unsupported_analysis_schema_rejected() -> None:
    with pytest.raises(AnalysisSchemaError):
        validate_analysis_output("unknown_task", {"status": "ok"})


def test_creator_score_schema_accepts_calculated_output() -> None:
    validated = validate_analysis_output(
        "creator_score",
        {
            "analysis_version": "v0.1",
            "beauty_fit_score": 80,
            "engagement_quality_score": 70,
            "audience_locality_score": 90,
            "commerce_intent_score": 60,
            "content_quality_score": 75,
            "collaboration_probability_score": 65,
            "cost_efficiency_score": 70,
            "risk_score": 20,
            "risk_penalty": 5,
            "final_score": 69,
            "segment": "beauty_educator",
            "recommended_products": ["sunscreen"],
            "recommended_campaign_angle": "Review angle",
            "ai_summary": "System calculated score.",
            "ai_evidence": [{"source": "score"}],
            "score_confidence": 0.8,
            "review_required_reason": "human_review_score_band",
        },
    )
    assert validated.model_dump()["final_score"] == 69
