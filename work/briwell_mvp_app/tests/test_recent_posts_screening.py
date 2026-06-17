from app.workers.recent_posts_screening import RecentPostSnapshot
from app.workers.recent_posts_screening import RecentPostsScreenRequest
from app.workers.recent_posts_screening import run_recent_posts_screen


def _spf_post(index: int) -> RecentPostSnapshot:
    return RecentPostSnapshot(
        video_id=f"video-{index}",
        caption="Rutina skincare con protector solar coreano SPF y link de compra.",
        transcript="Este protector solar coreano se siente ligero en la piel.",
        hashtags=["skincare", "kbeauty", "protectorsolar"],
        view_count=12000 + index,
        like_count=900,
        comment_count=80,
    )


def test_recent_posts_screen_passes_strong_twenty_post_creator() -> None:
    result = run_recent_posts_screen(
        RecentPostsScreenRequest(
            creator_id="creator-1",
            source_risk_level="low",
            recent_posts=[_spf_post(index) for index in range(20)],
            creator_snapshot={"username": "luzskincare", "country": "MX"},
            product_context={"product_category": "sunscreen"},
        )
    )

    assert result.status == "success"
    assert result.result.status == "ok"
    output = result.result.output
    assert output["post_count_analyzed"] == 20
    assert output["suitability_decision"] == "pass_to_full_analysis"
    assert output["next_step"] == "run_full_profile_comment_multimodal_analysis"
    assert output["suitability_score"] >= 75
    assert "sunscreen" in output["matched_product_categories"]
    assert result.invocation_log["task_type"] == "recent_posts_screen"


def test_recent_posts_screen_requires_review_when_less_than_twenty_posts() -> None:
    result = run_recent_posts_screen(
        RecentPostsScreenRequest(
            creator_id="creator-1",
            source_risk_level="low",
            recent_posts=[_spf_post(index) for index in range(8)],
        )
    )

    assert result.status == "success"
    output = result.result.output
    assert output["post_count_analyzed"] == 8
    assert output["suitability_decision"] == "human_review"
    assert output["next_step"] == "collect_more_recent_posts"
    assert "recent_posts_below_20" in output["coverage_gaps"]
    assert result.result.review_required_reason == "insufficient_recent_posts"


def test_recent_posts_screen_blocks_high_risk_source_before_provider_call() -> None:
    result = run_recent_posts_screen(
        RecentPostsScreenRequest(
            creator_id="creator-1",
            source_risk_level="high",
            recent_posts=[_spf_post(1)],
            expected_post_count=1,
        )
    )

    assert result.status == "skipped"
    assert result.result.status == "rejected"
    assert result.invocation_log["error_message"] == "source_risk_not_allowed"
