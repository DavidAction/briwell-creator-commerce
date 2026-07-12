from typing import Any

import psycopg

from app.partners.ingestion import handle_partner_asset_ingest
from app.repositories import audit_events as audit_events_repository


def handle_audit_event_persist(conn: psycopg.Connection, payload: dict[str, Any]) -> None:
    audit_events_repository.record_event(conn, **payload)


JOB_HANDLERS = {
    "audit_event.persist": handle_audit_event_persist,
    "partner_asset_ingest": handle_partner_asset_ingest,
}
