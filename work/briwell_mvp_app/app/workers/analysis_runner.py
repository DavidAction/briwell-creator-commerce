import json
import time
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.ai.contracts import AnalysisRequest, AnalysisResult
from app.ai.gemini import GeminiTextAdapter
from app.core.config import settings
from app.core.db import database_enabled
from app.repositories import ai_invocation_logs, analysis_jobs


TargetEntityType = Literal["creator", "video", "comment_sample", "outreach", "campaign", "other"]


class AnalysisRunRequest(BaseModel):
    analysis_job_id: str | None = None
    target_entity_type: TargetEntityType = "other"
    target_entity_id: str | None = None
    request: AnalysisRequest
    dry_run: bool | None = None
    allow_live_provider_calls: bool | None = None
    persist_log: bool = True
    mark_job_status: bool = True


class AnalysisRunResult(BaseModel):
    status: Literal["success", "failed", "skipped"]
    result: AnalysisResult
    invocation_log: dict[str, Any]
    persistence_status: Literal["persisted", "validated_not_persisted"]
    job_update: dict[str, Any] | None = None
    screen_persistence_status: Literal["persisted", "validated_not_persisted", "failed"] = "validated_not_persisted"
    persisted_screen_result: dict[str, Any] | None = None
    screen_persistence_error: str | None = None


def run_analysis(request: AnalysisRunRequest) -> AnalysisRunResult:
    live_provider_call = live_provider_call_requested(request)
    limit_error = live_analysis_limit_error(request) if live_provider_call else None
    if limit_error:
        result = AnalysisResult(
            status="error",
            model_alias=request.request.model_alias,
            prompt_version=request.request.prompt_version,
            output={"status": "error", "message": limit_error["message"]},
            confidence=0,
            review_required=True,
            review_required_reason=limit_error["message"],
            error_code=limit_error["code"],
        )
        log_payload = build_invocation_log_payload(
            run_request=request,
            result=result,
            latency_ms=0,
            live_provider_call=False,
        )
        return AnalysisRunResult(
            status="failed",
            result=result,
            invocation_log=log_payload,
            persistence_status="validated_not_persisted",
        )

    adapter = GeminiTextAdapter(
        dry_run=request.dry_run,
        allow_live_provider_calls=request.allow_live_provider_calls,
    )

    started = time.perf_counter()
    if database_enabled() and request.mark_job_status and request.analysis_job_id:
        analysis_jobs.mark_job_running(request.analysis_job_id)

    result = adapter.run(request.request)
    latency_ms = int((time.perf_counter() - started) * 1000)
    log_payload = build_invocation_log_payload(
        run_request=request,
        result=result,
        latency_ms=latency_ms,
        live_provider_call=live_provider_call,
    )
    run_status = log_payload["status"]
    job_update = None

    if database_enabled() and request.persist_log:
        log_payload = ai_invocation_logs.create_invocation_log(log_payload)
        if request.mark_job_status and request.analysis_job_id:
            if run_status == "success":
                job_update = analysis_jobs.mark_job_completed(
                    request.analysis_job_id,
                    success_count=1,
                    failed_count=0,
                    actual_cost_usd=log_payload.get("cost_usd"),
                )
            elif run_status == "skipped":
                job_update = analysis_jobs.mark_job_completed(
                    request.analysis_job_id,
                    success_count=0,
                    failed_count=0,
                    actual_cost_usd=log_payload.get("cost_usd"),
                )
            else:
                job_update = analysis_jobs.mark_job_failed(
                    request.analysis_job_id,
                    error_message=result.error_code or result.review_required_reason or "analysis_failed",
                    failed_count=1,
                )
        persistence_status = "persisted"
    else:
        persistence_status = "validated_not_persisted"

    return AnalysisRunResult(
        status=run_status,
        result=result,
        invocation_log=log_payload,
        persistence_status=persistence_status,
        job_update=job_update,
    )


def build_invocation_log_payload(
    run_request: AnalysisRunRequest,
    result: AnalysisResult,
    latency_ms: int,
    live_provider_call: bool = False,
) -> dict[str, Any]:
    input_token_count = estimate_tokens(run_request.request.model_dump())
    output_token_count = estimate_tokens(result.output)
    return {
        "analysis_job_id": run_request.analysis_job_id,
        "model_config_id": None,
        "target_entity_type": run_request.target_entity_type,
        "target_entity_id": run_request.target_entity_id,
        "prompt_version": run_request.request.prompt_version,
        "input_token_count": input_token_count,
        "output_token_count": output_token_count,
        "cost_usd": estimate_analysis_cost(
            model_alias=run_request.request.model_alias,
            input_token_count=input_token_count,
            output_token_count=output_token_count,
            live_provider_call=live_provider_call,
            result=result,
        ),
        "latency_ms": latency_ms,
        "status": status_for_result(result),
        "error_message": None if result.status == "ok" else result.error_code or result.review_required_reason,
        "model_alias": run_request.request.model_alias,
        "task_type": run_request.request.task_type,
    }


def status_for_result(result: AnalysisResult) -> Literal["success", "failed", "skipped"]:
    if result.status == "ok":
        return "success"
    if result.status == "rejected":
        return "skipped"
    return "failed"


def live_provider_call_requested(request: AnalysisRunRequest) -> bool:
    dry_run = settings.ai_dry_run if request.dry_run is None else request.dry_run
    allow_live = (
        settings.allow_live_provider_calls
        if request.allow_live_provider_calls is None
        else request.allow_live_provider_calls
    )
    return not dry_run and allow_live


def live_analysis_limit_error(request: AnalysisRunRequest) -> dict[str, str] | None:
    if settings.ai_dry_run and request.dry_run is False:
        return {
            "code": "live_ai_default_dry_run_enabled",
            "message": "Live AI calls require AI_DRY_RUN=false at server level.",
        }
    if settings.ai_live_require_database and not database_enabled():
        return {
            "code": "live_ai_database_required",
            "message": "Live AI calls require USE_DATABASE=true for cost and rate-limit tracking.",
        }
    if not database_enabled():
        return None

    daily = ai_invocation_logs.live_usage_summary()
    if settings.ai_live_daily_call_limit > 0 and daily["call_count"] >= settings.ai_live_daily_call_limit:
        return {
            "code": "live_ai_daily_call_limit_reached",
            "message": "Daily live AI call limit reached.",
        }
    if settings.ai_live_daily_cost_limit_usd > 0 and daily["cost_usd"] >= settings.ai_live_daily_cost_limit_usd:
        return {
            "code": "live_ai_daily_cost_limit_reached",
            "message": "Daily live AI cost limit reached.",
        }

    if (
        request.target_entity_type == "creator"
        and request.target_entity_id
        and _looks_like_uuid(request.target_entity_id)
        and settings.ai_live_per_creator_daily_call_limit > 0
    ):
        creator_daily = ai_invocation_logs.live_usage_summary(
            target_entity_type="creator",
            target_entity_id=request.target_entity_id,
        )
        if creator_daily["call_count"] >= settings.ai_live_per_creator_daily_call_limit:
            return {
                "code": "live_ai_creator_daily_call_limit_reached",
                "message": "Daily live AI call limit reached for this creator.",
            }
    return None


def _looks_like_uuid(value: str) -> bool:
    try:
        UUID(str(value))
    except (TypeError, ValueError):
        return False
    return True


def estimate_tokens(payload: Any) -> int:
    text = json.dumps(payload, ensure_ascii=True, default=str)
    return max(1, (len(text) + 3) // 4)


def estimate_dry_run_cost(result: AnalysisResult) -> float:
    if result.status == "ok":
        return 0.0
    return 0.0


GEMINI_ALIAS_COST_PER_1M_TOKENS = {
    # MVP planning estimates only. Reconcile with provider billing exports before production finance reporting.
    "low_cost_text": {"input": 0.10, "output": 0.40},
    "recent_posts_screen": {"input": 0.10, "output": 0.40},
    "dm_generation": {"input": 0.30, "output": 2.50},
    "multimodal_default": {"input": 0.30, "output": 2.50},
    "final_review": {"input": 0.30, "output": 2.50},
}


def estimate_analysis_cost(
    model_alias: str,
    input_token_count: int,
    output_token_count: int,
    live_provider_call: bool,
    result: AnalysisResult,
) -> float:
    if not live_provider_call or result.status != "ok":
        return 0.0
    pricing = GEMINI_ALIAS_COST_PER_1M_TOKENS.get(
        model_alias,
        GEMINI_ALIAS_COST_PER_1M_TOKENS["low_cost_text"],
    )
    return round(
        input_token_count / 1_000_000 * pricing["input"]
        + output_token_count / 1_000_000 * pricing["output"],
        6,
    )
