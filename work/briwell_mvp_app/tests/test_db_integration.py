import os
import time
from types import SimpleNamespace

import pytest

from app.core.db_contract import MINIMUM_SEED_COUNTS
from app.core.db_contract import REQUIRED_ENUMS
from app.core.db_contract import REQUIRED_TABLES


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1",
    reason="Set RUN_DB_TESTS=1 with a live PostgreSQL DATABASE_URL to run DB integration tests.",
)


def test_database_connection() -> None:
    import psycopg

    from app.core.config import settings

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone()[0] == 1


def test_required_tables_exist() -> None:
    import psycopg

    from app.core.config import settings

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                """
            )
            found = {row[0] for row in cur.fetchall()}
    assert REQUIRED_TABLES.issubset(found)


def test_required_enums_exist() -> None:
    import psycopg

    from app.core.config import settings

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT typname
                FROM pg_type
                WHERE typnamespace = 'public'::regnamespace
                """
            )
            found = {row[0] for row in cur.fetchall()}
    assert REQUIRED_ENUMS.issubset(found)


def test_minimum_seed_counts_exist() -> None:
    import psycopg

    from app.core.config import settings

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            for table_name, minimum_count in MINIMUM_SEED_COUNTS.items():
                cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                assert cur.fetchone()[0] >= minimum_count


def test_db_campaign_outreach_persistence_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.compliance.claims import ClaimsCheckInput, run_claims_check
    from app.compliance.outreach_review import OutreachReviewInput, evaluate_outreach_review
    from app.core import db as db_module
    from app.repositories import campaigns
    from app.repositories import creator_analyses
    from app.repositories import creators
    from app.repositories import outreach

    monkeypatch.setattr(
        db_module,
        "settings",
        SimpleNamespace(
            use_database=True,
            database_url=os.environ["DATABASE_URL"],
        ),
    )

    suffix = str(int(time.time() * 1000))
    imported = creators.import_creators(
        source_type="manual",
        source_risk_level="low",
        items=[
            {
                "country": "MX",
                "username": f"db_e2e_creator_{suffix}",
                "profile_url": f"https://example.com/@db_e2e_creator_{suffix}",
                "display_name": "DB E2E Creator",
                "bio": "skincare and kbeauty reviews",
                "language": "es",
                "follower_count": 50000,
                "source_url": "https://example.com/manual-import",
            }
        ],
    )
    creator_id = imported[0]["id"]

    creator_analyses.upsert_creator_analysis(
        creator_id=creator_id,
        payload={
            "analysis_version": f"db_e2e_{suffix}",
            "beauty_fit_score": 90,
            "engagement_quality_score": 85,
            "audience_locality_score": 88,
            "commerce_intent_score": 80,
            "content_quality_score": 84,
            "collaboration_probability_score": 82,
            "cost_efficiency_score": 78,
            "risk_score": 10,
            "risk_penalty": 2,
            "final_score": 86,
            "segment": "review_creator",
            "recommended_products": ["sunscreen"],
            "recommended_campaign_angle": "SPF review",
            "ai_summary": "DB E2E score.",
            "ai_evidence": [{"source": "test"}],
            "score_confidence": 0.91,
            "review_required_reason": None,
        },
    )

    campaign = campaigns.create_campaign(
        {
            "name": f"DB E2E Campaign {suffix}",
            "product_id": None,
            "country": "MX",
            "product_category": "sunscreen",
            "campaign_goal": "Verify persisted outreach flow.",
            "budget": None,
            "sales_channel": None,
            "tracking_url": None,
            "coupon_code_prefix": None,
            "target_creator_count": None,
            "target_post_count": None,
            "start_date": None,
            "end_date": None,
            "status": "draft",
        }
    )

    candidates = campaigns.list_campaign_candidates(
        campaign_id=str(campaign["id"]),
        country="MX",
        product_category="sunscreen",
        min_score=70,
        max_risk_penalty=10,
        limit=10,
    )
    assert any(str(candidate["creator_id"]) == str(creator_id) for candidate in candidates)

    draft = outreach.create_dm_draft(
        creator_id=str(creator_id),
        campaign_id=str(campaign["id"]),
        dm_variant="soft_intro",
        dm_message="Hola, queremos compartir detalles de una colaboracion K-beauty para una resena honesta.",
    )
    assert draft["claims_check_status"] == "needs_review"

    claims = run_claims_check(
        ClaimsCheckInput(
            dm_message=draft["dm_message"],
            product_category="sunscreen",
            country="MX",
        )
    )
    assert claims.status == "passed"

    checked = outreach.update_claims_check_status(
        outreach_id=str(draft["id"]),
        claims_check_status=claims.status,
        operator_notes=claims.recommendation,
    )
    assert checked["claims_check_status"] == "passed"

    review = evaluate_outreach_review(
        OutreachReviewInput(
            decision="approve",
            claims_check_status="passed",
            current_status="dm_drafted",
        )
    )
    assert review.can_record is True

    approved = outreach.update_review_decision(
        outreach_id=str(draft["id"]),
        status=review.outreach_status,
        operator_notes="DB E2E approval.",
    )
    assert approved["status"] == "approved"


def test_db_talent_intake_upload_quality_and_recent20_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from app.core import db as db_module
    from app.main import app

    monkeypatch.setattr(
        db_module,
        "settings",
        SimpleNamespace(
            use_database=True,
            database_url=os.environ["DATABASE_URL"],
        ),
    )

    client = TestClient(app)
    headers = {"X-User-Role": "admin", "X-User-Email": "db-e2e@briwell.test"}
    suffix = str(int(time.time() * 1000))
    username = f"db_intake_creator_{suffix}"

    creator_import = {
        "country": "MX",
        "username": username,
        "profile_url": f"https://www.tiktok.com/@{username}",
        "display_name": "DB Intake Creator",
        "bio": "K-beauty SPF reviews with link-in-bio shopping context.",
        "language": "es",
        "follower_count": 64000,
        "source_url": "https://www.tiktok.com/search?q=kbeauty%20spf%20mx",
    }
    creator_response = client.post(
        "/creators/import",
        headers=headers,
        json={
            "source_type": "manual",
            "source_risk_level": "low",
            "items": [creator_import],
        },
    )
    assert creator_response.status_code == 200
    creator_body = creator_response.json()
    assert creator_body["status"] == "persisted"
    creator_id = creator_body["items"][0]["id"]

    recent_posts = [
        {
            "url": f"https://www.tiktok.com/@{username}/video/{7000000000000000000 + index}",
            "platform_video_id": f"{username}-recent-{index}",
            "caption": "Rutina skincare con protector solar coreano SPF y link de compra.",
            "transcript": "Protector solar coreano de textura ligera para rutina diaria.",
            "hashtags": ["skincare", "kbeauty", "protectorsolar"],
            "posted_at": "2026-06-01T12:00:00Z",
            "view_count": 18000 + index,
            "like_count": 1200 + index,
            "comment_count": 80 + index,
            "share_count": 20 + index,
            "save_count": 90 + index,
            "duration_seconds": 40,
            "thumbnail_url": f"https://cdn.briwell.local/posts/{username}-{index}.jpg",
            "raw_metadata": {"e2e": True, "row": index},
            "source_url": f"https://www.tiktok.com/@{username}/video/{7000000000000000000 + index}",
        }
        for index in range(1, 21)
    ]
    video_response = client.post(
        "/videos/import",
        headers=headers,
        json={
            "creator_id": creator_id,
            "source_type": "manual",
            "source_risk_level": "low",
            "items": recent_posts,
        },
    )
    assert video_response.status_code == 200
    assert video_response.json()["accepted"] == 20
    video_list_response = client.get(
        "/videos",
        params={"creator_id": creator_id, "limit": 25},
    )
    assert video_list_response.status_code == 200
    assert len(video_list_response.json()["items"]) >= 20

    creator_snapshot = {
        **creator_import,
        "creator_id": creator_id,
        "source_risk_level": "low",
        "platform": "tiktok",
        "avg_views": 21000,
        "engagement_rate": 6.1,
        "contact_email": "db-intake@briwell.test",
        "instagram_url": f"https://www.instagram.com/{username}",
        "final_score": 88,
        "risk_penalty": 3,
        "segment": "review_creator",
        "signals": ["SPF Authority", "K-Beauty Fit", "Commerce Intent"],
        "recommended_products": ["sunscreen"],
        "recommended_campaign_angle": "Daily SPF review with tracked commerce link.",
    }
    quality_response = client.post(
        "/operations/import-quality-logs",
        headers=headers,
        json={
            "dataset_type": "mixed",
            "upload_name": f"db-intake-e2e-{suffix}.csv",
            "source_type": "manual",
            "source_risk_level": "low",
            "expected_countries": ["MX"],
            "creator_candidates": [creator_snapshot],
            "recent_posts_by_creator": {
                creator_id: [
                    {
                        "url": post["url"],
                        "platform_video_id": post["platform_video_id"],
                        "caption": post["caption"],
                        "transcript": post["transcript"],
                        "hashtags": post["hashtags"],
                        "view_count": post["view_count"],
                        "like_count": post["like_count"],
                        "comment_count": post["comment_count"],
                        "share_count": post["share_count"],
                    }
                    for post in recent_posts
                ]
            },
        },
    )
    assert quality_response.status_code == 200
    quality_body = quality_response.json()
    assert quality_body["persistence_status"] == "persisted"
    assert quality_body["quality_gate"]["posts"]["coverage_percent"] == 100

    enrichment_response = client.post(
        "/operations/creator-enrichment",
        headers=headers,
        json={
            "source_risk_level": "low",
            "creators": [creator_snapshot],
            "persist_result": True,
        },
    )
    assert enrichment_response.status_code == 200
    assert enrichment_response.json()["persistence_status"] == "persisted"

    direct_screen_response = client.post(
        "/analysis-jobs/run-recent-posts-screen",
        headers=headers,
        json={
            "creator_id": creator_id,
            "source_risk_level": "low",
            "recent_posts": [
                {
                    "video_id": post["platform_video_id"],
                    "url": post["url"],
                    "caption": post["caption"],
                    "transcript": post["transcript"],
                    "hashtags": post["hashtags"],
                    "view_count": post["view_count"],
                    "like_count": post["like_count"],
                    "comment_count": post["comment_count"],
                    "share_count": post["share_count"],
                }
                for post in recent_posts
            ],
            "expected_post_count": 20,
            "creator_snapshot": creator_snapshot,
            "product_context": {"product_category": "sunscreen", "brand": "Briwell"},
            "dry_run": True,
            "persist_result": True,
        },
    )
    assert direct_screen_response.status_code == 200
    direct_screen_body = direct_screen_response.json()
    assert direct_screen_body["status"] == "success"
    assert direct_screen_body["screen_persistence_status"] == "persisted"
    assert direct_screen_body["result"]["output"]["suitability_decision"] == "pass_to_full_analysis"

    screen_result = {
        "post_count_analyzed": 20,
        "expected_post_count": 20,
        "suitability_decision": "pass_to_full_analysis",
        "suitability_score": 91,
        "matched_product_categories": ["sunscreen"],
        "coverage_gaps": [],
        "risk_notes": [],
        "next_step": "run_full_profile_comment_multimodal_analysis",
    }
    apply_response = client.post(
        "/operations/recent-posts/apply",
        headers=headers,
        json={
            "source_risk_level": "low",
            "items": [
                {
                    "creator_id": creator_id,
                    "creator_snapshot": creator_snapshot,
                    "screen_result": screen_result,
                }
            ],
            "persist_result": True,
        },
    )
    assert apply_response.status_code == 200
    apply_body = apply_response.json()
    assert apply_body["persistence_status"] == "persisted"
    assert apply_body["queue_counts"]["full_analysis_queue"] == 1
