from typing import Any

from fastapi import APIRouter, Depends

from app.core.auth import UserContext, require_roles
from app.providers.kbeauty_keywords import Country
from app.providers.kbeauty_keywords import ProductCategory
from app.providers.kbeauty_keywords import build_kbeauty_keyword_playbook
from app.providers.tiktok import TikTokDiscoveryRunRequest
from app.providers.tiktok import provider_status
from app.providers.tiktok import run_discovery


router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/tiktok/status")
def tiktok_provider_status(
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    return provider_status()


@router.get("/tiktok/keyword-playbook")
def tiktok_keyword_playbook(
    countries: str = "MX,PE,EC",
    product_categories: str = "sunscreen,calming_serum,cleanser",
    max_keywords_per_country_category: int = 8,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    normalized_countries = _split_countries(countries)
    normalized_categories = _split_categories(product_categories)
    items = build_kbeauty_keyword_playbook(
        countries=normalized_countries,
        product_categories=normalized_categories,
        max_keywords_per_country_category=max_keywords_per_country_category,
    )
    return {
        "status": "planned",
        "strategy": "latam_kbeauty_20s_30s",
        "countries": normalized_countries,
        "product_categories": normalized_categories,
        "keyword_count": len(items),
        "items": [item.model_dump() for item in items],
        "selection_rules": [
            "Balance trend, discovery, concern, format, and commerce intent.",
            "Prioritize Spanish queries used by Gen Z and young millennial beauty buyers.",
            "Include country-localized variants for MX, PE, and EC.",
            "Avoid hard follower cutoffs until recent 20 post quality is screened.",
        ],
    }


@router.post("/tiktok/discovery-runs")
def create_tiktok_discovery_run(
    payload: TikTokDiscoveryRunRequest,
    _user: UserContext = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    result = run_discovery(payload)
    return result.model_dump()


def _split_countries(value: str) -> list[Country]:
    allowed = {"MX", "PE", "EC"}
    result = [
        item.strip().upper()
        for item in value.split(",")
        if item.strip().upper() in allowed
    ]
    return result or ["MX", "PE", "EC"]


def _split_categories(value: str) -> list[ProductCategory]:
    allowed = {
        "sunscreen",
        "calming_serum",
        "cleanser",
        "sheet_mask",
        "cushion_foundation",
    }
    result = [
        item.strip()
        for item in value.split(",")
        if item.strip() in allowed
    ]
    return result or ["sunscreen", "calming_serum", "cleanser"]

