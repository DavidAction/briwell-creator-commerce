from __future__ import annotations

import argparse
from pathlib import Path
import sys

from dotenv import load_dotenv
import psycopg


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def sql_files(include_seeds: bool) -> list[Path]:
    files = sorted((ROOT / "db" / "migrations").glob("*.sql"))
    if include_seeds:
        files.extend(sorted((ROOT / "db" / "seeds").glob("*.sql")))
    return files


def apply_file(conn: psycopg.Connection, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)


def main() -> int:
    load_dotenv()
    from app.core.config import settings

    parser = argparse.ArgumentParser(description="Apply Briwell SQL migrations.")
    parser.add_argument("--with-seeds", action="store_true", help="Also apply SQL seed files.")
    args = parser.parse_args()

    files = sql_files(include_seeds=args.with_seeds)
    if not files:
        print("No SQL files found.")
        return 0

    with psycopg.connect(settings.database_url) as conn:
        for path in files:
            print(f"Applying {path.relative_to(ROOT)}")
            apply_file(conn, path)
        conn.commit()

    print("SQL apply complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
