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
INTENT_BALANCE_ORDER = ["discovery", "concern", "format", "commerce"]

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
    include_coverage_audit: bool = True


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


class DiscoveryCoverageAuditItem(BaseModel):
    country: Country
    product_category: ProductCategory
    selected_count: int
    available_count: int
    selected_intent_types: list[str]
    missing_intent_types: list[str]
    false_negative_risks: list[str]
    recommended_actions: list[str]


class DiscoveryPlanResult(BaseModel):
    status: Literal["planned"] = "planned"
    countries: list[Country]
    platforms: list[Platform]
    product_categories: list[ProductCategory]
    planned_count: int
    items: list[DiscoveryPlanItem]
    blocked_collection_source_types: list[str]
    manual_review_checklist: list[str] = Field(default_factory=list)
    coverage_audit: list[DiscoveryCoverageAuditItem] = Field(default_factory=list)
    recall_safeguards: list[str] = Field(default_factory=list)


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

    selected_rows = _select_balanced_rows(
        rows=eligible_rows,
        max_per_country_category=payload.max_keywords_per_country_category,
    )

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
    coverage_audit = (
        _build_coverage_audit(
            eligible_rows=eligible_rows,
            selected_rows=selected_rows,
            countries=countries,
            product_categories=product_categories,
        )
        if payload.include_coverage_audit
        else []
    )
    return DiscoveryPlanResult(
        countries=countries,
        platforms=platforms,
        product_categories=product_categories,
        planned_count=len(items),
        items=items,
        blocked_collection_source_types=sorted(BLOCKED_COLLECTION_SOURCE_TYPES),
        manual_review_checklist=checklist,
        coverage_audit=coverage_audit,
        recall_safeguards=_recall_safeguards(),
    )


def _select_balanced_rows(
    rows: list[KeywordSeedRow],
    max_per_country_category: int,
) -> list[KeywordSeedRow]:
    grouped: dict[tuple[str, str], list[KeywordSeedRow]] = {}
    for row in rows:
        grouped.setdefault((row.country, row.product_category), []).append(row)

    selected: list[KeywordSeedRow] = []
    for key in sorted(grouped):
        group = sorted(
            grouped[key],
            key=lambda row: (
                row.priority,
                INTENT_BALANCE_ORDER.index(row.intent_type)
                if row.intent_type in INTENT_BALANCE_ORDER
                else len(INTENT_BALANCE_ORDER),
                row.keyword or row.hashtag or "",
            ),
        )
        picked: list[KeywordSeedRow] = []
        for intent_type in INTENT_BALANCE_ORDER:
            if len(picked) >= max_per_country_category:
                break
            match = next((row for row in group if row.intent_type == intent_type and row not in picked), None)
            if match is not None:
                picked.append(match)
        for row in group:
            if len(picked) >= max_per_country_category:
                break
            if row not in picked:
                picked.append(row)
        selected.extend(picked)
    return selected


def _build_coverage_audit(
    eligible_rows: list[KeywordSeedRow],
    selected_rows: list[KeywordSeedRow],
    countries: list[Country],
    product_categories: list[ProductCategory],
) -> list[DiscoveryCoverageAuditItem]:
    audits: list[DiscoveryCoverageAuditItem] = []
    for country in countries:
        for product_category in product_categories:
            available = [
                row
                for row in eligible_rows
                if row.country == country and row.product_category == product_category
            ]
            if not available:
                audits.append(
                    DiscoveryCoverageAuditItem(
                        country=country,
                        product_category=product_category,
                        selected_count=0,
                        available_count=0,
                        selected_intent_types=[],
                        missing_intent_types=INTENT_BALANCE_ORDER,
                        false_negative_risks=[
                            "No seed queries exist for this country and product category.",
                        ],
                        recommended_actions=[
                            "Add local Spanish keyword, concern, format, and commerce seeds before collection.",
                        ],
                    )
                )
                continue

            selected = [
                row
                for row in selected_rows
                if row.country == country and row.product_category == product_category
            ]
            selected_intents = sorted({row.intent_type for row in selected})
            available_intents = {row.intent_type for row in available}
            missing_intents = [
                intent
                for intent in INTENT_BALANCE_ORDER
                if intent in available_intents and intent not in selected_intents
            ]
            risks = _false_negative_risks(missing_intents, selected_count=len(selected))
            actions = _coverage_recommended_actions(missing_intents, selected_count=len(selected))
            audits.append(
                DiscoveryCoverageAuditItem(
                    country=country,
                    product_category=product_category,
                    selected_count=len(selected),
                    available_count=len(available),
                    selected_intent_types=selected_intents,
                    missing_intent_types=missing_intents,
                    false_negative_risks=risks,
                    recommended_actions=actions,
                )
            )
    return audits


def _false_negative_risks(missing_intents: list[str], selected_count: int) -> list[str]:
    risks: list[str] = []
    if selected_count < 4:
        risks.append("Small keyword budget can overfit discovery to one creator archetype.")
    if "format" in missing_intents:
        risks.append("Missing format queries can miss review, tutorial, UGC, and routine creators.")
    if "concern" in missing_intents:
        risks.append("Missing concern queries can miss skin-problem-led skincare educators.")
    if "commerce" in missing_intents:
        risks.append("Missing commerce queries can miss creators with purchase-intent audiences.")
    if "discovery" in missing_intents:
        risks.append("Missing broad discovery queries can miss general K-beauty creators.")
    return risks


def _coverage_recommended_actions(missing_intents: list[str], selected_count: int) -> list[str]:
    actions: list[str] = []
    if selected_count < 4:
        actions.append("Use at least 4 keywords per country/product when budget allows.")
    if missing_intents:
        actions.append("Run a second-pass expansion for missing intent types before rejecting a market.")
    actions.append("Keep nano, micro, and mid-tier creators in first-pass screening; avoid hard follower cutoffs.")
    actions.append("Screen recent 20 posts before final exclusion so strong niche creators are not missed.")
    return actions


def _query_for_row(row: KeywordSeedRow) -> tuple[str, Literal["keyword", "hashtag"]]:
    if row.hashtag:
        return row.hashtag, "hashtag"
    if row.keyword:
        return row.keyword, "keyword"
    raise ValueError("Keyword seed row must include keyword or hashtag.")


def _manual_review_checklist() -> list[str]:
    return [
        "Confirm creator country signal matches MX, PE, or EC.",
        "Record profile URL, username, follower count, and the latest 20 approved recent post snapshots when available.",
        "Do not collect private, sensitive, or login-gated data.",
        "Mark do-not-contact or removal requests before any outreach.",
        "Use only manual, official_api, approved_provider, or creator_provided source types.",
        "Do not exclude candidates only because follower count is low; first screen content fit and audience intent.",
    ]


def _recall_safeguards() -> list[str]:
    return [
        "Do not apply hard follower-count cutoffs during discovery; segment nano, micro, and mid-tier creators after screening.",
        "Balance keyword seeds across discovery, concern, format, and commerce intent types.",
        "Run recent 20 post screening before rejecting borderline creators.",
        "Use second-pass expansion for missing country/product intent coverage before concluding a market is weak.",
        "Keep TikTok, Instagram, approved provider exports, manual import, and creator-provided lists as separate source lanes.",
    ]
