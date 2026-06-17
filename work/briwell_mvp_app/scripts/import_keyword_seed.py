from __future__ import annotations

import csv
from pathlib import Path
import sys

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_csv_imports import validate_keyword_seed


CSV_PATH = ROOT / "db" / "seeds" / "keyword_seed_v0.csv"


UPSERT_SQL = """
INSERT INTO keyword_seed (
  country,
  language,
  product_category,
  intent_type,
  keyword,
  hashtag,
  priority,
  notes,
  status
) VALUES (
  %(country)s,
  %(language)s,
  %(product_category)s,
  %(intent_type)s,
  %(keyword)s,
  %(hashtag)s,
  %(priority)s,
  %(notes)s,
  'active'
)
ON CONFLICT DO NOTHING
"""


def rows_from_csv(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, object]] = []
        for row in reader:
            rows.append(
                {
                    "country": row["country"],
                    "language": row["language"],
                    "product_category": row["product_category"],
                    "intent_type": row["intent_type"],
                    "keyword": row["keyword"] or None,
                    "hashtag": row["hashtag"] or None,
                    "priority": int(row["priority"]),
                    "notes": row["notes"] or None,
                }
            )
    return rows


def main() -> int:
    load_dotenv()
    from app.core.config import settings

    errors = validate_keyword_seed(CSV_PATH)
    if errors:
        for error in errors:
            print(error)
        return 1

    rows = rows_from_csv(CSV_PATH)
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.executemany(UPSERT_SQL, rows)
        conn.commit()

    print(f"Imported keyword seeds: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
