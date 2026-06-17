from typing import Any

from fastapi import APIRouter, Depends

from app.core.auth import UserContext, require_roles
from app.core.policy import ALLOWED_COLLECTION_SOURCE_TYPES
from app.core.policy import BLOCKED_COLLECTION_SOURCE_TYPES
from app.discovery.planner import DiscoveryPlanInput
from app.discovery.planner import build_discovery_plan


router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.post("/plans")
def create_discovery_plan(
    payload: DiscoveryPlanInput,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    result = build_discovery_plan(payload)
    return result.model_dump()


@router.get("/source-policy")
def get_discovery_source_policy() -> dict[str, Any]:
    return {
        "allowed_source_types": sorted(ALLOWED_COLLECTION_SOURCE_TYPES),
        "blocked_source_types": sorted(BLOCKED_COLLECTION_SOURCE_TYPES),
        "policy": "MVP uses compliant collection paths only. Unauthorized scraping is blocked.",
    }
