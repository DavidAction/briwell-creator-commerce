from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import UserContext, require_roles
from app.core.db import database_enabled
from app.core.policy import (
    PolicyError,
    require_allowed_collection_source_type,
    require_allowed_source_risk,
)
from app.repositories import performance as performance_repository


router = APIRouter(prefix="/performance", tags=["performance"])

Platform = Literal["tiktok", "instagram", "other"]


class PerformanceSnapshotRequest(BaseModel):
    campaign_id: str | None = None
    outreach_id: str | None = None
    creator_id: str | None = None
    post_url: str | None = Field(default=None, max_length=2000)
    platform: Platform = "tiktok"
    tracking_url: str | None = Field(default=None, max_length=2000)
    coupon_code: str | None = Field(default=None, max_length=100)
    view_count: int | None = Field(default=None, ge=0)
    like_count: int | None = Field(default=None, ge=0)
    comment_count: int | None = Field(default=None, ge=0)
    share_count: int | None = Field(default=None, ge=0)
    click_count: int | None = Field(default=None, ge=0)
    conversion_count: int | None = Field(default=None, ge=0)
    revenue_usd: float | None = Field(default=None, ge=0)
    source_type: str = Field(min_length=1)
    source_risk_level: str = Field(min_length=1)
    measured_at: datetime | None = None


@router.post("/snapshots")
def create_performance_snapshot(
    payload: PerformanceSnapshotRequest,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    try:
        source_type = require_allowed_collection_source_type(payload.source_type)
        source_risk_level = require_allowed_source_risk(payload.source_risk_level)
    except PolicyError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "PERFORMANCE_SOURCE_NOT_ALLOWED",
                "message": "This performance source is blocked in MVP v0.1.",
                "details": {"reason": str(exc)},
            },
        ) from exc

    normalized = payload.model_dump()
    normalized["source_type"] = source_type
    normalized["source_risk_level"] = source_risk_level

    if database_enabled():
        created = performance_repository.create_performance_snapshot(normalized)
        return {
            "status": "persisted",
            "snapshot": created,
        }

    return {
        "status": "validated_not_persisted",
        "snapshot": normalized,
    }


@router.get("/campaigns/{campaign_id}/summary")
def get_campaign_performance_summary(
    campaign_id: str,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    if database_enabled():
        summary = performance_repository.campaign_summary(campaign_id)
    else:
        summary = {
            "campaign_id": campaign_id,
            "snapshot_count": 0,
            "view_count": 0,
            "like_count": 0,
            "comment_count": 0,
            "click_count": 0,
            "conversion_count": 0,
            "revenue_usd": 0,
        }
    return {
        "status": "ok",
        "summary": summary,
    }
