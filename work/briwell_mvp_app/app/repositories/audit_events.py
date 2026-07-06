from typing import Any

import psycopg
from psycopg.types.json import Jsonb

MAX_LIST_LIMIT = 200


def record_event(
    conn: psycopg.Connection,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    actor_role: str | None,
    actor_email: str | None,
    payload: dict[str, Any],
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO audit_events (
              event_type, aggregate_type, aggregate_id, actor_role, actor_email, payload
            ) VALUES (
              %(event_type)s, %(aggregate_type)s, %(aggregate_id)s, %(actor_role)s, %(actor_email)s, %(payload)s
            )
            RETURNING id
            """,
            {
                "event_type": event_type,
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "actor_role": actor_role,
                "actor_email": actor_email,
                "payload": Jsonb(payload),
            },
        )
        row = cur.fetchone()
    conn.commit()
    if row is None:
        raise RuntimeError("Audit event insert did not return a row.")
    return row["id"]


def list_events(
    conn: psycopg.Connection,
    aggregate_type: str | None = None,
    aggregate_id: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    filters = ["1 = 1"]
    params: dict[str, Any] = {"limit": max(min(limit, MAX_LIST_LIMIT), 1)}
    if aggregate_type:
        filters.append("aggregate_type = %(aggregate_type)s")
        params["aggregate_type"] = aggregate_type
    if aggregate_id:
        filters.append("aggregate_id = %(aggregate_id)s")
        params["aggregate_id"] = aggregate_id
    if event_type:
        filters.append("event_type = %(event_type)s")
        params["event_type"] = event_type

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, event_type, aggregate_type, aggregate_id, actor_role,
                   actor_email, payload, occurred_at
            FROM audit_events
            WHERE {' AND '.join(filters)}
            ORDER BY occurred_at DESC
            LIMIT %(limit)s
            """,
            params,
        )
        return [dict(row) for row in cur.fetchall()]
