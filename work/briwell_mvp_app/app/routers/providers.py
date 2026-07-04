from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import UserContext, require_roles
from app.providers.base import ProviderRunRequest
from app.providers.kbeauty_keywords import Country
from app.providers.kbeauty_keywords import ProductCategory
from app.providers.kbeauty_keywords import build_kbeauty_keyword_playbook
from app.providers.registry import UnknownProviderError, get_provider, list_status
from app.providers.tiktok import TikTokDiscoveryRunRequest
from app.providers.tiktok import provider_status
from app.providers.tiktok import run_discovery


router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/status")
def all_providers_status(
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    """Provider-neutral status roll-up for every registered data-intake provider."""

    return {"items": [item.model_dump() for item in list_status()]}


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


@router.post("/creator-provided/import")
def import_creator_provided_data(
    payload: ProviderRunRequest,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    """Accept uploaded creator-provided rows and return normalized + import payloads.

    Thin, explicit wrapper around the ``creator_provided`` provider so callers
    have a purpose-named endpoint for uploads without needing to know the
    generic ``/providers/{name}/discovery-runs`` route.
    """

    provider = get_provider("creator_provided")
    result = provider.run(payload)
    return result.model_dump()


@router.post("/{name}/discovery-runs")
def create_provider_discovery_run(
    name: str,
    payload: ProviderRunRequest,
    _user: UserContext = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    """Delegate a discovery/import run to any registered provider by name.

    dry_run/live gating is entirely handled by the provider itself; unknown
    provider names return a clear 404 instead of a crash. Registered after all
    other static ``/providers/...`` routes so it never shadows them.
    """

    try:
        provider = get_provider(name)
    except UnknownProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "PROVIDER_NOT_FOUND",
                "message": str(exc),
            },
        ) from exc

    result = provider.run(payload)
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

