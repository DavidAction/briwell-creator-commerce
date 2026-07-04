import asyncio
from collections.abc import Callable
import logging
from typing import Any

import psycopg

from app.repositories.jobs import claim_next_job, mark_job_done, mark_job_failed

logger = logging.getLogger("briwell")

JobHandler = Callable[[psycopg.Connection, dict[str, Any]], None]


def process_one(conn: psycopg.Connection, handlers: dict[str, JobHandler]) -> bool:
    job = claim_next_job(conn)
    if job is None:
        return False

    handler = handlers.get(job["job_type"])
    if handler is None:
        mark_job_failed(conn, job["id"], f"No handler registered for job_type={job['job_type']!r}")
        return True

    try:
        handler(conn, job["payload"])
    except Exception as exc:
        # A handler failure may have aborted the transaction (e.g. a constraint
        # violation); roll back before reusing conn or mark_job_failed's UPDATE
        # would itself raise InFailedSqlTransaction and escape uncaught.
        conn.rollback()
        mark_job_failed(conn, job["id"], str(exc))
        return True

    mark_job_done(conn, job["id"])
    return True


async def run_loop(
    handlers: dict[str, JobHandler],
    poll_interval_seconds: float,
    connection_factory: Callable[[], psycopg.Connection] | None = None,
) -> None:
    if connection_factory is None:
        from app.core.db import connection as connection_factory

    while True:
        with connection_factory() as conn:
            processed = process_one(conn, handlers)
        if not processed:
            await asyncio.sleep(poll_interval_seconds)
