from typing import Any

from fastapi import APIRouter, Depends

from app.compliance.country_rules import Country
from app.compliance.country_rules import CountryClaimsInput
from app.compliance.country_rules import ProductCategory
from app.compliance.country_rules import evaluate_country_claims
from app.compliance.country_rules import list_country_rules
from app.core.auth import UserContext, require_roles


router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/rules")
def get_compliance_rules(
    country: Country | None = None,
    product_category: ProductCategory | None = None,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    rules = list_country_rules(country=country, product_category=product_category)
    return {
        "items": [rule.model_dump() for rule in rules],
        "filters": {
            "country": country,
            "product_category": product_category,
        },
        "legal_note": "MVP rules are operational safeguards and not legal advice.",
    }


@router.post("/country-claims-check")
def run_country_claims_check(
    payload: CountryClaimsInput,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    result = evaluate_country_claims(payload)
    return result.model_dump()
