from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import UserContext, require_roles
from app.core.db import database_enabled
from app.core.policy import (
    PolicyError,
    require_allowed_source_risk,
    requires_admin_approval,
)
from app.repositories import analysis_jobs as analysis_job_repository
from app.workers.scoring_handoff import (
    CreatorScoringHandoffRequest,
    run_creator_scoring_handoff,
)
from app.workers.analysis_runner import AnalysisRunRequest, run_analysis
from app.workers.multimodal_analysis import (
    MultimodalAnalysisRequest,
    run_multimodal_analysis,
)
from app.workers.recent_posts_screening import (
    RecentPostsScreenRequest,
    run_recent_posts_screen,
)


router = APIRouter(prefix="/analysis-jobs", tags=["analysis-jobs"])

JobType = Literal[
    "profile_analysis",
    "comment_analysis",
    "transcription",
    "multimodal_analysis",
    "recent_posts_screen",
    "final_review",
    "dm_generation",
    "claims_check",
    "keyword_import",
    "csv_import",
]
JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
SourceRisk = Literal["low", "low_medium", "medium"]
TargetEntityType = Literal["creator", "video", "comment_sample", "outreach", "campaign", "other"]


class AnalysisJobCreateRequest(BaseModel):
    job_type: JobType
    source_risk_level: str = Field(min_length=1)
    target_entity_type: TargetEntityType
    target_entity_ids: list[str] = Field(min_length=1, max_length=100)
    model_alias: str = Field(min_length=1)
    estimated_cost_usd: float | None = Field(default=None, ge=0)


@router.get("")
def list_analysis_jobs(
    job_type: JobType | None = None,
    status: JobStatus | None = None,
    source_risk_level: SourceRisk | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    if database_enabled():
        items = analysis_job_repository.list_analysis_jobs(
            job_type=job_type,
            status=status,
            source_risk_level=source_risk_level,
            limit=limit,
        )
        return {
            "items": items,
            "next_cursor": None,
            "filters": {
                "job_type": job_type,
                "status": status,
                "source_risk_level": source_risk_level,
                "limit": limit,
            },
        }

    return {
        "items": [],
        "next_cursor": None,
        "filters": {
            "job_type": job_type,
            "status": status,
            "source_risk_level": source_risk_level,
            "limit": limit,
        },
    }


@router.post("")
def create_analysis_job(
    payload: AnalysisJobCreateRequest,
    user: UserContext = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    try:
        normalized_level = require_allowed_source_risk(payload.source_risk_level)
    except PolicyError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "SOURCE_RISK_NOT_ALLOWED",
                "message": "High Risk and Not Allowed analysis jobs are blocked in MVP v0.1.",
                "details": {"reason": str(exc)},
            },
        ) from exc

    approval_required = requires_admin_approval(normalized_level)
    if approval_required and user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ADMIN_APPROVAL_REQUIRED",
                "message": "Low/Medium and Medium risk analysis jobs require admin approval.",
                "details": {"source_risk_level": normalized_level},
            },
        )

    normalized_payload = payload.model_dump()
    normalized_payload["source_risk_level"] = normalized_level

    if database_enabled():
        created = analysis_job_repository.create_analysis_job(
            normalized_payload,
            approval_required=approval_required,
        )
        return {
            "status": "persisted",
            "analysis_job": created,
            "target_entity_type": payload.target_entity_type,
            "target_entity_ids": payload.target_entity_ids,
            "model_alias": payload.model_alias,
        }

    return {
        "status": "validated_not_persisted",
        "analysis_job": {
            "job_type": payload.job_type,
            "status": "queued",
            "source_risk_level": normalized_level,
            "approval_required": approval_required,
            "input_count": len(payload.target_entity_ids),
            "estimated_cost_usd": payload.estimated_cost_usd,
        },
        "target_entity_type": payload.target_entity_type,
        "target_entity_ids": payload.target_entity_ids,
        "model_alias": payload.model_alias,
    }


@router.post("/run-dry-run")
def run_analysis_job_dry_run(
    payload: AnalysisRunRequest,
    _user: UserContext = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    result = run_analysis(payload)
    return result.model_dump()


@router.post("/run-multimodal")
def run_multimodal_analysis_job(
    payload: MultimodalAnalysisRequest,
    _user: UserContext = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    result = run_multimodal_analysis(payload)
    return result.model_dump()


@router.post("/run-recent-posts-screen")
def run_recent_posts_screen_job(
    payload: RecentPostsScreenRequest,
    _user: UserContext = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    result = run_recent_posts_screen(payload)
    return result.model_dump()


@router.post("/run-creator-score-handoff")
def run_creator_score_handoff(
    payload: CreatorScoringHandoffRequest,
    user: UserContext = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    try:
        normalized_level = require_allowed_source_risk(payload.source_risk_level)
    except PolicyError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "SOURCE_RISK_NOT_ALLOWED",
                "message": "High Risk and Not Allowed scoring handoff is blocked in MVP v0.1.",
                "details": {"reason": str(exc)},
            },
        ) from exc

    if requires_admin_approval(normalized_level) and user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ADMIN_APPROVAL_REQUIRED",
                "message": "Low/Medium and Medium risk scoring handoff requires admin approval.",
                "details": {"source_risk_level": normalized_level},
            },
        )

    result = run_creator_scoring_handoff(payload)
    return result.model_dump()
