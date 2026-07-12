"""INCI ingredient normalization against the code-seeded dictionary.

Match order: exact canonical -> alias -> conservative fuzzy. Anything below
the fuzzy cutoff stays ``unmatched`` — guessing an ingredient identity would
poison regulatory screening downstream, so honesty beats recall here.
"""

from difflib import SequenceMatcher
from typing import Any

from app.partners.ingredient_data import INGREDIENT_DICTIONARY

FUZZY_CUTOFF = 0.90

_CANONICAL_BY_KEY: dict[str, str] = {}
_ALIAS_BY_KEY: dict[str, str] = {}


def _key(name: str) -> str:
    return "".join(ch for ch in name.lower().strip() if ch.isalnum())


for _canonical, _entry in INGREDIENT_DICTIONARY.items():
    _CANONICAL_BY_KEY[_key(_canonical)] = _canonical
    for _alias in _entry["aliases"]:
        _ALIAS_BY_KEY.setdefault(_key(_alias), _canonical)


def normalize_ingredient(raw_name: str) -> dict[str, Any]:
    """Resolve one raw ingredient string to a canonical INCI entry."""

    cleaned = " ".join(raw_name.split()).strip(" .,;·")
    key = _key(cleaned)
    if not key:
        return {
            "raw": raw_name,
            "inci_name": None,
            "match_status": "unmatched",
            "functions": [],
        }

    if key in _CANONICAL_BY_KEY:
        canonical = _CANONICAL_BY_KEY[key]
        return _matched(raw_name, canonical, "exact")
    if key in _ALIAS_BY_KEY:
        canonical = _ALIAS_BY_KEY[key]
        return _matched(raw_name, canonical, "alias")

    best_name, best_ratio = None, 0.0
    for candidate_key, canonical in _CANONICAL_BY_KEY.items():
        ratio = SequenceMatcher(None, key, candidate_key).ratio()
        if ratio > best_ratio:
            best_name, best_ratio = canonical, ratio
    if best_name is not None and best_ratio >= FUZZY_CUTOFF:
        result = _matched(raw_name, best_name, "fuzzy")
        result["fuzzy_ratio"] = round(best_ratio, 3)
        return result

    return {
        "raw": raw_name,
        "inci_name": None,
        "match_status": "unmatched",
        "functions": [],
    }


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
    }


def _matched(raw_name: str, canonical: str, status: str) -> dict[str, Any]:
    return {
        "raw": raw_name,
        "inci_name": canonical,
        "match_status": status,
        "functions": list(INGREDIENT_DICTIONARY[canonical]["functions"]),
    }
