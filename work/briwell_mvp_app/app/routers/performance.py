from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.commerce.money import to_usd
from app.core.auth import UserContext, require_roles
from app.core.db import database_enabled
from app.core.policy import (
    PolicyError,
    require_allowed_collection_source_type,
    require_allowed_source_risk,
)
from app.repositories import performance as performance_repository
from app.routers.commerce import Currency, _validate_currency_fx


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
    revenue_amount: Decimal | None = Field(default=None, ge=0)
    revenue_currency: Currency | None = None
    fx_rate_usd: Decimal | None = Field(default=None, gt=0)
    source_type: str = Field(min_length=1)
    source_risk_level: str = Field(min_length=1)
    measured_at: datetime | None = None

    @model_validator(mode="after")
    def validate_revenue_currency_triple(self) -> "PerformanceSnapshotRequest":
        # Mirrors chk_snapshot_currency_triple in migration 008: the
        # currency-explicit triple travels together or not at all.
        triple = (self.revenue_amount, self.revenue_currency, self.fx_rate_usd)
        provided = sum(1 for value in triple if value is not None)
        if provided not in (0, len(triple)):
            raise ValueError(
                "revenue_amount, revenue_currency, and fx_rate_usd must be "
                "provided together or not at all."
            )
        if self.revenue_currency is not None and self.fx_rate_usd is not None:
            _validate_currency_fx(self.revenue_currency, self.fx_rate_usd)
        return self


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

    # Derive revenue_usd from the currency triple in Python as well as via the
    # derive_snapshot_revenue_usd DB trigger: the trigger never runs on the
    # USE_DATABASE=false validated_not_persisted path, and deriving here keeps
    # the persisted path correct even if the trigger is dropped or bypassed.
    # Like the trigger, the derived value wins over any caller-sent revenue_usd.
    if payload.revenue_amount is not None and payload.fx_rate_usd is not None:
        normalized["revenue_usd"] = to_usd(payload.revenue_amount, payload.fx_rate_usd)

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
            "revenue_by_currency": [],
        }
    return {
        "status": "ok",
        "summary": summary,
    }
