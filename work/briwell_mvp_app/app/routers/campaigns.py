from datetime import date
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from app.ai.dm import build_dm_drafts
from app.core.auth import UserContext, require_roles
from app.core.db import database_enabled
from app.core.policy import PolicyError, require_dm_allowed
from app.ranking.campaign_candidates import priority_label
from app.ranking.campaign_candidates import rank_candidate_rows
from app.repositories import campaigns as campaign_repository
from app.repositories import outreach as outreach_repository


router = APIRouter(prefix="/campaigns", tags=["campaigns"])

Country = Literal["MX", "PE", "EC"]
ProductCategory = Literal[
    "sunscreen",
    "calming_serum",
    "cleanser",
    "sheet_mask",
    "cushion_foundation",
]
CampaignStatus = Literal["draft", "active", "paused", "completed", "cancelled"]
SalesChannel = Literal[
    "tiktok_shop",
    "shopify",
    "mercado_libre",
    "instagram_dm",
    "whatsapp",
    "reseller_link",
    "other",
]
DmVariant = Literal["soft_intro", "product_review", "ugc_collaboration", "commerce_collaboration"]
CreatorSegment = Literal[
    "viral_micro",
    "commerce_creator",
    "beauty_educator",
    "ugc_creator",
    "brand_builder",
    "review_creator",
]


class CampaignCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    product_id: UUID | None = None
    country: Country
    product_category: ProductCategory
    campaign_goal: str = Field(min_length=1, max_length=1000)
    budget: float | None = Field(default=None, ge=0)
    sales_channel: SalesChannel | None = None
    tracking_url: str | None = Field(default=None, max_length=2000)
    coupon_code_prefix: str | None = Field(default=None, max_length=50)
    target_creator_count: int | None = Field(default=None, ge=0)
    target_post_count: int | None = Field(default=None, ge=0)
    start_date: date | None = None
    end_date: date | None = None
    status: CampaignStatus = "draft"

    @model_validator(mode="after")
    def validate_dates(self) -> "CampaignCreateRequest":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date.")
        return self


class CampaignOutreachCandidateSnapshot(BaseModel):
    creator_id: str = Field(min_length=1)
    country: Country
    username: str = Field(min_length=1)
    profile_url: str = Field(min_length=1)
    source_risk_level: str = Field(min_length=1)
    display_name: str | None = None
    bio: str | None = None
    follower_count: int | None = Field(default=None, ge=0)
    status: str = "active"
    do_not_contact: bool = False
    removal_requested_at: str | None = None
    final_score: float | None = Field(default=None, ge=0, le=100)
    risk_penalty: float | None = Field(default=None, ge=0, le=30)
    segment: CreatorSegment | None = None
    recommended_products: list[ProductCategory] = Field(default_factory=list, max_length=5)
    recommended_campaign_angle: str | None = None


class CampaignOutreachDraftRequest(BaseModel):
    creator_ids: list[str] = Field(default_factory=list, max_length=20)
    candidate_snapshots: list[CampaignOutreachCandidateSnapshot] = Field(
        default_factory=list,
        max_length=20,
    )
    product_category: ProductCategory | None = None
    product_name: str | None = None
    dm_variant: DmVariant = "soft_intro"
    model_alias: str = "dm_draft"
    min_score: float = Field(default=70, ge=0, le=100)
    max_risk_penalty: float = Field(default=10, ge=0, le=30)
    exclude_existing_outreach: bool = True


@router.get("")
def list_campaigns(
    country: Country | None = None,
    status: CampaignStatus | None = None,
    product_category: ProductCategory | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    if database_enabled():
        items = campaign_repository.list_campaigns(
            country=country,
            status=status,
            product_category=product_category,
            limit=limit,
        )
        return {
            "items": items,
            "next_cursor": None,
            "filters": {
                "country": country,
                "status": status,
                "product_category": product_category,
                "limit": limit,
            },
        }

    return {
        "items": [],
        "next_cursor": None,
        "filters": {
            "country": country,
            "status": status,
            "product_category": product_category,
            "limit": limit,
        },
    }


@router.post("")
def create_campaign(
    payload: CampaignCreateRequest,
    _user: UserContext = Depends(require_roles("admin", "campaign_manager")),
) -> dict[str, Any]:
    campaign = payload.model_dump()
    if database_enabled():
        created = campaign_repository.create_campaign(campaign)
        return {
            "status": "persisted",
            "campaign": created,
        }

    return {
        "status": "validated_not_persisted",
        "campaign": campaign,
    }


@router.post("/{campaign_id}/outreach-drafts")
def prepare_campaign_outreach_drafts(
    campaign_id: str,
    payload: CampaignOutreachDraftRequest,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    if not payload.creator_ids and not payload.candidate_snapshots:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "OUTREACH_CANDIDATES_REQUIRED",
                "message": "Provide creator_ids in DB mode or candidate_snapshots in local mode.",
            },
        )

    if database_enabled():
        return _prepare_campaign_outreach_drafts_db(campaign_id, payload)

    if not payload.product_category:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "PRODUCT_CATEGORY_REQUIRED",
                "message": "Provide product_category when USE_DATABASE=false.",
            },
        )

    items: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for snapshot in payload.candidate_snapshots:
        filter_failure = _candidate_filter_failure(
            snapshot.model_dump(),
            min_score=payload.min_score,
            max_risk_penalty=payload.max_risk_penalty,
        )
        if filter_failure is not None:
            skipped.append(filter_failure)
            continue
        prepared = _prepare_outreach_item(
            campaign_id=campaign_id,
            creator_id=snapshot.creator_id,
            creator=snapshot.model_dump(),
            product_category=payload.product_category,
            product_name=payload.product_name,
            dm_variant=payload.dm_variant,
            model_alias=payload.model_alias,
            persist=False,
        )
        if prepared["status"] == "skipped":
            skipped.append(prepared)
        else:
            items.append(prepared)

    return {
        "status": "validated_not_persisted",
        "campaign_id": campaign_id,
        "prepared_count": len(items),
        "skipped_count": len(skipped),
        "items": items,
        "skipped": skipped,
        "review_required": True,
        "review_required_reason": "operator_approval_required",
        "claims_check_policy": {
            "status": "needs_review",
            "send_allowed": False,
            "required_before_send": ["claims_check_passed", "human_approval"],
        },
    }


@router.get("/{campaign_id}/candidates")
def list_campaign_candidates(
    campaign_id: str,
    min_score: float = Query(default=70, ge=0, le=100),
    max_risk_penalty: float = Query(default=10, ge=0, le=30),
    segment: CreatorSegment | None = None,
    product_category: ProductCategory | None = None,
    exclude_existing_outreach: bool = True,
    limit: int = Query(default=50, ge=1, le=100),
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    filters = {
        "campaign_id": campaign_id,
        "min_score": min_score,
        "max_risk_penalty": max_risk_penalty,
        "segment": segment,
        "product_category": product_category,
        "exclude_existing_outreach": exclude_existing_outreach,
        "limit": limit,
    }

    if not database_enabled():
        return {
            "items": [],
            "next_cursor": None,
            "filters": filters,
        }

    campaign = campaign_repository.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "CAMPAIGN_NOT_FOUND",
                "message": "Campaign does not exist.",
            },
        )

    resolved_product_category = product_category or campaign["product_category"]
    rows = campaign_repository.list_campaign_candidates(
        campaign_id=campaign_id,
        country=campaign["country"],
        product_category=resolved_product_category,
        min_score=min_score,
        max_risk_penalty=max_risk_penalty,
        segment=segment,
        exclude_existing_outreach=exclude_existing_outreach,
        limit=limit,
    )
    return {
        "items": rank_candidate_rows(rows, limit=limit),
        "next_cursor": None,
        "campaign": campaign,
        "filters": {
            **filters,
            "country": campaign["country"],
            "product_category": resolved_product_category,
        },
    }


def _prepare_campaign_outreach_drafts_db(
    campaign_id: str,
    payload: CampaignOutreachDraftRequest,
) -> dict[str, Any]:
    campaign = campaign_repository.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "CAMPAIGN_NOT_FOUND",
                "message": "Campaign does not exist.",
            },
        )

    product_category = payload.product_category or campaign["product_category"]
    items: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for creator_id in payload.creator_ids:
        candidate = campaign_repository.get_campaign_candidate(
            campaign_id=campaign_id,
            creator_id=creator_id,
            country=campaign["country"],
            product_category=product_category,
            min_score=payload.min_score,
            max_risk_penalty=payload.max_risk_penalty,
            exclude_existing_outreach=payload.exclude_existing_outreach,
        )
        if candidate is None:
            skipped.append(
                {
                    "status": "skipped",
                    "creator_id": creator_id,
                    "code": "CAMPAIGN_CANDIDATE_NOT_ELIGIBLE",
                    "reason": "Creator is not eligible for this campaign candidate filter.",
                }
            )
            continue

        creator = {
            **candidate,
            "status": candidate.get("creator_status", "active"),
        }
        prepared = _prepare_outreach_item(
            campaign_id=campaign_id,
            creator_id=creator_id,
            creator=creator,
            product_category=product_category,
            product_name=payload.product_name,
            dm_variant=payload.dm_variant,
            model_alias=payload.model_alias,
            persist=True,
        )
        if prepared["status"] == "skipped":
            skipped.append(prepared)
        else:
            items.append(prepared)

    return {
        "status": "persisted",
        "campaign_id": campaign_id,
        "campaign": campaign,
        "prepared_count": len(items),
        "skipped_count": len(skipped),
        "items": items,
        "skipped": skipped,
        "review_required": True,
        "review_required_reason": "operator_approval_required",
        "claims_check_policy": {
            "status": "needs_review",
            "send_allowed": False,
            "required_before_send": ["claims_check_passed", "human_approval"],
        },
    }


def _candidate_filter_failure(
    creator: dict[str, Any],
    min_score: float,
    max_risk_penalty: float,
) -> dict[str, Any] | None:
    creator_id = creator.get("creator_id")
    final_score = creator.get("final_score")
    risk_penalty = creator.get("risk_penalty")
    if creator.get("segment") == "avoid":
        return {
            "status": "skipped",
            "creator_id": creator_id,
            "username": creator.get("username"),
            "code": "CAMPAIGN_CANDIDATE_NOT_ELIGIBLE",
            "reason": "avoid_segment",
        }
    if final_score is not None and float(final_score) < min_score:
        return {
            "status": "skipped",
            "creator_id": creator_id,
            "username": creator.get("username"),
            "code": "CAMPAIGN_CANDIDATE_NOT_ELIGIBLE",
            "reason": "below_min_score",
        }
    if risk_penalty is not None and float(risk_penalty) > max_risk_penalty:
        return {
            "status": "skipped",
            "creator_id": creator_id,
            "username": creator.get("username"),
            "code": "CAMPAIGN_CANDIDATE_NOT_ELIGIBLE",
            "reason": "risk_penalty_above_limit",
        }
    return None


def _prepare_outreach_item(
    campaign_id: str,
    creator_id: str,
    creator: dict[str, Any],
    product_category: str,
    product_name: str | None,
    dm_variant: str,
    model_alias: str,
    persist: bool,
) -> dict[str, Any]:
    try:
        require_dm_allowed(creator)
    except PolicyError as exc:
        return {
            "status": "skipped",
            "creator_id": creator_id,
            "username": creator.get("username"),
            "code": "DM_GENERATION_NOT_ALLOWED",
            "reason": str(exc),
        }

    drafts = build_dm_drafts(
        creator=creator,
        product_category=product_category,
        product_name=product_name,
    )
    selected = next(
        (draft for draft in drafts if draft["variant"] == dm_variant),
        drafts[0],
    )
    outreach = {
        "creator_id": creator_id,
        "campaign_id": campaign_id,
        "status": "dm_drafted",
        "dm_variant": selected["variant"],
        "dm_message": selected["message"],
        "claims_check_status": "needs_review",
    }
    if persist:
        outreach = outreach_repository.create_dm_draft(
            creator_id=creator_id,
            campaign_id=campaign_id,
            dm_variant=selected["variant"],
            dm_message=selected["message"],
        )

    final_score = creator.get("final_score")
    risk_penalty = creator.get("risk_penalty")
    priority = None
    if final_score is not None and risk_penalty is not None:
        priority = priority_label(
            final_score=float(final_score),
            risk_penalty=float(risk_penalty),
        )

    return {
        "status": "prepared",
        "creator_id": creator_id,
        "username": creator.get("username"),
        "display_name": creator.get("display_name"),
        "final_score": final_score,
        "risk_penalty": risk_penalty,
        "priority_label": priority,
        "outreach": outreach,
        "selected_draft": selected,
        "drafts": drafts,
        "claims_check_job": {
            "status": "queued" if persist else "validated_not_persisted",
            "job_type": "claims_check",
            "source_risk_level": creator.get("source_risk_level"),
        },
        "model_alias": model_alias,
        "review_required": True,
        "review_required_reason": "operator_approval_required",
    }
