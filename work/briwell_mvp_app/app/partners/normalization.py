"""INCI ingredient normalization against the merged dictionary.

Two layers (P3):

* **Curated seed** (``ingredient_data.INGREDIENT_DICTIONARY``): hand-checked
  K-beauty staples with Korean aliases and slug functions. Always wins —
  its canonical spelling and aliases override everything.
* **CosIng inventory** (``cosing_data``): ~28,700 INCI names from the EU
  Commission open-data export, loaded lazily on first use. Fallback layer
  for everything the curated seed does not cover.

Match order: curated canonical -> curated alias -> CosIng canonical ->
conservative fuzzy (bucketed for speed). Anything below the fuzzy cutoff
stays ``unmatched`` — guessing an ingredient identity would poison
regulatory screening downstream, so honesty beats recall here.
"""

from difflib import SequenceMatcher
from typing import Any

from app.partners.cosing_data import COSING_VERSION, cosing_entries
from app.partners.ingredient_data import INGREDIENT_DICTIONARY

FUZZY_CUTOFF = 0.90

_CURATED_BY_KEY: dict[str, str] = {}
_ALIAS_BY_KEY: dict[str, str] = {}


def _key(name: str) -> str:
    return "".join(ch for ch in name.lower().strip() if ch.isalnum())


for _canonical, _entry in INGREDIENT_DICTIONARY.items():
    _CURATED_BY_KEY[_key(_canonical)] = _canonical
    for _alias in _entry["aliases"]:
        _ALIAS_BY_KEY.setdefault(_key(_alias), _canonical)


# CosIng layer, built lazily on first normalization (loading 28k rows at
# import time would tax every process that never touches the pipeline).
_COSING_BY_KEY: dict[str, str] | None = None
_FUZZY_BUCKETS: dict[str, list[tuple[str, str]]] | None = None


def _cosing_by_key() -> dict[str, str]:
    global _COSING_BY_KEY
    if _COSING_BY_KEY is None:
        mapping: dict[str, str] = {}
        for name in cosing_entries():
            key = _key(name)
            # Curated entries own their key outright (canonical spelling,
            # aliases, functions) — the CosIng layer never shadows them,
            # not even in the fuzzy buckets built from this map.
            if key and key not in _CURATED_BY_KEY:
                mapping.setdefault(key, name)
        _COSING_BY_KEY = mapping
    return _COSING_BY_KEY


def _fuzzy_buckets() -> dict[str, list[tuple[str, str]]]:
    """Candidate keys bucketed by first character so a fuzzy pass compares
    against hundreds of neighbours instead of the whole 28k inventory."""

    global _FUZZY_BUCKETS
    if _FUZZY_BUCKETS is None:
        buckets: dict[str, list[tuple[str, str]]] = {}
        for key, canonical in _cosing_by_key().items():
            buckets.setdefault(key[0], []).append((key, canonical))
        for key, canonical in _CURATED_BY_KEY.items():
            buckets.setdefault(key[0], []).append((key, canonical))
        _FUZZY_BUCKETS = buckets
    return _FUZZY_BUCKETS


def _functions_for(canonical: str) -> list[str]:
    curated = INGREDIENT_DICTIONARY.get(canonical)
    if curated is not None:
        return list(curated["functions"])
    return list(cosing_entries().get(canonical, ()))


def dictionary_meta() -> dict[str, Any]:
    return {
        "curated": len(INGREDIENT_DICTIONARY),
        "cosing": len(cosing_entries()),
        "cosing_version": COSING_VERSION,
    }


def normalize_ingredient(raw_name: str) -> dict[str, Any]:
    """Resolve one raw ingredient string to a canonical INCI entry."""

    cleaned = " ".join(raw_name.split()).strip(" .,;·")
    key = _key(cleaned)
    if not key:
        return _unmatched(raw_name)

    if key in _CURATED_BY_KEY:
        return _matched(raw_name, _CURATED_BY_KEY[key], "exact")
    if key in _ALIAS_BY_KEY:
        return _matched(raw_name, _ALIAS_BY_KEY[key], "alias")
    cosing = _cosing_by_key()
    if key in cosing:
        return _matched(raw_name, cosing[key], "exact")

    best_name, best_ratio = None, 0.0
    for candidate_key, canonical in _fuzzy_buckets().get(key[0], ()):
        if abs(len(candidate_key) - len(key)) > 3:
            continue
        ratio = SequenceMatcher(None, key, candidate_key).ratio()
        if ratio > best_ratio:
            best_name, best_ratio = canonical, ratio
    if best_name is not None and best_ratio >= FUZZY_CUTOFF:
        result = _matched(raw_name, best_name, "fuzzy")
        result["fuzzy_ratio"] = round(best_ratio, 3)
        return result

    return _unmatched(raw_name)


def normalize_ingredient_list(raw_names: list[str]) -> dict[str, Any]:
    """Normalize a full INCI list, preserving declaration order."""

    # Position reflects INCI declaration order among actual ingredients,
    # so blank rows in a pasted list do not shift the numbering.
    items = [
        dict(normalize_ingredient(name), position=index + 1)
        for index, name in enumerate(
            name for name in raw_names if str(name).strip()
        )
    ]
    matched = [item for item in items if item["match_status"] != "unmatched"]
    return {
        "items": items,
        "total": len(items),
        "matched": len(matched),
        "unmatched": len(items) - len(matched),
        "dictionary": dictionary_meta(),
    }


def _matched(raw_name: str, canonical: str, status: str) -> dict[str, Any]:
    return {
        "raw": raw_name,
        "inci_name": canonical,
        "match_status": status,
        "functions": _functions_for(canonical),
    }


def _unmatched(raw_name: str) -> dict[str, Any]:
    return {
        "raw": raw_name,
        "inci_name": None,
        "match_status": "unmatched",
        "functions": [],
    }
