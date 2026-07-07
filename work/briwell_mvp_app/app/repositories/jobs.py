from typing import Any

import psycopg
from psycopg.types.json import Jsonb


def enqueue_job(conn: psycopg.Connection, job_type: str, payload: dict[str, Any]) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO jobs (job_type, payload)
            VALUES (%(job_type)s, %(payload)s)
            RETURNING id
            """,
            {"job_type": job_type, "payload": Jsonb(payload)},
        )
        row = cur.fetchone()
    conn.commit()
    if row is None:
        raise RuntimeError("Job insert did not return a row.")
    return row["id"]


def claim_next_job(
    conn: psycopg.Connection,
    job_types: list[str] | None = None,
) -> dict[str, Any] | None:
    filters = ["status = 'pending'"]
    params: dict[str, Any] = {}
    if job_types:
        filters.append("job_type = ANY(%(job_types)s)")
        params["job_types"] = job_types

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, job_type, payload, status, attempts, max_attempts,
                   last_error, created_at, started_at, finished_at
            FROM jobs
            WHERE {' AND '.join(filters)}
            ORDER BY created_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """,
            params,
        )
        row = cur.fetchone()
        if row is None:
            conn.commit()
            return None

        cur.execute(
            """
            UPDATE jobs
            SET status = 'processing', started_at = now()
            WHERE id = %(job_id)s
            RETURNING id, job_type, payload, status, attempts, max_attempts,
                      last_error, created_at, started_at, finished_at
            """,
            {"job_id": row["id"]},
        )
        claimed = cur.fetchone()
    conn.commit()
    return dict(claimed) if claimed is not None else None


def mark_job_done(conn: psycopg.Connection, job_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE jobs
            SET status = 'done', finished_at = now()
            WHERE id = %(job_id)s
            """,
            {"job_id": job_id},
        )
    conn.commit()


def mark_job_failed(conn: psycopg.Connection, job_id: int, error: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE jobs
            SET
              attempts = attempts + 1,
              last_error = %(error)s,
              status = CASE WHEN attempts + 1 < max_attempts THEN 'pending' ELSE 'failed' END,
              started_at = CASE WHEN attempts + 1 < max_attempts THEN NULL ELSE started_at END,
              finished_at = CASE WHEN attempts + 1 < max_attempts THEN NULL ELSE now() END
            WHERE id = %(job_id)s
            """,
            {"job_id": job_id, "error": error},
        )
    conn.commit()
