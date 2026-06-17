from __future__ import annotations

import csv
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.core.policy import BLOCKED_COLLECTION_SOURCE_TYPES


Country = Literal["MX", "PE", "EC"]
ProductCategory = Literal[
    "sunscreen",
    "calming_serum",
    "cleanser",
    "sheet_mask",
    "cushion_foundation",
]
Platform = Literal["tiktok", "instagram"]

ROOT = Path(__file__).resolve().parents[2]
KEYWORD_CSV = ROOT / "db" / "seeds" / "keyword_seed_v0.csv"
ALLOWED_DISCOVERY_SOURCE_TYPES = [
    "manual",
    "official_api",
    "approved_provider",
    "creator_provided",
]


class KeywordSeedRow(BaseModel):
    country: Country
    language: str = "es"
    product_category: ProductCategory
    intent_type: Literal["discovery", "concern", "format", "commerce"]
    keyword: str | None = None
    hashtag: str | None = None
    priority: int = Field(ge=1, le=5)
    notes: str | None = None


class DiscoveryPlanInput(BaseModel):
    countries: list[Country] = Field(default_factory=lambda: ["MX", "PE", "EC"])
    product_categories: list[ProductCategory] = Field(default_factory=list)
    platforms: list[Platform] = Field(default_factory=lambda: ["tiktok"])
    max_keywords_per_country_category: int = Field(default=5, ge=1, le=20)
    include_manual_review_checklist: bool = True


class DiscoveryPlanItem(BaseModel):
    country: Country
    platform: Platform
    product_category: ProductCategory
    query: str
    query_type: Literal["keyword", "hashtag"]
    intent_type: str
    priority: int
    source_type_options: list[str]
    source_risk_level: Literal["low", "low_medium"]
    next_action: str
    notes: str | None = None


class DiscoveryPlanResult(BaseModel):
    status: Literal["planned"] = "planned"
    countries: list[Country]
    platforms: list[Platform]
    product_categories: list[ProductCategory]
    planned_count: int
    items: list[DiscoveryPlanItem]
    blocked_collection_source_types: list[str]
    manual_review_checklist: list[str] = Field(default_factory=list)


def load_keyword_seed(path: Path = KEYWORD_CSV) -> list[KeywordSeedRow]:
    rows: list[KeywordSeedRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                KeywordSeedRow(
                    country=row["country"],
                    language=row.get("language") or "es",
                    product_category=row["product_category"],
                    intent_type=row["intent_type"],
                    keyword=row.get("keyword") or None,
                    hashtag=row.get("hashtag") or None,
                    priority=int(row["priority"]),
                    notes=row.get("notes") or None,
                )
            )
    return rows


def build_discovery_plan(payload: DiscoveryPlanInput) -> DiscoveryPlanResult:
    product_filter = set(payload.product_categories)
    countries = list(dict.fromkeys(payload.countries))
    platforms = list(dict.fromkeys(payload.platforms))

    eligible_rows = [
        row
        for row in load_keyword_seed()
        if row.country in countries
        and (not product_filter or row.product_category in product_filter)
    ]
    eligible_rows.sort(
        key=lambda row: (
            row.country,
            row.product_category,
            row.priority,
            row.intent_type,
            row.keyword or row.hashtag or "",
        )
    )

    selected_rows: list[KeywordSeedRow] = []
    counters: dict[tuple[str, str], int] = {}
    for row in eligible_rows:
        key = (row.country, row.product_category)
        current_count = counters.get(key, 0)
        if current_count >= payload.max_keywords_per_country_category:
            continue
        selected_rows.append(row)
        counters[key] = current_count + 1

    items: list[DiscoveryPlanItem] = []
    for row in selected_rows:
        for platform in platforms:
            query, query_type = _query_for_row(row)
            items.append(
                DiscoveryPlanItem(
                    country=row.country,
                    platform=platform,
                    product_category=row.product_category,
                    query=query,
                    query_type=query_type,
                    intent_type=row.intent_type,
                    priority=row.priority,
                    source_type_options=ALLOWED_DISCOVERY_SOURCE_TYPES,
                    source_risk_level="low" if platform == "tiktok" else "low_medium",
                    next_action="Collect candidates through manual review, creator opt-in, official API, or approved provider export.",
                    notes=row.notes,
                )
            )

    product_categories = (
        payload.product_categories
        if payload.product_categories
        else sorted({row.product_category for row in eligible_rows})
    )
    checklist = _manual_review_checklist() if payload.include_manual_review_checklist else []
    return DiscoveryPlanResult(
        countries=countries,
        platforms=platforms,
        product_categories=product_categories,
        planned_count=len(items),
        items=items,
        blocked_collection_source_types=sorted(BLOCKED_COLLECTION_SOURCE_TYPES),
        manual_review_checklist=checklist,
    )


def _query_for_row(row: KeywordSeedRow) -> tuple[str, Literal["keyword", "hashtag"]]:
    if row.hashtag:
        return row.hashtag, "hashtag"
    if row.keyword:
        return row.keyword, "keyword"
    raise ValueError("Keyword seed row must include keyword or hashtag.")


def _manual_review_checklist() -> list[str]:
    return [
        "Confirm creator country signal matches MX, PE, or EC.",
        "Record profile URL, username, follower count, and recent representative video URLs.",
        "Do not collect private, sensitive, or login-gated data.",
        "Mark do-not-contact or removal requests before any outreach.",
        "Use only manual, official_api, approved_provider, or creator_provided source types.",
    ]
