"""Orchestrates the pure-compute pipeline steps over a draft.

Used after AI extraction AND after every partner edit, so normalization,
validation, screening and completeness always describe the draft as it
currently is — never a stale earlier version.
"""

from typing import Any

from app.partners.normalization import normalize_ingredient_list
from app.partners.screening import screen_ingredients
from app.partners.scoring import completeness
from app.partners.validation import validate_draft


def enrich_draft(draft: dict[str, Any], photo_count: int) -> dict[str, Any]:
    normalized = normalize_ingredient_list(list(draft.get("ingredients_raw") or []))
    screening = screen_ingredients(normalized["items"])
    validation = validate_draft(draft, normalized)
    score = completeness(draft, normalized, screening, photo_count)
    return {
        "ingredients_normalized": normalized,
        "validation": validation,
        "regulatory": screening,
        "completeness": score,
    }
