from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.auth import UserContext, require_roles
from app.core.db import database_enabled
from app.repositories import products as product_repository


router = APIRouter(prefix="/products", tags=["products"])

ProductCategory = Literal[
    "sunscreen",
    "calming_serum",
    "cleanser",
    "sheet_mask",
    "cushion_foundation",
]


class ProductCreateRequest(BaseModel):
    brand_name: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    product_category: ProductCategory
    country_availability: list[Literal["MX", "PE", "EC"]] = Field(default_factory=list)
    key_claims_allowed: list[str] = Field(default_factory=list)
    claims_disallowed: list[str] = Field(default_factory=list)


@router.get("")
def list_products(product_category: ProductCategory | None = None) -> dict[str, Any]:
    if database_enabled():
        items = product_repository.list_products(product_category=product_category)
        return {
            "items": items,
            "next_cursor": None,
            "filters": {"product_category": product_category},
        }

    return {
        "items": [],
        "next_cursor": None,
        "filters": {"product_category": product_category},
    }


@router.post("")
def create_product(
    payload: ProductCreateRequest,
    _user: UserContext = Depends(require_roles("admin", "campaign_manager")),
) -> dict[str, Any]:
    if database_enabled():
        created = product_repository.create_product(payload.model_dump())
        return {
            "status": "persisted",
            "product": created,
        }

    return {
        "status": "validated_not_persisted",
        "product": payload.model_dump(),
    }
