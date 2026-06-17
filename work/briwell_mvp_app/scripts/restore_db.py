from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from dotenv import load_dotenv
import psycopg


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.bootstrap_db import verify_database
from scripts.db_tools import database_url_for_name
from scripts.db_tools import maintenance_database_url
from scripts.db_tools import redact_database_url
from scripts.db_tools import resolve_pg_tool


def recreate_database(maintenance_url: str, target_database: str, drop_existing: bool) -> None:
    with psycopg.connect(maintenance_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_database,))
            exists = cur.fetchone() is not None
            if exists and not drop_existing:
                raise RuntimeError(
                    f"Target database already exists: {target_database}. "
                    "Pass --drop-existing to replace it."
                )
            if exists:
                cur.execute(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = %s AND pid <> pg_backend_pid()
                    """,
                    (target_database,),
                )
                cur.execute(f'DROP DATABASE "{target_database}"')
            cur.execute(f'CREATE DATABASE "{target_database}"')


def run_restore(
    database_url: str,
    backup_file: Path,
    target_database: str,
    drop_existing: bool = False,
    verify: bool = True,
    pg_bin_dir: str | None = None,
) -> dict[str, object]:
    if not backup_file.exists():
        raise FileNotFoundError(f"Backup file does not exist: {backup_file}")

    maintenance_url = maintenance_database_url(database_url)
    target_url = database_url_for_name(database_url, target_database)
    recreate_database(maintenance_url, target_database, drop_existing=drop_existing)

    pg_restore = resolve_pg_tool("pg_restore", pg_bin_dir=pg_bin_dir)
    command = [
        pg_restore,
        "--no-owner",
        "--no-acl",
        "--dbname",
        target_url,
        str(backup_file),
    ]
    subprocess.run(command, check=True)

    verification_status = "not_requested"
    if verify:
        with psycopg.connect(target_url) as conn:
            verify_database(conn)
        verification_status = "passed"

    return {
        "status": "restore_completed",
        "target_database": target_database,
        "target_database_url": redact_database_url(target_url),
        "backup_file": str(backup_file),
        "verification_status": verification_status,
    }


def main() -> int:
    load_dotenv()
    from app.core.config import settings

    parser = argparse.ArgumentParser(description="Restore a Briwell PostgreSQL backup.")
    parser.add_argument("--backup-file", required=True)
    parser.add_argument("--target-db", required=True)
    parser.add_argument("--drop-existing", action="store_true")
    parser.add_argument("--no-verify", action="store_true")
    parser.add_argument("--pg-bin-dir", default=os.getenv("PG_BIN_DIR"))
    args = parser.parse_args()

    result = run_restore(
        database_url=settings.database_url,
        backup_file=Path(args.backup_file),
        target_database=args.target_db,
        drop_existing=args.drop_existing,
        verify=not args.no_verify,
        pg_bin_dir=args.pg_bin_dir,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
