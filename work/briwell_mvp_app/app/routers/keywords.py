from typing import Any, Literal

from fastapi import APIRouter

from app.core.db import database_enabled
from app.repositories import keywords as keyword_repository


router = APIRouter(prefix="/keywords", tags=["keywords"])

Country = Literal["MX", "PE", "EC"]


@router.get("")
def list_keywords(
    country: Country | None = None,
    product_category: str | None = None,
    status: str = "active",
) -> dict[str, Any]:
    if database_enabled():
        items = keyword_repository.list_keywords(
            country=country,
            product_category=product_category,
            status=status,
        )
        return {
            "items": items,
            "next_cursor": None,
            "filters": {
                "country": country,
                "product_category": product_category,
                "status": status,
            },
        }

    return {
        "items": [],
        "next_cursor": None,
        "filters": {
            "country": country,
            "product_category": product_category,
            "status": status,
        },
    }
