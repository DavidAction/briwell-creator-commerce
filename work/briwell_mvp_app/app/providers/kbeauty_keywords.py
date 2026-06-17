from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Country = Literal["MX", "PE", "EC"]
ProductCategory = Literal[
    "sunscreen",
    "calming_serum",
    "cleanser",
    "sheet_mask",
    "cushion_foundation",
]
IntentType = Literal["discovery", "concern", "format", "commerce", "trend"]


class KeywordPlaybookItem(BaseModel):
    country: Country
    product_category: ProductCategory
    intent_type: IntentType
    query: str = Field(min_length=1)
    query_type: Literal["keyword", "hashtag"] = "keyword"
    priority: int = Field(ge=1, le=5)
    audience: Literal["gen_z", "young_millennial", "both"] = "both"
    reason: str


COUNTRY_TERMS: dict[Country, tuple[str, str, str]] = {
    "MX": ("mexico", "mexicana", "mx"),
    "PE": ("peru", "peruana", "pe"),
    "EC": ("ecuador", "ecuatoriana", "ec"),
}


PRODUCT_QUERY_BANK: dict[ProductCategory, list[tuple[IntentType, str, int, str]]] = {
    "sunscreen": [
        ("trend", "spf coreano viral tiktok", 1, "Viral SPF discovery for TikTok-native shoppers."),
        ("discovery", "protector solar coreano", 1, "Core K-beauty SPF search."),
        ("concern", "bloqueador coreano sin grasa", 1, "Texture concern for oily and humid climates."),
        ("concern", "protector solar para piel mixta", 1, "High-fit concern for 20s and 30s routines."),
        ("format", "grwm protector solar coreano", 1, "GRWM format tends to surface routine creators."),
        ("format", "resena honesta protector solar", 1, "Honest-review creators are strong for commerce trust."),
        ("commerce", "donde comprar protector solar coreano", 1, "Purchase-intent query."),
        ("commerce", "lo vi en tiktok protector solar", 2, "Social proof and TikTok discovery intent."),
    ],
    "calming_serum": [
        ("trend", "serum coreano viral tiktok", 1, "Viral serum discovery."),
        ("discovery", "serum calmante coreano", 1, "Core calming-serum query."),
        ("concern", "barrera de la piel serum", 1, "Barrier-care concern without medical claims."),
        ("concern", "rutina piel sensible serum coreano", 1, "Sensitive-skin routine fit."),
        ("format", "probando serum coreano", 1, "Try-on and first-impression format."),
        ("format", "resena honesta serum coreano", 1, "Review creator signal."),
        ("commerce", "serum coreano recomendado", 2, "Recommendation and conversion intent."),
        ("commerce", "skincare coreano para piel sensible", 2, "K-beauty concern-to-commerce bridge."),
    ],
    "cleanser": [
        ("trend", "limpiador coreano viral tiktok", 1, "Viral cleanser discovery."),
        ("discovery", "limpiador facial coreano", 1, "Core cleanser search."),
        ("concern", "limpiador para piel grasa coreano", 1, "Oily-skin concern."),
        ("concern", "limpiador suave piel sensible", 1, "Gentle cleanser concern."),
        ("format", "doble limpieza coreana rutina", 1, "Routine education format."),
        ("format", "aceite limpiador coreano resena", 1, "Oil-cleanser review format."),
        ("commerce", "limpiador coreano recomendado", 2, "Recommendation intent."),
        ("commerce", "skincare coreano basico rutina", 2, "Starter routine intent."),
    ],
    "sheet_mask": [
        ("trend", "mascarilla coreana viral tiktok", 1, "Viral mask discovery."),
        ("discovery", "mascarilla facial coreana", 1, "Core sheet-mask search."),
        ("concern", "mascarilla hidratante coreana", 1, "Hydration concern."),
        ("concern", "piel glow mascarilla coreana", 1, "Glow look for young shoppers."),
        ("format", "selfcare mascarilla coreana", 1, "Self-care format."),
        ("format", "unboxing kbeauty mascarillas", 1, "UGC unboxing format."),
        ("commerce", "kbeauty barato mascarillas", 2, "Affordable K-beauty angle."),
        ("commerce", "mascarilla coreana recomendada", 2, "Recommendation intent."),
    ],
    "cushion_foundation": [
        ("trend", "cushion coreano viral tiktok", 1, "Viral cushion discovery."),
        ("discovery", "cushion coreano", 1, "Core cushion query."),
        ("concern", "base ligera para diario", 1, "Daily lightweight base concern."),
        ("concern", "maquillaje coreano piel mixta", 1, "Combination-skin makeup fit."),
        ("format", "maquillaje coreano natural tutorial", 1, "Natural K-makeup tutorial format."),
        ("format", "glass skin maquillaje", 1, "K-beauty look signal."),
        ("commerce", "cushion coreano recomendado", 2, "Recommendation intent."),
        ("commerce", "dupes maquillaje coreano", 2, "Dupe and affordable shopping intent."),
    ],
}


HASHTAG_BANK: dict[ProductCategory, list[tuple[IntentType, str, int, str]]] = {
    "sunscreen": [
        ("discovery", "kbeauty", 1, "Broad K-beauty discovery hashtag."),
        ("concern", "pielgrasa", 1, "Oily-skin audience."),
        ("format", "grwm", 1, "Routine format."),
        ("commerce", "skincarerecomendado", 2, "Recommendation intent."),
    ],
    "calming_serum": [
        ("discovery", "serumcoreano", 1, "Serum discovery."),
        ("concern", "pielsensible", 1, "Sensitive-skin audience."),
        ("concern", "barreracutanea", 1, "Barrier-care concern."),
        ("format", "resenaskincare", 2, "Review format."),
    ],
    "cleanser": [
        ("discovery", "limpiadorfacial", 1, "Cleanser discovery."),
        ("format", "doblelimpieza", 1, "Double-cleansing format."),
        ("format", "rutinafacial", 1, "Routine creators."),
        ("commerce", "skincarebasico", 2, "Starter routine shoppers."),
    ],
    "sheet_mask": [
        ("discovery", "mascarillacoreana", 1, "Sheet-mask discovery."),
        ("concern", "hidratacion", 1, "Hydration concern."),
        ("format", "selfcare", 1, "Self-care content."),
        ("commerce", "kbeautybarato", 2, "Affordable K-beauty."),
    ],
    "cushion_foundation": [
        ("discovery", "maquillajecoreano", 1, "K-makeup discovery."),
        ("format", "glassskin", 1, "Look-led creators."),
        ("format", "maquillajenatural", 1, "Natural makeup format."),
        ("commerce", "dupesmaquillaje", 2, "Dupe shopping intent."),
    ],
}


def build_kbeauty_keyword_playbook(
    countries: list[Country],
    product_categories: list[ProductCategory],
    max_keywords_per_country_category: int = 8,
) -> list[KeywordPlaybookItem]:
    items: list[KeywordPlaybookItem] = []
    for country in list(dict.fromkeys(countries)):
        country_name, demonym, short_code = COUNTRY_TERMS[country]
        for category in list(dict.fromkeys(product_categories)):
            candidates = _country_product_candidates(country, country_name, demonym, short_code, category)
            candidates.sort(key=lambda item: (item.priority, _intent_order(item.intent_type), item.query))
            selected = _balanced_select(candidates, max_keywords_per_country_category)
            items.extend(selected)
    return items


def _country_product_candidates(
    country: Country,
    country_name: str,
    demonym: str,
    short_code: str,
    category: ProductCategory,
) -> list[KeywordPlaybookItem]:
    rows: list[KeywordPlaybookItem] = []
    for intent_type, query, priority, reason in PRODUCT_QUERY_BANK[category]:
        localized_queries = [query, f"{query} {country_name}"]
        if intent_type in {"trend", "format"}:
            localized_queries.append(f"{query} {demonym}")
        for localized in localized_queries:
            rows.append(
                KeywordPlaybookItem(
                    country=country,
                    product_category=category,
                    intent_type=intent_type,
                    query=localized,
                    query_type="keyword",
                    priority=priority,
                    audience=_audience_for_query(localized),
                    reason=reason,
                )
            )
    for intent_type, hashtag, priority, reason in HASHTAG_BANK[category]:
        rows.append(
            KeywordPlaybookItem(
                country=country,
                product_category=category,
                intent_type=intent_type,
                query=f"#{hashtag}{short_code}" if hashtag in {"kbeauty", "maquillajecoreano"} else f"#{hashtag}",
                query_type="hashtag",
                priority=priority,
                audience="both",
                reason=reason,
            )
        )
    return _dedupe_keyword_items(rows)


def _balanced_select(
    rows: list[KeywordPlaybookItem],
    max_count: int,
) -> list[KeywordPlaybookItem]:
    selected: list[KeywordPlaybookItem] = []
    for intent in ("trend", "discovery", "concern", "format", "commerce"):
        if len(selected) >= max_count:
            break
        match = next((row for row in rows if row.intent_type == intent and row not in selected), None)
        if match is not None:
            selected.append(match)
    for row in rows:
        if len(selected) >= max_count:
            break
        if row not in selected:
            selected.append(row)
    return selected


def _dedupe_keyword_items(rows: list[KeywordPlaybookItem]) -> list[KeywordPlaybookItem]:
    seen: set[tuple[str, str, str, str]] = set()
    result: list[KeywordPlaybookItem] = []
    for row in rows:
        key = (row.country, row.product_category, row.query_type, row.query.lower())
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _intent_order(intent_type: str) -> int:
    order = {
        "trend": 0,
        "discovery": 1,
        "concern": 2,
        "format": 3,
        "commerce": 4,
    }
    return order.get(intent_type, 99)


def _audience_for_query(query: str) -> Literal["gen_z", "young_millennial", "both"]:
    lowered = query.lower()
    if any(term in lowered for term in ("viral", "tiktok", "grwm", "dupes", "glass skin")):
        return "gen_z"
    if any(term in lowered for term in ("rutina", "resena honesta", "diario", "recomendado")):
        return "young_millennial"
    return "both"

