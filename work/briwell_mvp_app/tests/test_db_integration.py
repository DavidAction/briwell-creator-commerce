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
