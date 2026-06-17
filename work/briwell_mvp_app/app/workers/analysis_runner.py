import json
import time
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.ai.contracts import AnalysisRequest, AnalysisResult
from app.ai.gemini import GeminiTextAdapter
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
        live_provider_call=not adapter.dry_run,
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
