from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator


CountryCode: TypeAlias = Literal["MX", "PE", "EC", "unknown"]
ProductCategory: TypeAlias = Literal[
    "sunscreen",
    "calming_serum",
    "cleanser",
    "sheet_mask",
    "cushion_foundation",
]


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceSchema(StrictSchema):
    status: Literal["ok"]
    evidence: list[str] = Field(min_length=1, max_length=5)
    missing_data: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(ge=0, le=1)
    review_required: bool = False
    review_required_reason: str | None = None

    @model_validator(mode="after")
    def require_review_reason(self) -> "EvidenceSchema":
        if self.review_required and not self.review_required_reason:
            raise ValueError("review_required_reason is required when review_required=true")
        return self


class RejectedAnalysisOutput(StrictSchema):
    status: Literal["rejected"]
    reason: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class CreatorProfileAnalysisOutput(EvidenceSchema):
    creator_type: Literal[
        "beauty_reviewer",
        "makeup_artist",
        "skincare_educator",
        "lifestyle",
        "commerce_creator",
        "ugc_creator",
        "unknown",
    ]
    primary_country: CountryCode
    language: str = Field(min_length=2, max_length=10)
    beauty_relevance: float = Field(ge=0, le=100)
    contact_available: bool
    contact_channels: list[Literal["tiktok", "instagram", "email", "whatsapp", "other"]] = Field(
        default_factory=list,
        max_length=5,
    )
    sponsorship_experience: Literal["none", "likely", "confirmed"]
    category_tags: list[str] = Field(default_factory=list, max_length=10)
    risk_notes: list[str] = Field(default_factory=list, max_length=10)
    summary: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def contact_channels_match_availability(self) -> "CreatorProfileAnalysisOutput":
        if self.contact_available and not self.contact_channels:
            raise ValueError("contact_channels is required when contact_available=true")
        return self


class CommentAnalysisOutput(EvidenceSchema):
    positive_sentiment_ratio: float = Field(ge=0, le=1)
    negative_sentiment_ratio: float = Field(ge=0, le=1)
    purchase_intent_comments: int = Field(ge=0)
    where_to_buy_comments: int = Field(ge=0)
    price_questions: int = Field(ge=0)
    skin_concern_questions: int = Field(ge=0)
    spam_or_low_quality_ratio: float = Field(ge=0, le=1)
    representative_comments: list[str] = Field(default_factory=list, max_length=5)
    insights: str = Field(min_length=1, max_length=1500)

    @model_validator(mode="after")
    def sentiment_ratios_are_plausible(self) -> "CommentAnalysisOutput":
        if self.positive_sentiment_ratio + self.negative_sentiment_ratio > 1:
            raise ValueError("positive and negative sentiment ratios cannot exceed 1 combined")
        return self


class MultimodalVideoAnalysisOutput(EvidenceSchema):
    product_visibility_score: float = Field(ge=0, le=100)
    skincare_context_score: float = Field(ge=0, le=100)
    content_quality_score: float = Field(ge=0, le=100)
    brand_safety_score: float = Field(ge=0, le=100)
    commerce_signal_score: float = Field(ge=0, le=100)
    audio_transcript_available: bool
    visible_product_types: list[ProductCategory] = Field(default_factory=list, max_length=5)
    frame_observations: list[str] = Field(default_factory=list, max_length=10)
    detected_risks: list[str] = Field(default_factory=list, max_length=10)
    scene_summary: str = Field(min_length=1, max_length=1500)
    suggested_campaign_angle: str = Field(min_length=1, max_length=1000)


class RecentPostsScreenOutput(EvidenceSchema):
    post_count_analyzed: int = Field(ge=0, le=20)
    expected_post_count: int = Field(ge=1, le=20)
    suitability_decision: Literal[
        "pass_to_full_analysis",
        "human_review",
        "recheck_later",
        "avoid",
    ]
    suitability_score: float = Field(ge=0, le=100)
    beauty_content_ratio: float = Field(ge=0, le=1)
    kbeauty_signal_ratio: float = Field(ge=0, le=1)
    skincare_relevance_score: float = Field(ge=0, le=100)
    commerce_signal_score: float = Field(ge=0, le=100)
    consistency_score: float = Field(ge=0, le=100)
    brand_safety_precheck_score: float = Field(ge=0, le=100)
    matched_product_categories: list[ProductCategory] = Field(default_factory=list, max_length=5)
    recent_post_observations: list[str] = Field(default_factory=list, max_length=10)
    coverage_gaps: list[str] = Field(default_factory=list, max_length=10)
    risk_notes: list[str] = Field(default_factory=list, max_length=10)
    next_step: Literal[
        "run_full_profile_comment_multimodal_analysis",
        "collect_more_recent_posts",
        "operator_review",
        "do_not_prioritize",
    ]


class FinalCreatorReviewOutput(EvidenceSchema):
    recommendation: Literal["approve_for_outreach", "human_review", "recheck_later", "avoid"]
    recommended_products: list[ProductCategory] = Field(default_factory=list, max_length=5)
    recommended_campaign_angle: str = Field(min_length=1, max_length=1000)
    creator_segment: Literal[
        "viral_micro",
        "beauty_educator",
        "review_creator",
        "commerce_creator",
        "brand_builder",
        "ugc_creator",
        "avoid",
    ]
    strengths: list[str] = Field(default_factory=list, max_length=10)
    risks: list[str] = Field(default_factory=list, max_length=10)
    operator_notes: str = Field(default="", max_length=1500)


class CreatorAnalysisScoreOutput(StrictSchema):
    analysis_version: str = Field(min_length=1)
    beauty_fit_score: float = Field(ge=0, le=100)
    engagement_quality_score: float = Field(ge=0, le=100)
    audience_locality_score: float = Field(ge=0, le=100)
    commerce_intent_score: float = Field(ge=0, le=100)
    content_quality_score: float = Field(ge=0, le=100)
    collaboration_probability_score: float = Field(ge=0, le=100)
    cost_efficiency_score: float = Field(ge=0, le=100)
    risk_score: float = Field(ge=0, le=100)
    risk_penalty: float = Field(ge=0, le=30)
    final_score: float = Field(ge=0, le=100)
    segment: Literal[
        "viral_micro",
        "beauty_educator",
        "review_creator",
        "commerce_creator",
        "brand_builder",
        "ugc_creator",
        "avoid",
    ]
    recommended_products: list[ProductCategory] = Field(default_factory=list, max_length=5)
    recommended_campaign_angle: str | None = None
    ai_summary: str | None = None
    ai_evidence: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    score_confidence: float = Field(ge=0, le=1)
    review_required_reason: str | None = None


ANALYSIS_OUTPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    "profile_analysis": CreatorProfileAnalysisOutput,
    "comment_analysis": CommentAnalysisOutput,
    "multimodal_analysis": MultimodalVideoAnalysisOutput,
    "recent_posts_screen": RecentPostsScreenOutput,
    "final_review": FinalCreatorReviewOutput,
    "creator_score": CreatorAnalysisScoreOutput,
}
