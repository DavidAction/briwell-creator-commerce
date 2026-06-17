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
from app.repositories import videos as video_repository


router = APIRouter(prefix="/videos", tags=["videos"])

SourceRisk = Literal["low", "low_medium", "medium"]


class VideoImportItem(BaseModel):
    url: str = Field(min_length=1)
    platform_video_id: str | None = None
    caption: str | None = None
    hashtags: list[str] = Field(default_factory=list, max_length=30)
    posted_at: datetime | None = None
    view_count: int | None = Field(default=None, ge=0)
    like_count: int | None = Field(default=None, ge=0)
    comment_count: int | None = Field(default=None, ge=0)
    share_count: int | None = Field(default=None, ge=0)
    save_count: int | None = Field(default=None, ge=0)
    duration_seconds: int | None = Field(default=None, ge=0)
    thumbnail_url: str | None = None
    transcript: str | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)
    source_url: str | None = None


class VideoImportRequest(BaseModel):
    creator_id: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_risk_level: str = Field(min_length=1)
    items: list[VideoImportItem] = Field(min_length=1, max_length=50)


@router.get("")
def list_videos(
    creator_id: str | None = None,
    source_risk_level: SourceRisk | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    if database_enabled():
        items = video_repository.list_videos(
            creator_id=creator_id,
            source_risk_level=source_risk_level,
            limit=limit,
        )
        return {
            "items": items,
            "next_cursor": None,
            "filters": {
                "creator_id": creator_id,
                "source_risk_level": source_risk_level,
                "limit": limit,
            },
        }

    return {
        "items": [],
        "next_cursor": None,
        "filters": {
            "creator_id": creator_id,
            "source_risk_level": source_risk_level,
            "limit": limit,
        },
    }


@router.post("/import")
def import_videos(
    payload: VideoImportRequest,
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
                "message": "This video import source is blocked in MVP v0.1.",
                "details": {"reason": reason},
            },
        ) from exc

    items = [item.model_dump() for item in payload.items]
    if database_enabled():
        imported = video_repository.import_videos(
            creator_id=payload.creator_id,
            source_type=normalized_source_type,
            source_risk_level=normalized_level,
            items=items,
        )
        return {
            "accepted": len(imported),
            "source_type": normalized_source_type,
            "source_risk_level": normalized_level,
            "status": "persisted",
            "items": imported,
        }

    return {
        "accepted": len(payload.items),
        "creator_id": payload.creator_id,
        "source_type": normalized_source_type,
        "source_risk_level": normalized_level,
        "status": "validated_not_persisted",
    }
