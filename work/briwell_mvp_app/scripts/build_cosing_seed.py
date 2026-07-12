"""Build data/cosing_ingredients.csv from the official CosIng inventory CSV.

Source (P3, critical review v0): the EU Commission CosIng "Ingredients and
Fragrance Inventory" — public open data. The redesigned CosIng site no longer
serves the bulk CSV anonymously, so the seed is generated from the last full
official CSV export, preserved by the Internet Archive:

    https://web.archive.org/web/20201230181855/
    https://ec.europa.eu/growth/tools-databases/cosing/pdf/
    COSING_Ingredients-Fragrance%20Inventory_v2.csv
    (file creation 30/12/2020, data "Last update: 15/12/2020",
     source sha256 701d42a7066a8d2aa9f4b1e259c123ab5c353a2ad5267cc96fa6cb76805ba31f)

Only INCI name + functions are kept (the matcher needs nothing else), which
turns ~6MB of source into a small repo file. INCI names are preserved
verbatim (CosIng publishes them uppercase); display casing is a UI concern,
matching is case-insensitive anyway.

Usage:
    python -m scripts.build_cosing_seed <raw_cosing.csv>
"""

from __future__ import annotations

import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "data" / "cosing_ingredients.csv"

SNAPSHOT_NOTE = (
    "CosIng Ingredients-Fragrance Inventory v2 (EU Commission open data); "
    "official CSV export dated 2020-12-30 (data last update 2020-12-15), "
    "retrieved via Internet Archive snapshot 20201230181855"
)


def rows_from_raw(raw_path: Path) -> list[tuple[str, str]]:
    """Extract (inci_name, functions) pairs from the official export.

    The export carries preamble lines before the real header, and cells with
    embedded newlines — csv.reader handles the latter; we skip until the
    header row that starts with 'COSING Ref No'."""

    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    with raw_path.open(encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        header: list[str] | None = None
        name_idx = functions_idx = -1
        for row in reader:
            if header is None:
                if row and row[0].strip() == "COSING Ref No":
                    header = row
                    name_idx = header.index("INCI name")
                    functions_idx = header.index("Function")
                continue
            if len(row) <= max(name_idx, functions_idx):
                continue
            name = " ".join(row[name_idx].split()).strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            functions = ";".join(
                part.strip().lower()
                for part in row[functions_idx].split(",")
                if part.strip()
            )
            rows.append((name, functions))
    if header is None:
        raise SystemExit("Header row 'COSING Ref No,...' not found — wrong input file?")
    return rows


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    raw_path = Path(sys.argv[1])
    rows = rows_from_raw(raw_path)
    rows.sort(key=lambda pair: pair[0].lower())

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        handle.write(f"# {SNAPSHOT_NOTE}\n")
        handle.write("# columns: inci_name,functions (functions ';'-separated, lowercase)\n")
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["inci_name", "functions"])
        writer.writerows(rows)
    print(f"wrote {len(rows)} ingredients -> {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
