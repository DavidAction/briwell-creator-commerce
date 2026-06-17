from collections.abc import Iterable
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings


class DatabaseNotEnabled(RuntimeError):
    """Raised when a repository is called without USE_DATABASE enabled."""


def database_enabled() -> bool:
    return settings.use_database


@contextmanager
def connection():
    if not settings.use_database:
        raise DatabaseNotEnabled("Set USE_DATABASE=true to enable PostgreSQL persistence.")
    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        yield conn


def fetch_all(query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or {})
            return list(cur.fetchall())


def fetch_one(query: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or {})
            row = cur.fetchone()
            return dict(row) if row is not None else None


def execute_many(
    query: str,
    rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with connection() as conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(query, row)
                if cur.description:
                    fetched = cur.fetchone()
                    if fetched is not None:
                        results.append(dict(fetched))
        conn.commit()
    return results
