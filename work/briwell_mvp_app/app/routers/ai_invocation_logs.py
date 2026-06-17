from typing import Any, Literal

from fastapi import APIRouter, Depends

from app.core.auth import UserContext, require_roles
from app.core.db import database_enabled
from app.repositories import ai_invocation_logs as log_repository


router = APIRouter(prefix="/ai-invocation-logs", tags=["ai-invocation-logs"])

LogStatus = Literal["success", "failed", "skipped"]
TargetEntityType = Literal["creator", "video", "comment_sample", "outreach", "campaign", "other"]


@router.get("")
def list_ai_invocation_logs(
    analysis_job_id: str | None = None,
    target_entity_type: TargetEntityType | None = None,
    status: LogStatus | None = None,
    limit: int = 50,
    _user: UserContext = Depends(require_roles("admin")),
) -> dict[str, Any]:
    if database_enabled():
        items = log_repository.list_invocation_logs(
            analysis_job_id=analysis_job_id,
            target_entity_type=target_entity_type,
            status=status,
            limit=limit,
        )
        return {
            "items": items,
            "next_cursor": None,
            "filters": {
                "analysis_job_id": analysis_job_id,
                "target_entity_type": target_entity_type,
                "status": status,
                "limit": limit,
            },
        }

    return {
        "items": [],
        "next_cursor": None,
        "filters": {
            "analysis_job_id": analysis_job_id,
            "target_entity_type": target_entity_type,
            "status": status,
            "limit": limit,
        },
    }
