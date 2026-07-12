"""Regulatory pre-screening signals for MX/PE/EC (never legal advice).

Compares a normalized ingredient list against the code-seeded rule set and
returns per-country signal grades:

* ``blocked_candidate``    — at least one seeded *banned* substance matched
* ``restricted_candidate`` — at least one seeded *restricted* substance matched
* ``no_flag``              — nothing in the seed matched (NOT a clearance!)

The disclaimer travels inside every result payload so no UI can render the
signal without it (non-negotiable constraint 6: not legal advice).
"""

from typing import Any

from app.partners.ingredient_data import (
    REGULATORY_DISCLAIMER,
    REGULATORY_RULES,
    SEED_VERSION,
)

COUNTRIES = ("MX", "PE", "EC")

_RULES_BY_INCI_KEY: dict[str, list[dict[str, str]]] = {}
for _rule in REGULATORY_RULES:
    _RULES_BY_INCI_KEY.setdefault(_rule["inci_name"].lower(), []).append(_rule)


def screen_ingredients(normalized_items: list[dict[str, Any]]) -> dict[str, Any]:
    """Screen normalized ingredients; also checks raw strings of unmatched
    items so a seeded substance cannot hide behind a dictionary miss."""

    flags: list[dict[str, Any]] = []
    for item in normalized_items:
        names_to_check = set()
        if item.get("inci_name"):
            names_to_check.add(str(item["inci_name"]).lower())
        names_to_check.add(str(item.get("raw", "")).strip().lower())
        for name in names_to_check:
            for rule in _RULES_BY_INCI_KEY.get(name, []):
                flags.append(
                    {
                        "ingredient": rule["inci_name"],
                        "raw": item.get("raw"),
                        "country": rule["country"],
                        "rule_type": rule["rule_type"],
                        "detail": rule["detail"],
                        "source_ref": rule["source_ref"],
                    }
                )

    by_country = {}
    for country in COUNTRIES:
        country_flags = [flag for flag in flags if flag["country"] == country]
        if any(flag["rule_type"] == "banned" for flag in country_flags):
            grade = "blocked_candidate"
        elif country_flags:
            grade = "restricted_candidate"
        else:
            grade = "no_flag"
        by_country[country] = {"grade": grade, "flag_count": len(country_flags)}

    return {
        "flags": flags,
        "by_country": by_country,
        "seed_version": SEED_VERSION,
        "disclaimer": REGULATORY_DISCLAIMER,
    }
