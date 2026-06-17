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
from app.repositories import creators as creator_repository
from app.repositories import creator_analyses as creator_analysis_repository
from app.scoring.creator_score import CreatorScoreInput, calculate_creator_score


router = APIRouter(prefix="/creators", tags=["creators"])

Country = Literal["MX", "PE", "EC"]
SourceRisk = Literal["low", "low_medium", "medium"]


class CreatorImportItem(BaseModel):
    country: Country
    username: str = Field(min_length=1)
    profile_url: str = Field(min_length=1)
    display_name: str | None = None
    bio: str | None = None
    language: str = "es"
    follower_count: int | None = Field(default=None, ge=0)
    source_url: str | None = None


class CreatorImportRequest(BaseModel):
    source_type: str = Field(min_length=1)
    source_risk_level: str = Field(min_length=1)
    items: list[CreatorImportItem] = Field(min_length=1)


@router.get("")
def list_creators(
    country: Country | None = None,
    source_risk_level: SourceRisk | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    if database_enabled():
        items = creator_repository.list_creators(
            country=country,
            source_risk_level=source_risk_level,
            limit=limit,
        )
        return {
            "items": items,
            "next_cursor": None,
            "filters": {
                "country": country,
                "source_risk_level": source_risk_level,
                "limit": limit,
            },
        }

    return {
        "items": [],
        "next_cursor": None,
        "filters": {
            "country": country,
            "source_risk_level": source_risk_level,
            "limit": limit,
        },
    }


@router.get("/{creator_id}/analysis")
def list_creator_analysis(
    creator_id: str,
    limit: int = 20,
) -> dict[str, Any]:
    if database_enabled():
        items = creator_analysis_repository.list_creator_analyses(
            creator_id=creator_id,
            limit=limit,
        )
        return {
            "items": items,
            "next_cursor": None,
            "filters": {"creator_id": creator_id, "limit": limit},
        }

    return {
        "items": [],
        "next_cursor": None,
        "filters": {"creator_id": creator_id, "limit": limit},
    }


@router.post("/{creator_id}/score")
def calculate_creator_analysis_score(
    creator_id: str,
    payload: CreatorScoreInput,
    _user: UserContext = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    score = calculate_creator_score(payload)
    score_payload = score.model_dump()

    if database_enabled():
        persisted = creator_analysis_repository.upsert_creator_analysis(
            creator_id=creator_id,
            payload=score_payload,
        )
        return {
            "status": "persisted",
            "creator_id": creator_id,
            "score": persisted,
        }

    return {
        "status": "validated_not_persisted",
        "creator_id": creator_id,
        "score": score_payload,
    }


@router.post("/import")
def import_creators(
    payload: CreatorImportRequest,
    _user: UserContext = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    try:
        normalized_level = require_allowed_source_risk(payload.source_risk_level)
        normalized_source_type = require_allowed_collection_source_type(payload.source_type)
    except PolicyError as exc:
        reason = str(exc)
        code = (
            "SOURCE_RISK_NOT_ALLOWED"
            if reason in {"source_risk_not_allowed", "unknown_source_risk_level"}
            else "COLLECTION_SOURCE_TYPE_NOT_ALLOWED"
        )
        raise HTTPException(
            status_code=400,
            detail={
                "code": code,
                "message": "This import source is blocked in MVP v0.1.",
                "details": {"reason": reason},
            },
        ) from exc

    if database_enabled():
        imported = creator_repository.import_creators(
            source_type=normalized_source_type,
            source_risk_level=normalized_level,
            items=[item.model_dump() for item in payload.items],
        )
        return {
            "accepted": len(imported),
            "source_risk_level": normalized_level,
            "status": "persisted",
            "items": imported,
        }

    return {
        "accepted": len(payload.items),
        "source_type": normalized_source_type,
        "source_risk_level": normalized_level,
        "status": "validated_not_persisted",
    }
