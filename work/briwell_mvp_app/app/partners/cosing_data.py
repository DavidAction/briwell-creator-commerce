"""Lazy loader for the CosIng ingredient inventory seed (P3).

``data/cosing_ingredients.csv`` is generated from the official EU Commission
CosIng "Ingredients and Fragrance Inventory" open-data CSV by
``scripts/build_cosing_seed.py`` (source, snapshot date and sha256 are
recorded in that script and in the file header). ~28,700 INCI names with
their published functions.

The loader is lazy (first normalization call) and fail-soft: if the seed
file is missing the curated dictionary still works alone — a smaller
dictionary is honest degradation, a crash is not.
"""

import csv
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COSING_CSV_PATH = ROOT / "data" / "cosing_ingredients.csv"

# Data vintage, surfaced in normalization metadata so an operator can see
# which inventory snapshot matched an ingredient list.
COSING_VERSION = "cosing-inventory-v2-2020-12-15"


@lru_cache(maxsize=1)
def cosing_entries() -> dict[str, tuple[str, ...]]:
    """INCI name (verbatim, as published) -> functions tuple."""

    if not COSING_CSV_PATH.is_file():
        return {}
    entries: dict[str, tuple[str, ...]] = {}
    with COSING_CSV_PATH.open(encoding="utf-8", newline="") as handle:
        data_lines = (line for line in handle if not line.startswith("#"))
        reader = csv.reader(data_lines)
        next(reader, None)  # header row
        for row in reader:
            if len(row) < 2:
                continue
            name = row[0].strip()
            if name:
                entries[name] = tuple(part for part in row[1].split(";") if part)
    return entries
