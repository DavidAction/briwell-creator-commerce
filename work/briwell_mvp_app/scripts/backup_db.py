from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.db_tools import database_name_from_url
from scripts.db_tools import redact_database_url
from scripts.db_tools import resolve_pg_tool


DEFAULT_BACKUP_DIR = ROOT.parent / "db_backups"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_backup_path(output_dir: Path, database_name: str, created_at: datetime) -> Path:
    timestamp = created_at.strftime("%Y%m%d_%H%M%S")
    return output_dir / f"{database_name}_{timestamp}.dump"


def run_backup(
    database_url: str,
    output_dir: Path = DEFAULT_BACKUP_DIR,
    pg_bin_dir: str | None = None,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    database_name = database_name_from_url(database_url)
    backup_path = build_backup_path(output_dir, database_name, datetime.now())
    pg_dump = resolve_pg_tool("pg_dump", pg_bin_dir=pg_bin_dir)

    command = [
        pg_dump,
        "--format=custom",
        "--no-owner",
        "--no-acl",
        "--file",
        str(backup_path),
        database_url,
    ]
    subprocess.run(command, check=True)

    manifest = {
        "status": "backup_created",
        "database": database_name,
        "database_url": redact_database_url(database_url),
        "backup_file": str(backup_path),
        "size_bytes": backup_path.stat().st_size,
        "sha256": sha256_file(backup_path),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "format": "pg_dump_custom",
    }
    manifest_path = backup_path.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["manifest_file"] = str(manifest_path)
    return manifest


def main() -> int:
    load_dotenv()
    from app.core.config import settings

    parser = argparse.ArgumentParser(description="Create a Briwell PostgreSQL backup.")
    parser.add_argument("--output-dir", default=str(DEFAULT_BACKUP_DIR))
    parser.add_argument("--pg-bin-dir", default=os.getenv("PG_BIN_DIR"))
    args = parser.parse_args()

    result = run_backup(
        database_url=settings.database_url,
        output_dir=Path(args.output_dir),
        pg_bin_dir=args.pg_bin_dir,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
