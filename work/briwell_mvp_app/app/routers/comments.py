from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import UserContext, require_roles
from app.core.db import database_enabled
from app.core.policy import PolicyError, require_allowed_source_risk
from app.repositories import comments as comment_repository


router = APIRouter(prefix="/comments", tags=["comments"])

SourceRisk = Literal["low", "low_medium", "medium"]
SampleMethod = Literal["manual", "official_api", "approved_provider", "creator_provided"]
Sentiment = Literal["positive", "neutral", "negative", "mixed"]
QuestionType = Literal["where_to_buy", "price", "skin_concern", "usage", "other"]


class CommentImportItem(BaseModel):
    comment_text: str = Field(min_length=1, max_length=1000)
    comment_language: str = "es"
    like_count: int | None = Field(default=None, ge=0)
    reply_count: int | None = Field(default=None, ge=0)
    sentiment: Sentiment | None = None
    purchase_intent: bool | None = None
    question_type: QuestionType | None = None
    contains_sensitive_data: bool = False


class CommentImportRequest(BaseModel):
    video_id: str = Field(min_length=1)
    sample_method: SampleMethod
    source_risk_level: str = Field(min_length=1)
    items: list[CommentImportItem] = Field(min_length=1, max_length=50)


@router.get("")
def list_comment_samples(
    video_id: str | None = None,
    source_risk_level: SourceRisk | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    if database_enabled():
        items = comment_repository.list_comment_samples(
            video_id=video_id,
            source_risk_level=source_risk_level,
            limit=limit,
        )
        return {
            "items": items,
            "next_cursor": None,
            "filters": {
                "video_id": video_id,
                "source_risk_level": source_risk_level,
                "limit": limit,
            },
        }

    return {
        "items": [],
        "next_cursor": None,
        "filters": {
            "video_id": video_id,
            "source_risk_level": source_risk_level,
            "limit": limit,
        },
    }


@router.post("/import")
def import_comment_samples(
    payload: CommentImportRequest,
    _user: UserContext = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    try:
        normalized_level = require_allowed_source_risk(payload.source_risk_level)
    except PolicyError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "SOURCE_RISK_NOT_ALLOWED",
                "message": "High Risk and Not Allowed comment samples are blocked in MVP v0.1.",
                "details": {"reason": str(exc)},
            },
        ) from exc

    sensitive_count = sum(1 for item in payload.items if item.contains_sensitive_data)
    if sensitive_count > 0:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "SENSITIVE_COMMENT_DATA_NOT_ALLOWED",
                "message": "Comment samples containing sensitive data are blocked in MVP v0.1.",
                "details": {"sensitive_count": sensitive_count},
            },
        )

    items = [item.model_dump() for item in payload.items]
    if database_enabled():
        imported = comment_repository.import_comment_samples(
            video_id=payload.video_id,
            sample_method=payload.sample_method,
            source_risk_level=normalized_level,
            items=items,
        )
        return {
            "accepted": len(imported),
            "sample_method": payload.sample_method,
            "source_risk_level": normalized_level,
            "status": "persisted",
            "items": imported,
        }

    return {
        "accepted": len(payload.items),
        "video_id": payload.video_id,
        "sample_method": payload.sample_method,
        "source_risk_level": normalized_level,
        "status": "validated_not_persisted",
    }
