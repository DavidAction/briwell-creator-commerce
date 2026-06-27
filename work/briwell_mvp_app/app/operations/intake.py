"""Live Data Intake v1 — one validation contract for every approved source lane.

Standardizes manual CSV, approved_provider, creator_provided, and provider_scrape inputs
into a single pre-import validation report: the source-policy decision, required-column
presence per creator row, recommended-column coverage, and the existing import quality
gate. This is what turns the console from a demo into an operating tool — operators see
exactly what is missing before real creator data enters the pipeline.
"""

from __future__ import annotations

from typing import Any

from app.core.policy import (
    PROVIDER_SCRAPE_SOURCE_TYPES,
    PolicyError,
    require_allowed_collection_source_type,
    require_allowed_source_risk,
)
from app.operations.workflows import evaluate_import_quality


REQUIRED_CREATOR_COLUMNS = ("country", "username", "profile_url", "source_risk_level")
RECOMMENDED_CREATOR_COLUMNS = ("display_name", "bio", "follower_count", "language")
RECOMMENDED_POST_COLUMNS = ("url", "caption", "view_count", "like_count", "comment_count", "hashtags", "transcript")

_EMPTY = (None, "", [])


def _source_decision(source_type: str, source_risk_level: str) -> dict[str, Any]:
    decision: dict[str, Any] = {
        "source_type": source_type,
        "source_risk_level": source_risk_level,
        "allowed": True,
        "reasons": [],
        "is_scrape_lane": False,
    }
    try:
        normalized_type = require_allowed_collection_source_type(source_type)
        decision["normalized_source_type"] = normalized_type
        decision["is_scrape_lane"] = normalized_type in PROVIDER_SCRAPE_SOURCE_TYPES
    except PolicyError as exc:
        decision["allowed"] = False
        decision["reasons"].append(f"source_type_{exc}")
    try:
        decision["normalized_source_risk_level"] = require_allowed_source_risk(source_risk_level)
    except PolicyError as exc:
        decision["allowed"] = False
        decision["reasons"].append(f"source_risk_{exc}")
    return decision


def _column_coverage(rows: list[dict[str, Any]], columns: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    total = len(rows) or 1
    coverage: dict[str, dict[str, Any]] = {}
    for column in columns:
        present = sum(1 for row in rows if row.get(column) not in _EMPTY)
        coverage[column] = {"present": present, "coverage_percent": round(present / total * 100)}
    return coverage


def validate_intake(
    source_type: str,
    source_risk_level: str,
    creators: list[dict[str, Any]],
    recent_posts_by_creator: dict[str, list[dict[str, Any]]] | None = None,
    expected_countries: list[str] | None = None,
) -> dict[str, Any]:
    recent_posts_by_creator = recent_posts_by_creator or {}
    source_decision = _source_decision(source_type, source_risk_level)

    missing_required_rows: list[dict[str, Any]] = []
    for index, creator in enumerate(creators, start=1):
        missing = [column for column in REQUIRED_CREATOR_COLUMNS if creator.get(column) in _EMPTY]
        if missing:
            missing_required_rows.append(
                {"row": index, "username": creator.get("username"), "missing": missing}
            )

    quality_gate = evaluate_import_quality(
        creators,
        recent_posts_by_creator,
        expected_countries=expected_countries,
    )

    all_posts = [post for posts in recent_posts_by_creator.values() for post in posts]

    blocked = (
        not source_decision["allowed"]
        or quality_gate["overall_status"] == "blocked"
        or bool(missing_required_rows)
    )
    status = "blocked" if blocked else quality_gate["overall_status"]

    notes: list[str] = []
    if source_decision.get("is_scrape_lane"):
        notes.append(
            "provider_scrape lane: elevated review and deferred legal/ToS confirmation. "
            "Keep live provider calls opt-in (default OFF)."
        )
    if missing_required_rows:
        notes.append(f"{len(missing_required_rows)} creator rows are missing required columns.")

    return {
        "status": status,
        "ready_to_import": not blocked,
        "source_decision": source_decision,
        "creator_rows": {
            "total": len(creators),
            "required_columns": list(REQUIRED_CREATOR_COLUMNS),
            "missing_required": missing_required_rows,
            "recommended_coverage": _column_coverage(creators, RECOMMENDED_CREATOR_COLUMNS),
        },
        "recent_posts": {
            "total": len(all_posts),
            "recommended_columns": list(RECOMMENDED_POST_COLUMNS),
            "recommended_coverage": _column_coverage(all_posts, RECOMMENDED_POST_COLUMNS),
        },
        "quality_gate": quality_gate,
        "notes": notes,
    }
