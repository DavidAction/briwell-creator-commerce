from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
from typing import Iterable

from dotenv import load_dotenv
import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.db_contract import MINIMUM_SEED_COUNTS
from app.core.db_contract import REQUIRED_ENUMS
from app.core.db_contract import REQUIRED_TABLES
from scripts.import_keyword_seed import UPSERT_SQL
from scripts.import_keyword_seed import rows_from_csv
from scripts.import_keyword_seed import CSV_PATH
from scripts.validate_csv_imports import validate_keyword_seed


def sql_files(include_seeds: bool) -> list[Path]:
    files = sorted((ROOT / "db" / "migrations").glob("*.sql"))
    if include_seeds:
        files.extend(sorted((ROOT / "db" / "seeds").glob("*.sql")))
    return files


def file_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ensure_migration_table(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migration (
              file_name TEXT PRIMARY KEY,
              checksum TEXT NOT NULL,
              applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    conn.commit()


def applied_files(conn: psycopg.Connection) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute("SELECT file_name, checksum FROM schema_migration")
        return {row[0]: row[1] for row in cur.fetchall()}


def apply_sql_file(conn: psycopg.Connection, path: Path) -> str:
    relative = path.relative_to(ROOT).as_posix()
    checksum = file_checksum(path)
    already_applied = applied_files(conn)
    if relative in already_applied:
        if already_applied[relative] != checksum:
            raise RuntimeError(f"SQL file changed after apply: {relative}")
        return "skipped"

    with conn.cursor() as cur:
        cur.execute(path.read_text(encoding="utf-8"))
        cur.execute(
            """
            INSERT INTO schema_migration (file_name, checksum)
            VALUES (%s, %s)
            """,
            (relative, checksum),
        )
    conn.commit()
    return "applied"


def import_keywords(conn: psycopg.Connection) -> int:
    errors = validate_keyword_seed(CSV_PATH)
    if errors:
        raise RuntimeError("Keyword seed validation failed: " + "; ".join(errors))

    rows = rows_from_csv(CSV_PATH)
    with conn.cursor() as cur:
        cur.executemany(UPSERT_SQL, rows)
    conn.commit()
    return len(rows)


def fetch_names(conn: psycopg.Connection, query: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(query)
        return {row[0] for row in cur.fetchall()}


def verify_required_tables(conn: psycopg.Connection) -> None:
    found = fetch_names(
        conn,
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        """,
    )
    missing = sorted(REQUIRED_TABLES - found)
    if missing:
        raise RuntimeError(f"Missing required tables: {', '.join(missing)}")


def verify_required_enums(conn: psycopg.Connection) -> None:
    found = fetch_names(
        conn,
        """
        SELECT typname
        FROM pg_type
        WHERE typnamespace = 'public'::regnamespace
        """,
    )
    missing = sorted(REQUIRED_ENUMS - found)
    if missing:
        raise RuntimeError(f"Missing required enums: {', '.join(missing)}")


def table_count(conn: psycopg.Connection, table_name: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name))
        )
        return int(cur.fetchone()[0])


def verify_seed_counts(conn: psycopg.Connection) -> None:
    failures: list[str] = []
    for table_name, minimum in MINIMUM_SEED_COUNTS.items():
        count = table_count(conn, table_name)
        if count < minimum:
            failures.append(f"{table_name}: expected >= {minimum}, found {count}")
    if failures:
        raise RuntimeError("Seed verification failed: " + "; ".join(failures))


def verify_database(conn: psycopg.Connection) -> None:
    verify_required_tables(conn)
    verify_required_enums(conn)
    verify_seed_counts(conn)


def apply_files(conn: psycopg.Connection, files: Iterable[Path]) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    for path in files:
        status = apply_sql_file(conn, path)
        results.append((path.relative_to(ROOT).as_posix(), status))
    return results


def main() -> int:
    load_dotenv()
    from app.core.config import settings

    parser = argparse.ArgumentParser(description="Bootstrap and verify Briwell PostgreSQL.")
    parser.add_argument("--with-seeds", action="store_true", help="Apply SQL seed files.")
    parser.add_argument("--with-keywords", action="store_true", help="Import keyword CSV seed.")
    parser.add_argument("--verify", action="store_true", help="Verify required tables, enums, and seeds.")
    args = parser.parse_args()

    with psycopg.connect(settings.database_url) as conn:
        ensure_migration_table(conn)
        for file_name, status in apply_files(conn, sql_files(include_seeds=args.with_seeds)):
            print(f"{status}: {file_name}")

        if args.with_keywords:
            imported = import_keywords(conn)
            print(f"imported keyword rows: {imported}")

        if args.verify:
            verify_database(conn)
            print("database verification passed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
