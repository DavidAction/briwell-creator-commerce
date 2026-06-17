from typing import Any

from psycopg.types.json import Jsonb

from app.core.db import fetch_one


def create_contract(payload: dict[str, Any]) -> dict[str, Any]:
    query = """
        INSERT INTO creator_contract (
          outreach_id,
          creator_id,
          campaign_id,
          deliverables,
          compensation_terms,
          due_date,
          status,
          contract_url,
          operator_notes
        ) VALUES (
          %(outreach_id)s,
          %(creator_id)s,
          %(campaign_id)s,
          %(deliverables)s,
          %(compensation_terms)s,
          %(due_date)s,
          %(status)s,
          %(contract_url)s,
          %(operator_notes)s
        )
        RETURNING *
    """
    created = fetch_one(
        query,
        {
            **payload,
            "deliverables": Jsonb(payload.get("deliverables", {})),
            "compensation_terms": Jsonb(payload.get("compensation_terms", {})),
        },
    )
    if created is None:
        raise RuntimeError("Creator contract insert did not return a row.")
    return created


def create_payout(payload: dict[str, Any]) -> dict[str, Any]:
    query = """
        INSERT INTO creator_payout (
          contract_id,
          creator_id,
          campaign_id,
          amount_usd,
          payout_status,
          payout_method,
          invoice_url,
          tax_document_url,
          blocker_reason
        ) VALUES (
          %(contract_id)s,
          %(creator_id)s,
          %(campaign_id)s,
          %(amount_usd)s,
          %(payout_status)s,
          %(payout_method)s,
          %(invoice_url)s,
          %(tax_document_url)s,
          %(blocker_reason)s
        )
        RETURNING *
    """
    created = fetch_one(query, payload)
    if created is None:
        raise RuntimeError("Creator payout insert did not return a row.")
    return created
