from fastapi.testclient import TestClient

from app.main import app
from app.operations.workflows import evaluate_import_quality
from app.operations.workflows import match_campaign_candidates


client = TestClient(app)


def _creator(username: str = "luzskincare") -> dict:
    return {
        "creator_id": "creator-1",
        "country": "MX",
        "username": username,
        "display_name": "Luz Skincare",
        "profile_url": f"https://example.com/@{username}",
        "source_risk_level": "low",
        "bio": "K-beauty skincare SPF reviews with purchase link.",
        "platform": "tiktok",
        "follower_count": 48000,
        "avg_views": 18000,
        "final_score": 90,
        "risk_penalty": 3,
        "segment": "review_creator",
        "signals": ["SPF Authority"],
        "recommended_products": ["sunscreen"],
        "recommended_campaign_angle": "SPF review and commerce link.",
    }


def _post(index: int) -> dict:
    return {
        "url": f"https://example.com/post/{index}",
        "platform_video_id": f"video-{index}",
        "caption": "Rutina skincare con protector solar coreano SPF y link de compra.",
        "transcript": "Este protector solar coreano se siente ligero.",
        "hashtags": ["skincare", "kbeauty", "protectorsolar"],
        "view_count": 12000 + index,
        "like_count": 800,
        "comment_count": 60,
        "share_count": 12,
    }


def _screen_result() -> dict:
    return {
        "post_count_analyzed": 20,
        "expected_post_count": 20,
        "suitability_decision": "pass_to_full_analysis",
        "suitability_score": 88,
        "matched_product_categories": ["sunscreen"],
        "coverage_gaps": [],
        "risk_notes": [],
        "next_step": "run_full_profile_comment_multimodal_analysis",
    }


def test_import_quality_detects_recent_post_readiness() -> None:
    quality = evaluate_import_quality(
        [_creator()],
        {"creator-1": [_post(index) for index in range(20)]},
    )

    assert quality["overall_status"] == "needs_review"
    assert quality["posts"]["coverage_percent"] == 100
    assert quality["creator"]["country_counts"]["MX"] == 1


def test_operations_import_quality_endpoint_validates_without_database() -> None:
    response = client.post(
        "/operations/import-quality-logs",
        headers={"X-User-Role": "operator"},
        json={
            "dataset_type": "mixed",
            "source_type": "manual",
            "source_risk_level": "low",
            "creator_candidates": [_creator()],
            "recent_posts_by_creator": {"creator-1": [_post(index) for index in range(20)]},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "logged"
    assert body["persistence_status"] == "validated_not_persisted"
    assert body["quality_gate"]["posts"]["coverage_percent"] == 100


def test_operations_creator_enrichment_endpoint_returns_next_actions() -> None:
    response = client.post(
        "/operations/creator-enrichment",
        headers={"X-User-Role": "operator"},
        json={"source_risk_level": "low", "creators": [_creator()]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "enriched"
    assert body["items"][0]["commerce_readiness"] == "commerce_ready"
    assert "sunscreen" in body["items"][0]["normalized_categories"]


def test_operations_recent_screen_apply_routes_pass_to_full_analysis_queue() -> None:
    response = client.post(
        "/operations/recent-posts/apply",
        headers={"X-User-Role": "operator"},
        json={
            "source_risk_level": "low",
            "items": [
                {
                    "creator_id": "creator-1",
                    "creator_snapshot": _creator(),
                    "screen_result": _screen_result(),
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["queue_counts"]["full_analysis_queue"] == 1
    assert body["items"][0]["next_action"] == "run_profile_comment_multimodal_analysis"


def test_campaign_match_combines_creator_score_product_match_and_recent_screen() -> None:
    ranked = match_campaign_candidates(
        [_creator()],
        product_category="sunscreen",
        recent_screen_results={"creator-1": _screen_result()},
    )

    assert ranked[0]["rank"] == 1
    assert ranked[0]["priority_label"] == "priority_outreach"
    assert ranked[0]["product_match"] is True


def test_operations_campaign_match_and_outreach_plan_without_database() -> None:
    match_response = client.post(
        "/operations/campaign-match",
        headers={"X-User-Role": "campaign_manager"},
        json={
            "country": "MX",
            "product_category": "sunscreen",
            "candidates": [_creator()],
            "recent_screen_results": {"creator-1": _screen_result()},
        },
    )

    assert match_response.status_code == 200
    matched = match_response.json()["items"]
    assert matched[0]["priority_label"] == "priority_outreach"

    plan_response = client.post(
        "/operations/outreach-plan",
        headers={"X-User-Role": "operator"},
        json={
            "product_category": "sunscreen",
            "product_name": "Briwell Daily Sun",
            "candidates": matched,
        },
    )
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert plan["items"][0]["crm_status"] == "dm_drafted"
    assert plan["send_policy"]["auto_send_enabled"] is False


def test_operations_crm_board_and_performance_rollup_without_database() -> None:
    crm_response = client.post(
        "/operations/outreach-crm/board",
        headers={"X-User-Role": "operator"},
        json={
            "outreach_items": [
                {"creator_id": "creator-1", "username": "luzskincare", "crm_status": "dm_drafted"},
                {"creator_id": "creator-2", "username": "andrea", "crm_status": "approved"},
            ]
        },
    )
    assert crm_response.status_code == 200
    board = crm_response.json()["board"]
    assert board["counts"]["dm_drafted"] == 1
    assert board["manual_send_policy"]["auto_send_enabled"] is False

    rollup_response = client.post(
        "/operations/performance-rollup",
        headers={"X-User-Role": "campaign_manager"},
        json={
            "spend_usd": 200,
            "snapshots": [
                {
                    "creator_id": "creator-1",
                    "view_count": 10000,
                    "like_count": 800,
                    "comment_count": 80,
                    "share_count": 20,
                    "click_count": 200,
                    "conversion_count": 12,
                    "revenue_usd": 480,
                }
            ],
        },
    )
    assert rollup_response.status_code == 200
    rollup = rollup_response.json()["rollup"]
    assert rollup["summary"]["roas"] == 2.4
    assert rollup["creator_leaderboard"][0]["creator_id"] == "creator-1"
