from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.ai.contracts import AnalysisRequest
from app.ai.gemini import GeminiTextAdapter
from app.ai.schema_validation import AnalysisSchemaError, validate_analysis_output
from app.core.auth import UserContext, require_roles
from app.core.config import settings


router = APIRouter(prefix="/ai", tags=["ai"])

AnalysisTask = Literal[
    "profile_analysis",
    "comment_analysis",
    "multimodal_analysis",
    "final_review",
    "creator_score",
]


class ValidateAnalysisOutputRequest(BaseModel):
    task_type: AnalysisTask
    output: dict[str, Any] = Field(default_factory=dict)


@router.post("/validate-output")
def validate_output(
    payload: ValidateAnalysisOutputRequest,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    try:
        validated = validate_analysis_output(payload.task_type, payload.output)
    except AnalysisSchemaError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "AI_SCHEMA_INVALID",
                "message": "AI output failed schema validation.",
                "details": {"reason": str(exc)},
            },
        ) from exc

    return {
        "status": "validated",
        "task_type": payload.task_type,
        "output": validated.model_dump(),
    }


@router.post("/dry-run")
def dry_run_analysis(
    payload: AnalysisRequest,
    _user: UserContext = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    adapter = GeminiTextAdapter(dry_run=True)
    result = adapter.run(payload)
    return result.model_dump()


@router.get("/provider-status")
def provider_status(
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    return {
        "provider": "google",
        "default_adapter": "GeminiTextAdapter",
        "dry_run_default": settings.ai_dry_run,
        "live_provider_calls_allowed": settings.allow_live_provider_calls,
        "api_key_configured": bool(settings.gemini_api_key),
        "live_ready": (
            not settings.ai_dry_run
            and settings.allow_live_provider_calls
            and bool(settings.gemini_api_key)
        ),
        "safety_note": "Live calls require AI_DRY_RUN=false, ALLOW_LIVE_PROVIDER_CALLS=true, and GEMINI_API_KEY.",
    }
