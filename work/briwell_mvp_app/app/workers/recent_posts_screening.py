from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.ai.contracts import AnalysisRequest
from app.core.db import database_enabled
from app.repositories import operations as operations_repository
from app.workers.analysis_runner import AnalysisRunRequest
from app.workers.analysis_runner import AnalysisRunResult
from app.workers.analysis_runner import run_analysis


SourceRisk = Literal["low", "low_medium", "medium", "high", "not_allowed"]


class RecentPostSnapshot(BaseModel):
    video_id: str | None = None
    url: str | None = Field(default=None, max_length=2000)
    caption: str | None = Field(default=None, max_length=3000)
    transcript: str | None = Field(default=None, max_length=10000)
    hashtags: list[str] = Field(default_factory=list, max_length=30)
    posted_at: datetime | None = None
    view_count: int | None = Field(default=None, ge=0)
    like_count: int | None = Field(default=None, ge=0)
    comment_count: int | None = Field(default=None, ge=0)
    share_count: int | None = Field(default=None, ge=0)
    save_count: int | None = Field(default=None, ge=0)
    duration_seconds: int | None = Field(default=None, ge=0)
    thumbnail_url: str | None = Field(default=None, max_length=2000)


class RecentPostsScreenRequest(BaseModel):
    creator_id: str = Field(min_length=1)
    source_risk_level: SourceRisk
    recent_posts: list[RecentPostSnapshot] = Field(min_length=1, max_length=20)
    expected_post_count: int = Field(default=20, ge=1, le=20)
    creator_snapshot: dict[str, Any] = Field(default_factory=dict)
    product_context: dict[str, Any] = Field(default_factory=dict)
    model_alias: str = "recent_posts_screen"
    prompt_version: str = "recent_posts_screen_v0"
    dry_run: bool | None = None
    allow_live_provider_calls: bool | None = None
    persist_result: bool = False

    @model_validator(mode="after")
    def expected_count_must_cover_provided_posts(self) -> "RecentPostsScreenRequest":
        if len(self.recent_posts) > self.expected_post_count:
            raise ValueError("expected_post_count cannot be lower than provided recent_posts count")
        return self


def run_recent_posts_screen(payload: RecentPostsScreenRequest) -> AnalysisRunResult:
    posts = sorted(
        payload.recent_posts,
        key=lambda item: item.posted_at or datetime.min,
        reverse=True,
    )[:20]
    result = run_analysis(
        AnalysisRunRequest(
            target_entity_type="creator",
            target_entity_id=payload.creator_id,
            dry_run=payload.dry_run,
            allow_live_provider_calls=payload.allow_live_provider_calls,
            request=AnalysisRequest(
                task_type="recent_posts_screen",
                model_alias=payload.model_alias,
                source_risk_level=payload.source_risk_level,
                prompt_version=payload.prompt_version,
                payload={
                    "creator_id": payload.creator_id,
                    "creator": payload.creator_snapshot,
                    "recent_posts": [item.model_dump() for item in posts],
                    "expected_post_count": payload.expected_post_count,
                    "product_context": payload.product_context,
                    "screening_policy": {
                        "required_recent_post_count": 20,
                        "purpose": "first_pass_creator_fit_screen",
                        "next_full_analysis": [
                            "profile_analysis",
                            "comment_analysis",
                            "multimodal_analysis",
                            "creator_score",
                        ],
                    },
                },
            ),
        )
    )
    if not payload.persist_result or not database_enabled():
        return result
    if result.status != "success":
        return result.model_copy(
            update={
                "screen_persistence_status": "failed",
                "screen_persistence_error": result.result.error_code or result.result.review_required_reason or "analysis_failed",
            }
        )
    if not _looks_like_uuid(payload.creator_id):
        return result.model_copy(
            update={
                "screen_persistence_status": "failed",
                "screen_persistence_error": "creator_id_must_be_uuid_for_db_persistence",
            }
        )
    persisted = operations_repository.create_recent_posts_screen_result(
        {
            "creator_id": payload.creator_id,
            "creator_snapshot": payload.creator_snapshot,
            "screen_result": result.result.output,
        },
        source_risk_level=payload.source_risk_level,
    )
    return result.model_copy(
        update={
            "screen_persistence_status": "persisted",
            "persisted_screen_result": persisted,
        }
    )


def _looks_like_uuid(value: str) -> bool:
    try:
        UUID(str(value))
    except (TypeError, ValueError):
        return False
    return True
