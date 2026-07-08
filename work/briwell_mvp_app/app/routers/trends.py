from typing import Any

from fastapi import APIRouter, Depends

from app.core.auth import UserContext, require_roles
from app.trends.news_rss import fetch_news_signals

router = APIRouter(prefix="/trends", tags=["trends"])

_ALLOWED_COUNTRIES = {"MX", "PE", "EC"}
_ALLOWED_CATEGORIES = {
    "sunscreen",
    "calming_serum",
    "cleanser",
    "sheet_mask",
    "cushion_foundation",
}


@router.get("/news")
def news_signals(
    countries: str = "MX,PE,EC",
    product_categories: str = "sunscreen",
    max_items_per_query: int = 5,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    """Public-RSS market news signals for the discovery screen.

    Dry-run by default (sample rows); live fetch requires the NEWS_RSS gates.
    Items are market signals only — never creator workflow inputs.
    """

    normalized_countries = [
        item.strip().upper()
        for item in countries.split(",")
        if item.strip().upper() in _ALLOWED_COUNTRIES
    ] or ["MX", "PE", "EC"]
    normalized_categories = [
        item.strip()
        for item in product_categories.split(",")
        if item.strip() in _ALLOWED_CATEGORIES
    ] or ["sunscreen"]
    return fetch_news_signals(
        countries=normalized_countries,
        product_categories=normalized_categories,
        max_items_per_query=max_items_per_query,
    )
