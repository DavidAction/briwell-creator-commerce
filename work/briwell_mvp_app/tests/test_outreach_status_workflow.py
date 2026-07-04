import os
import time
from types import SimpleNamespace

import pytest

from app.workflows.outreach_status import OutreachTransitionInput
from app.workflows.outreach_status import evaluate_outreach_transition


db_tests_only = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1",
    reason="Set RUN_DB_TESTS=1 with a live PostgreSQL DATABASE_URL to run DB integration tests.",
)


def test_outreach_transition_allows_manual_send_after_approval() -> None:
    result = evaluate_outreach_transition(
        OutreachTransitionInput(
            current_status="approved",
            next_status="dm_sent",
            claims_check_status="passed",
            do_not_contact_checked=True,
            manual_send_confirmed=True,
        )
    )

    assert result.allowed is True
    assert result.external_send_automated is False
    assert result.audit_required is True


def test_outreach_transition_blocks_dm_sent_without_manual_confirmation() -> None:
    result = evaluate_outreach_transition(
        OutreachTransitionInput(
            current_status="approved",
            next_status="dm_sent",
            claims_check_status="passed",
            do_not_contact_checked=True,
            manual_send_confirmed=False,
        )
    )

    assert result.allowed is False
    assert "MANUAL_SEND_CONFIRMATION_REQUIRED" in result.reasons


def test_outreach_transition_blocks_dm_sent_without_claims_check() -> None:
    result = evaluate_outreach_transition(
        OutreachTransitionInput(
            current_status="approved",
            next_status="dm_sent",
            claims_check_status="needs_review",
            do_not_contact_checked=True,
            manual_send_confirmed=True,
        )
    )

    assert result.allowed is False
    assert "CLAIMS_CHECK_REQUIRED_BEFORE_DM_SENT" in result.reasons


def test_outreach_transition_requires_response_summary_for_reply() -> None:
    result = evaluate_outreach_transition(
        OutreachTransitionInput(
            current_status="dm_sent",
            next_status="replied",
            claims_check_status="passed",
        )
    )

    assert result.allowed is False
    assert "RESPONSE_SUMMARY_REQUIRED" in result.reasons


def test_outreach_transition_requires_terms_for_acceptance() -> None:
    result = evaluate_outreach_transition(
        OutreachTransitionInput(
            current_status="negotiating",
            next_status="accepted",
            claims_check_status="passed",
            response_summary="Creator agreed in principle.",
        )
    )

    assert result.allowed is False
    assert "PROPOSED_TERMS_REQUIRED" in result.reasons


@db_tests_only
def test_dm_sent_transition_enqueues_one_audit_event_persist_job(monkeypatch: pytest.MonkeyPatch) -> None:
    import psycopg
    from psycopg.rows import dict_row
    from fastapi.testclient import TestClient

    from app.core import db as db_module
    from app.main import app
    from app.repositories import creators, outreach

    monkeypatch.setattr(
        db_module,
        "settings",
        SimpleNamespace(use_database=True, database_url=os.environ["DATABASE_URL"]),
    )

    suffix = str(int(time.time() * 1000))
    imported = creators.import_creators(
        source_type="manual",
        source_risk_level="low",
        items=[
            {
                "country": "MX",
                "username": f"audit_job_creator_{suffix}",
                "profile_url": f"https://example.com/@audit_job_creator_{suffix}",
                "display_name": "Audit Job Creator",
                "bio": "skincare and kbeauty reviews",
                "language": "es",
                "follower_count": 500_000,
                "source_url": "https://example.com/manual-import",
            }
        ],
    )
    creator_id = imported[0]["id"]

    draft = outreach.create_dm_draft(
        creator_id=str(creator_id),
        campaign_id=None,
        dm_variant="soft_intro",
        dm_message="Hola, queremos compartir detalles de una colaboracion K-beauty.",
    )
    outreach.update_claims_check_status(
        outreach_id=str(draft["id"]),
        claims_check_status="passed",
    )
    outreach.update_review_decision(
        outreach_id=str(draft["id"]),
        status="approved",
    )

    client = TestClient(app)
    response = client.post(
        "/outreach/status-transition",
        headers={"X-User-Role": "operator", "X-User-Email": "operator@briwell.test"},
        json={
            "outreach_id": str(draft["id"]),
            "next_status": "dm_sent",
            "manual_send_confirmed": True,
            "operator_notes": "Sent manually in TikTok app.",
        },
    )

    assert response.status_code == 200
    assert response.json()["persistence_status"] == "persisted"

    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT payload FROM jobs
                WHERE job_type = 'audit_event.persist'
                  AND payload->>'aggregate_id' = %(aggregate_id)s
                """,
                {"aggregate_id": str(draft["id"])},
            )
            rows = cur.fetchall()

    assert len(rows) == 1
    job_payload = rows[0]["payload"]
    assert job_payload["event_type"] == "outreach.status_changed"
    assert job_payload["aggregate_type"] == "outreach"
    assert job_payload["aggregate_id"] == str(draft["id"])
    assert job_payload["actor_role"] == "operator"
    assert job_payload["actor_email"] == "operator@briwell.test"
    assert job_payload["payload"]["old_status"] == "approved"
    assert job_payload["payload"]["new_status"] == "dm_sent"
