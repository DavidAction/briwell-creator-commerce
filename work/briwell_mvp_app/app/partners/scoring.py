"""Salsify-style completeness score: how ready is this draft to sell?

Weighted components (sum 100). The score is a readiness gauge for partners
and operators — it never gates approval by itself (the human decides).
"""

from typing import Any

WEIGHTS = {
    "basics": 20,       # product/brand name, category, size
    "ingredients": 30,  # INCI list present and mostly matched
    "images": 20,       # at least one photo upload linked
    "claims": 15,       # claims reviewed (allowed list non-empty or explicit none)
    "regulatory": 15,   # screening ran with no flags
}


def completeness(
    draft: dict[str, Any],
    normalized: dict[str, Any] | None,
    screening: dict[str, Any] | None,
    photo_count: int,
) -> dict[str, Any]:
    components: dict[str, dict[str, Any]] = {}

    basics_have = sum(
        1
        for field in ("product_name", "brand_name", "product_category", "size")
        if str(draft.get(field) or "").strip()
    )
    components["basics"] = _component(WEIGHTS["basics"], basics_have / 4)

    if normalized and normalized.get("total"):
        matched_ratio = normalized["matched"] / normalized["total"]
        listed = 0.5 + 0.5 * matched_ratio  # having a list at all is half the credit
    else:
        listed = 0.0
    components["ingredients"] = _component(WEIGHTS["ingredients"], listed)

    components["images"] = _component(WEIGHTS["images"], 1.0 if photo_count > 0 else 0.0)

    claims_reviewed = bool(draft.get("key_claims_allowed")) or draft.get("claims_none") is True
    components["claims"] = _component(WEIGHTS["claims"], 1.0 if claims_reviewed else 0.0)

    if screening is None:
        regulatory_ratio = 0.0
    else:
        grades = [entry["grade"] for entry in screening["by_country"].values()]
        if any(grade == "blocked_candidate" for grade in grades):
            regulatory_ratio = 0.0
        elif any(grade == "restricted_candidate" for grade in grades):
            regulatory_ratio = 0.5
        else:
            regulatory_ratio = 1.0
    components["regulatory"] = _component(WEIGHTS["regulatory"], regulatory_ratio)

    score = round(sum(component["earned"] for component in components.values()))
    return {"score": score, "components": components}


def _component(weight: int, ratio: float) -> dict[str, Any]:
    bounded = max(0.0, min(1.0, ratio))
    return {"weight": weight, "earned": round(weight * bounded, 1)}
