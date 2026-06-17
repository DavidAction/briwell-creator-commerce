from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import UserContext, require_roles
from app.core.db import database_enabled
from app.core.policy import (
    PolicyError,
    require_allowed_collection_source_type,
    require_allowed_source_risk,
)
from app.operations.workflows import (
    apply_recent_screen_results,
    build_outreach_crm_board,
    build_outreach_plan,
    enrich_creator_profiles,
    evaluate_import_quality,
    match_campaign_candidates,
    rollup_performance,
)
from app.repositories import campaigns as campaign_repository
from app.repositories import operations as operations_repository
from app.repositories import outreach as outreach_repository
from app.repositories import performance as performance_repository


router = APIRouter(prefix="/operations", tags=["operations"])

Country = Literal["MX", "PE", "EC"]
ProductCategory = Literal[
    "sunscreen",
    "calming_serum",
    "cleanser",
    "sheet_mask",
    "cushion_foundation",
]
DatasetType = Literal["creator_candidates", "recent_posts", "mixed"]
DmVariant = Literal["soft_intro", "product_review", "ugc_collaboration", "commerce_collaboration"]


class CreatorCandidate(BaseModel):
    creator_id: str | None = None
    country: Country
    username: str = Field(min_length=1)
    profile_url: str = Field(min_length=1)
    source_risk_level: str = Field(min_length=1)
    display_name: str | None = None
    bio: str | None = None
    language: str = "es"
    platform: str = "tiktok"
    follower_count: int | None = Field(default=None, ge=0)
    avg_views: int | None = Field(default=None, ge=0)
    engagement_rate: float | None = Field(default=None, ge=0)
    contact_email: str | None = None
    instagram_url: str | None = None
    status: str = "active"
    final_score: float | None = Field(default=None, ge=0, le=100)
    risk_penalty: float | None = Field(default=None, ge=0, le=30)
    segment: str | None = None
    signals: list[str] = Field(default_factory=list, max_length=20)
    recommended_products: list[ProductCategory] = Field(default_factory=list, max_length=5)
    recommended_campaign_angle: str | None = None


class RecentPostInput(BaseModel):
    url: str | None = None
    platform_video_id: str | None = None
    caption: str | None = None
    transcript: str | None = None
    hashtags: list[str] = Field(default_factory=list, max_length=30)
    view_count: int | None = Field(default=None, ge=0)
    like_count: int | None = Field(default=None, ge=0)
    comment_count: int | None = Field(default=None, ge=0)
    share_count: int | None = Field(default=None, ge=0)


class ImportQualityLogRequest(BaseModel):
    dataset_type: DatasetType = "mixed"
    upload_name: str | None = Field(default=None, max_length=200)
    source_type: str = Field(min_length=1)
    source_risk_level: str = Field(min_length=1)
    expected_countries: list[Country] = Field(default_factory=lambda: ["MX", "PE", "EC"], max_length=3)
    creator_candidates: list[CreatorCandidate] = Field(default_factory=list, max_length=200)
    recent_posts_by_creator: dict[str, list[RecentPostInput]] = Field(default_factory=dict)
    quality_gate: dict[str, Any] | None = None


class CreatorEnrichmentRequest(BaseModel):
    source_risk_level: str = Field(min_length=1)
    creators: list[CreatorCandidate] = Field(min_length=1, max_length=200)
    persist_result: bool = True


class RecentScreenApplyItem(BaseModel):
    creator_id: str = Field(min_length=1)
    creator_snapshot: dict[str, Any] = Field(default_factory=dict)
    screen_result: dict[str, Any] = Field(default_factory=dict)


class RecentScreenApplyRequest(BaseModel):
    source_risk_level: str = Field(min_length=1)
    items: list[RecentScreenApplyItem] = Field(min_length=1, max_length=200)
    persist_result: bool = True


class CampaignMatchRequest(BaseModel):
    campaign_id: str | None = None
    country: Country | None = None
    product_category: ProductCategory
    campaign_goal: str | None = None
    candidates: list[CreatorCandidate] = Field(default_factory=list, max_length=200)
    recent_screen_results: dict[str, dict[str, Any]] = Field(default_factory=dict)
    min_score: float = Field(default=70, ge=0, le=100)
    max_risk_penalty: float = Field(default=10, ge=0, le=30)
    limit: int = Field(default=50, ge=1, le=100)


class OutreachPlanRequest(BaseModel):
    campaign_id: str | None = None
    product_category: ProductCategory
    product_name: str | None = None
    dm_variant: DmVariant = "product_review"
    candidates: list[dict[str, Any]] = Field(min_length=1, max_length=50)
    persist_result: bool = False


class OutreachCrmBoardRequest(BaseModel):
    campaign_id: str | None = None
    outreach_items: list[dict[str, Any]] = Field(default_factory=list, max_length=200)
    persist_event: bool = False


class PerformanceRollupRequest(BaseModel):
    campaign_id: str | None = None
    spend_usd: float | None = Field(default=None, ge=0)
    snapshots: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
    include_db_summary: bool = True


@router.post("/import-quality-logs")
def create_import_quality_log(
    payload: ImportQualityLogRequest,
    user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    source_type, source_risk_level = _normalize_source(payload.source_type, payload.source_risk_level)
    creators = [item.model_dump() for item in payload.creator_candidates]
    posts = {
        key: [post.model_dump() for post in value]
        for key, value in payload.recent_posts_by_creator.items()
    }
    quality_gate = payload.quality_gate or evaluate_import_quality(
        creators,
        posts,
        expected_countries=payload.expected_countries,
    )
    normalized_payload = payload.model_dump()
    normalized_payload["source_type"] = source_type
    normalized_payload["source_risk_level"] = source_risk_level

    persisted = None
    persistence_status = "validated_not_persisted"
    if database_enabled():
        persisted = operations_repository.create_import_quality_log(
            normalized_payload,
            quality_gate=quality_gate,
            user_email=user.email,
        )
        persistence_status = "persisted"

    return {
        "status": "logged",
        "persistence_status": persistence_status,
        "quality_gate": quality_gate,
        "import_log": persisted,
        "next_action": _quality_next_action(quality_gate),
    }


@router.post("/creator-enrichment")
def run_creator_enrichment(
    payload: CreatorEnrichmentRequest,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    source_risk_level = _normalize_risk(payload.source_risk_level)
    enriched = enrich_creator_profiles([item.model_dump() for item in payload.creators])
    persisted: list[dict[str, Any]] = []
    if database_enabled() and payload.persist_result:
        for item in enriched:
            _require_db_uuid(item.get("creator_id"), "creator_id")
            persisted.append(
                operations_repository.upsert_creator_profile_enrichment(
                    item,
                    source_risk_level=source_risk_level,
                )
            )
    return {
        "status": "enriched",
        "persistence_status": "persisted" if persisted else "validated_not_persisted",
        "items": enriched,
        "persisted": persisted,
        "summary": {
            "ready": sum(1 for item in enriched if item["enrichment_status"] == "ready"),
            "needs_review": sum(1 for item in enriched if item["enrichment_status"] == "needs_review"),
            "blocked": sum(1 for item in enriched if item["enrichment_status"] == "blocked"),
        },
    }


@router.post("/recent-posts/apply")
def apply_recent_posts_screening(
    payload: RecentScreenApplyRequest,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    source_risk_level = _normalize_risk(payload.source_risk_level)
    items = [item.model_dump() for item in payload.items]
    applied = apply_recent_screen_results(items)
    persisted: list[dict[str, Any]] = []
    if database_enabled() and payload.persist_result:
        for item in items:
            _require_db_uuid(item.get("creator_id"), "creator_id")
            persisted.append(
                operations_repository.create_recent_posts_screen_result(
                    item,
                    source_risk_level=source_risk_level,
                )
            )
    return {
        "status": "applied",
        "persistence_status": "persisted" if persisted else "validated_not_persisted",
        "items": applied,
        "persisted": persisted,
        "queue_counts": _count_by(applied, "queue"),
    }


@router.post("/campaign-match")
def run_campaign_match(
    payload: CampaignMatchRequest,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    campaign = None
    candidates = [item.model_dump() for item in payload.candidates]
    country = payload.country
    product_category = payload.product_category

    if database_enabled() and payload.campaign_id and not candidates:
        _require_db_uuid(payload.campaign_id, "campaign_id")
        campaign = campaign_repository.get_campaign(payload.campaign_id)
        if campaign is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "CAMPAIGN_NOT_FOUND", "message": "Campaign does not exist."},
            )
        country = campaign["country"]
        product_category = campaign["product_category"]
        candidates = campaign_repository.list_campaign_candidates(
            campaign_id=payload.campaign_id,
            country=country,
            product_category=product_category,
            min_score=payload.min_score,
            max_risk_penalty=payload.max_risk_penalty,
            limit=payload.limit,
        )

    ranked = match_campaign_candidates(
        candidates,
        product_category=product_category,
        country=country,
        recent_screen_results=payload.recent_screen_results,
        min_score=payload.min_score,
        max_risk_penalty=payload.max_risk_penalty,
        limit=payload.limit,
    )
    return {
        "status": "matched",
        "campaign": campaign,
        "items": ranked,
        "summary": {
            "matched_count": len(ranked),
            "priority_outreach": sum(1 for item in ranked if item["priority_label"] == "priority_outreach"),
            "human_review": sum(1 for item in ranked if item["priority_label"] == "human_review"),
        },
        "filters": payload.model_dump(exclude={"candidates", "recent_screen_results"}),
    }


@router.post("/outreach-plan")
def create_outreach_plan(
    payload: OutreachPlanRequest,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    plan = build_outreach_plan(
        payload.candidates,
        product_category=payload.product_category,
        product_name=payload.product_name,
        dm_variant=payload.dm_variant,
    )
    persisted: list[dict[str, Any]] = []
    if database_enabled() and payload.persist_result:
        if payload.campaign_id:
            _require_db_uuid(payload.campaign_id, "campaign_id")
        for item in plan:
            _require_db_uuid(item.get("creator_id"), "creator_id")
            persisted.append(
                outreach_repository.create_dm_draft(
                    creator_id=str(item["creator_id"]),
                    campaign_id=payload.campaign_id,
                    dm_variant=item["dm_variant"],
                    dm_message=item["dm_message"],
                )
            )
    return {
        "status": "planned",
        "persistence_status": "persisted" if persisted else "validated_not_persisted",
        "items": plan,
        "persisted": persisted,
        "send_policy": {
            "auto_send_enabled": False,
            "required_before_send": ["claims_check_passed", "human_approval", "manual_send_confirmed"],
        },
    }


@router.post("/outreach-crm/board")
def build_crm_board(
    payload: OutreachCrmBoardRequest,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    board = build_outreach_crm_board(payload.outreach_items)
    persisted: list[dict[str, Any]] = []
    if database_enabled() and payload.persist_event:
        for item in payload.outreach_items:
            _require_optional_db_uuid(item.get("outreach_id"), "outreach_id")
            _require_optional_db_uuid(item.get("creator_id"), "creator_id")
            _require_optional_db_uuid(item.get("campaign_id"), "campaign_id")
            persisted.append(operations_repository.create_outreach_crm_event(item))
    return {
        "status": "ok",
        "persistence_status": "persisted" if persisted else "validated_not_persisted",
        "board": board,
        "persisted": persisted,
    }


@router.post("/performance-rollup")
def create_performance_rollup(
    payload: PerformanceRollupRequest,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    rollup = rollup_performance(payload.snapshots, spend_usd=payload.spend_usd)
    db_summary = None
    if database_enabled() and payload.campaign_id and payload.include_db_summary:
        _require_db_uuid(payload.campaign_id, "campaign_id")
        db_summary = performance_repository.campaign_summary(payload.campaign_id)
    return {
        "status": "ok",
        "rollup": rollup,
        "db_summary": db_summary,
        "measurement_policy": {
            "required_keys": ["post_url", "tracking_url", "coupon_code", "view_count", "revenue_usd"],
            "allowed_sources": ["manual", "official_api", "approved_provider", "creator_provided"],
        },
    }


def _normalize_source(source_type: str, source_risk_level: str) -> tuple[str, str]:
    try:
        return (
            require_allowed_collection_source_type(source_type),
            require_allowed_source_risk(source_risk_level),
        )
    except PolicyError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "OPERATIONS_SOURCE_NOT_ALLOWED",
                "message": "This operations source is blocked in MVP v0.1.",
                "details": {"reason": str(exc)},
            },
        ) from exc


def _normalize_risk(source_risk_level: str) -> str:
    try:
        return require_allowed_source_risk(source_risk_level)
    except PolicyError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "SOURCE_RISK_NOT_ALLOWED",
                "message": "High Risk and Not Allowed operations are blocked in MVP v0.1.",
                "details": {"reason": str(exc)},
            },
        ) from exc


def _quality_next_action(quality_gate: dict[str, Any]) -> str:
    status = quality_gate.get("overall_status")
    if status == "ready":
        return "run_creator_enrichment"
    if status == "needs_review":
        return "operator_review_then_enrichment"
    return "fix_import_blockers"


def _require_optional_db_uuid(value: Any, field_name: str) -> None:
    if value is None or value == "":
        return
    _require_db_uuid(value, field_name)


def _require_db_uuid(value: Any, field_name: str) -> None:
    try:
        UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "DB_UUID_REQUIRED",
                "message": f"{field_name} must be a UUID when database persistence is enabled.",
                "details": {"field": field_name, "value": value},
            },
        ) from exc


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts
