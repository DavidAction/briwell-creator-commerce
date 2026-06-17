from __future__ import annotations

from pathlib import Path
import sys

from dotenv import load_dotenv
import psycopg


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    load_dotenv()
    from app.core.config import settings

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user")
            database, user = cur.fetchone()
    print(f"Connected to database={database} user={user}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
