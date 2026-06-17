from typing import Any

from psycopg.types.json import Jsonb

from app.core.db import fetch_one


def create_import_quality_log(
    payload: dict[str, Any],
    quality_gate: dict[str, Any],
    user_email: str | None = None,
) -> dict[str, Any]:
    query = """
        INSERT INTO import_quality_log (
          upload_name,
          dataset_type,
          source_type,
          source_risk_level,
          creator_count,
          post_count,
          quality_status,
          blocker_count,
          warning_count,
          quality_gate,
          raw_payload,
          created_by_email
        ) VALUES (
          %(upload_name)s,
          %(dataset_type)s,
          %(source_type)s,
          %(source_risk_level)s,
          %(creator_count)s,
          %(post_count)s,
          %(quality_status)s,
          %(blocker_count)s,
          %(warning_count)s,
          %(quality_gate)s,
          %(raw_payload)s,
          %(created_by_email)s
        )
        RETURNING *
    """
    created = fetch_one(
        query,
        {
            "upload_name": payload.get("upload_name"),
            "dataset_type": payload["dataset_type"],
            "source_type": payload["source_type"],
            "source_risk_level": payload["source_risk_level"],
            "creator_count": quality_gate["creator"]["total"],
            "post_count": quality_gate["posts"]["loaded"],
            "quality_status": quality_gate["overall_status"],
            "blocker_count": quality_gate["blocker_count"],
            "warning_count": quality_gate["warning_count"],
            "quality_gate": Jsonb(quality_gate),
            "raw_payload": Jsonb(payload),
            "created_by_email": user_email,
        },
    )
    if created is None:
        raise RuntimeError("Import quality log insert did not return a row.")
    return created


def upsert_creator_profile_enrichment(
    enrichment: dict[str, Any],
    source_risk_level: str,
) -> dict[str, Any]:
    query = """
        INSERT INTO creator_profile_enrichment (
          creator_id,
          username,
          source_risk_level,
          primary_country,
          country_confidence,
          language,
          platforms,
          contact_channels,
          normalized_categories,
          commerce_readiness,
          duplicate_key,
          missing_data,
          enrichment_status,
          next_action,
          enrichment_payload
        ) VALUES (
          %(creator_id)s,
          %(username)s,
          %(source_risk_level)s,
          %(primary_country)s,
          %(country_confidence)s,
          %(language)s,
          %(platforms)s,
          %(contact_channels)s,
          %(normalized_categories)s,
          %(commerce_readiness)s,
          %(duplicate_key)s,
          %(missing_data)s,
          %(enrichment_status)s,
          %(next_action)s,
          %(enrichment_payload)s
        )
        ON CONFLICT (creator_id)
        DO UPDATE SET
          username = EXCLUDED.username,
          source_risk_level = EXCLUDED.source_risk_level,
          primary_country = EXCLUDED.primary_country,
          country_confidence = EXCLUDED.country_confidence,
          language = EXCLUDED.language,
          platforms = EXCLUDED.platforms,
          contact_channels = EXCLUDED.contact_channels,
          normalized_categories = EXCLUDED.normalized_categories,
          commerce_readiness = EXCLUDED.commerce_readiness,
          duplicate_key = EXCLUDED.duplicate_key,
          missing_data = EXCLUDED.missing_data,
          enrichment_status = EXCLUDED.enrichment_status,
          next_action = EXCLUDED.next_action,
          enrichment_payload = EXCLUDED.enrichment_payload,
          updated_at = now()
        RETURNING *
    """
    created = fetch_one(
        query,
        {
            "creator_id": enrichment.get("creator_id"),
            "username": enrichment.get("username"),
            "source_risk_level": source_risk_level,
            "primary_country": enrichment.get("primary_country"),
            "country_confidence": enrichment.get("country_confidence"),
            "language": enrichment.get("language"),
            "platforms": enrichment.get("platforms", []),
            "contact_channels": enrichment.get("contact_channels", []),
            "normalized_categories": enrichment.get("normalized_categories", []),
            "commerce_readiness": enrichment.get("commerce_readiness"),
            "duplicate_key": enrichment.get("duplicate_key"),
            "missing_data": enrichment.get("missing_data", []),
            "enrichment_status": enrichment.get("enrichment_status"),
            "next_action": enrichment.get("next_action"),
            "enrichment_payload": Jsonb(enrichment),
        },
    )
    if created is None:
        raise RuntimeError("Creator enrichment upsert did not return a row.")
    return created


def create_recent_posts_screen_result(
    item: dict[str, Any],
    source_risk_level: str,
) -> dict[str, Any]:
    result = item.get("screen_result", {})
    query = """
        INSERT INTO recent_posts_screen_result (
          creator_id,
          source_risk_level,
          post_count_analyzed,
          suitability_decision,
          suitability_score,
          matched_product_categories,
          coverage_gaps,
          risk_notes,
          next_step,
          result_payload
        ) VALUES (
          %(creator_id)s,
          %(source_risk_level)s,
          %(post_count_analyzed)s,
          %(suitability_decision)s,
          %(suitability_score)s,
          %(matched_product_categories)s,
          %(coverage_gaps)s,
          %(risk_notes)s,
          %(next_step)s,
          %(result_payload)s
        )
        RETURNING *
    """
    created = fetch_one(
        query,
        {
            "creator_id": item.get("creator_id"),
            "source_risk_level": source_risk_level,
            "post_count_analyzed": result.get("post_count_analyzed", 0),
            "suitability_decision": result.get("suitability_decision"),
            "suitability_score": result.get("suitability_score"),
            "matched_product_categories": result.get("matched_product_categories", []),
            "coverage_gaps": result.get("coverage_gaps", []),
            "risk_notes": result.get("risk_notes", []),
            "next_step": result.get("next_step"),
            "result_payload": Jsonb(result),
        },
    )
    if created is None:
        raise RuntimeError("Recent posts screen result insert did not return a row.")
    return created


def create_outreach_crm_event(
    event: dict[str, Any],
) -> dict[str, Any]:
    query = """
        INSERT INTO outreach_crm_event (
          outreach_id,
          creator_id,
          campaign_id,
          from_status,
          to_status,
          event_type,
          event_payload,
          operator_notes
        ) VALUES (
          %(outreach_id)s,
          %(creator_id)s,
          %(campaign_id)s,
          %(from_status)s,
          %(to_status)s,
          %(event_type)s,
          %(event_payload)s,
          %(operator_notes)s
        )
        RETURNING *
    """
    created = fetch_one(
        query,
        {
            "outreach_id": event.get("outreach_id"),
            "creator_id": event.get("creator_id"),
            "campaign_id": event.get("campaign_id"),
            "from_status": event.get("from_status"),
            "to_status": event.get("to_status") or event.get("status") or event.get("crm_status"),
            "event_type": event.get("event_type", "crm_board_snapshot"),
            "event_payload": Jsonb(event),
            "operator_notes": event.get("operator_notes"),
        },
    )
    if created is None:
        raise RuntimeError("Outreach CRM event insert did not return a row.")
    return created
