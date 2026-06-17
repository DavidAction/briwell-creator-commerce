from typing import Any

from psycopg.types.json import Jsonb

from app.core.db import fetch_one


def create_dm_draft(
    creator_id: str,
    campaign_id: str | None,
    dm_variant: str,
    dm_message: str,
    channel: str = "tiktok",
) -> dict[str, Any]:
    query = """
        INSERT INTO outreach (
          creator_id,
          campaign_id,
          status,
          dm_variant,
          dm_message,
          claims_check_status,
          channel,
          do_not_contact_checked_at
        ) VALUES (
          %(creator_id)s,
          %(campaign_id)s,
          'dm_drafted',
          %(dm_variant)s,
          %(dm_message)s,
          'needs_review',
          %(channel)s,
          now()
        )
        RETURNING
          id,
          creator_id,
          campaign_id,
          status,
          dm_variant,
          dm_message,
          claims_check_status,
          channel,
          do_not_contact_checked_at,
          created_at
    """
    created = fetch_one(
        query,
        {
            "creator_id": creator_id,
            "campaign_id": campaign_id,
            "dm_variant": dm_variant,
            "dm_message": dm_message,
            "channel": channel,
        },
    )
    if created is None:
        raise RuntimeError("Outreach insert did not return a row.")
    return created


def get_outreach(outreach_id: str) -> dict[str, Any] | None:
    query = """
        SELECT
          id,
          creator_id,
          campaign_id,
          status,
          dm_variant,
          dm_message,
          claims_check_status,
          approved_by_user_id,
          channel,
          sent_at,
          response_summary,
          proposed_terms,
          do_not_contact_checked_at,
          created_at,
          updated_at
        FROM outreach
        WHERE id = %(outreach_id)s
        LIMIT 1
    """
    return fetch_one(query, {"outreach_id": outreach_id})


def update_claims_check_status(
    outreach_id: str,
    claims_check_status: str,
    operator_notes: str | None = None,
) -> dict[str, Any]:
    query = """
        UPDATE outreach
        SET
          claims_check_status = %(claims_check_status)s,
          operator_notes = %(operator_notes)s,
          updated_at = now()
        WHERE id = %(outreach_id)s
        RETURNING
          id,
          creator_id,
          campaign_id,
          status,
          dm_variant,
          dm_message,
          claims_check_status,
          channel,
          do_not_contact_checked_at,
          operator_notes,
          updated_at
    """
    updated = fetch_one(
        query,
        {
            "outreach_id": outreach_id,
            "claims_check_status": claims_check_status,
            "operator_notes": operator_notes,
        },
    )
    if updated is None:
        raise RuntimeError("Outreach claims check update did not return a row.")
    return updated


def update_review_decision(
    outreach_id: str,
    status: str,
    operator_notes: str | None = None,
    approved_by_user_id: str | None = None,
) -> dict[str, Any]:
    query = """
        UPDATE outreach
        SET
          status = %(status)s,
          operator_notes = %(operator_notes)s,
          approved_by_user_id = %(approved_by_user_id)s,
          updated_at = now()
        WHERE id = %(outreach_id)s
        RETURNING
          id,
          creator_id,
          campaign_id,
          status,
          dm_variant,
          dm_message,
          claims_check_status,
          approved_by_user_id,
          channel,
          do_not_contact_checked_at,
          operator_notes,
          updated_at
    """
    updated = fetch_one(
        query,
        {
            "outreach_id": outreach_id,
            "status": status,
            "operator_notes": operator_notes,
            "approved_by_user_id": approved_by_user_id,
        },
    )
    if updated is None:
        raise RuntimeError("Outreach review decision update did not return a row.")
    return updated


def update_status(
    outreach_id: str,
    status: str,
    response_summary: str | None = None,
    proposed_terms: dict[str, Any] | None = None,
    operator_notes: str | None = None,
) -> dict[str, Any]:
    query = """
        UPDATE outreach
        SET
          status = %(status)s,
          response_summary = COALESCE(%(response_summary)s, response_summary),
          proposed_terms = COALESCE(%(proposed_terms)s::jsonb, proposed_terms),
          sent_at = CASE
            WHEN %(status)s = 'dm_sent' AND sent_at IS NULL THEN now()
            ELSE sent_at
          END,
          last_contacted_at = CASE
            WHEN %(status)s = 'dm_sent' THEN now()
            ELSE last_contacted_at
          END,
          response_received_at = CASE
            WHEN %(status)s IN ('replied', 'negotiating') AND response_received_at IS NULL THEN now()
            ELSE response_received_at
          END,
          operator_notes = COALESCE(%(operator_notes)s, operator_notes),
          updated_at = now()
        WHERE id = %(outreach_id)s
        RETURNING
          id,
          creator_id,
          campaign_id,
          status,
          dm_variant,
          dm_message,
          claims_check_status,
          approved_by_user_id,
          channel,
          sent_at,
          last_contacted_at,
          response_received_at,
          response_summary,
          proposed_terms,
          operator_notes,
          updated_at
    """
    updated = fetch_one(
        query,
        {
            "outreach_id": outreach_id,
            "status": status,
            "response_summary": response_summary,
            "proposed_terms": Jsonb(proposed_terms) if proposed_terms is not None else None,
            "operator_notes": operator_notes,
        },
    )
    if updated is None:
        raise RuntimeError("Outreach status update did not return a row.")
    return updated
