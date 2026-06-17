from typing import Any

from app.core.db import fetch_all, fetch_one


def list_analysis_jobs(
    job_type: str | None = None,
    status: str | None = None,
    source_risk_level: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": min(limit, 100)}
    filters = ["source_risk_level IN ('low', 'low_medium', 'medium')"]
    if job_type:
        filters.append("job_type = %(job_type)s")
        params["job_type"] = job_type
    if status:
        filters.append("status = %(status)s")
        params["status"] = status
    if source_risk_level:
        filters.append("source_risk_level = %(source_risk_level)s")
        params["source_risk_level"] = source_risk_level

    query = f"""
        SELECT
          id,
          job_type,
          status,
          source_risk_level,
          approval_required,
          input_count,
          success_count,
          failed_count,
          estimated_cost_usd,
          actual_cost_usd,
          created_at,
          updated_at
        FROM analysis_job
        WHERE {' AND '.join(filters)}
        ORDER BY created_at DESC
        LIMIT %(limit)s
    """
    return fetch_all(query, params)


def create_analysis_job(payload: dict[str, Any], approval_required: bool) -> dict[str, Any]:
    query = """
        INSERT INTO analysis_job (
          job_type,
          status,
          source_risk_level,
          approval_required,
          input_count,
          estimated_cost_usd
        ) VALUES (
          %(job_type)s,
          'queued',
          %(source_risk_level)s,
          %(approval_required)s,
          %(input_count)s,
          %(estimated_cost_usd)s
        )
        RETURNING
          id,
          job_type,
          status,
          source_risk_level,
          approval_required,
          input_count,
          estimated_cost_usd,
          created_at
    """
    created = fetch_one(
        query,
        {
            "job_type": payload["job_type"],
            "source_risk_level": payload["source_risk_level"],
            "approval_required": approval_required,
            "input_count": len(payload["target_entity_ids"]),
            "estimated_cost_usd": payload.get("estimated_cost_usd"),
        },
    )
    if created is None:
        raise RuntimeError("Analysis job insert did not return a row.")
    return created


def mark_job_running(analysis_job_id: str) -> dict[str, Any]:
    query = """
        UPDATE analysis_job
        SET
          status = 'running',
          started_at = COALESCE(started_at, now()),
          updated_at = now()
        WHERE id = %(analysis_job_id)s
        RETURNING id, job_type, status, source_risk_level, started_at, updated_at
    """
    updated = fetch_one(query, {"analysis_job_id": analysis_job_id})
    if updated is None:
        raise RuntimeError("Analysis job update did not return a row.")
    return updated


def mark_job_completed(
    analysis_job_id: str,
    success_count: int,
    failed_count: int,
    actual_cost_usd: float | None = None,
) -> dict[str, Any]:
    query = """
        UPDATE analysis_job
        SET
          status = 'completed',
          completed_at = now(),
          success_count = %(success_count)s,
          failed_count = %(failed_count)s,
          actual_cost_usd = %(actual_cost_usd)s,
          updated_at = now()
        WHERE id = %(analysis_job_id)s
        RETURNING
          id,
          job_type,
          status,
          success_count,
          failed_count,
          actual_cost_usd,
          completed_at,
          updated_at
    """
    updated = fetch_one(
        query,
        {
            "analysis_job_id": analysis_job_id,
            "success_count": success_count,
            "failed_count": failed_count,
            "actual_cost_usd": actual_cost_usd,
        },
    )
    if updated is None:
        raise RuntimeError("Analysis job update did not return a row.")
    return updated


def mark_job_failed(
    analysis_job_id: str,
    error_message: str,
    failed_count: int = 1,
) -> dict[str, Any]:
    query = """
        UPDATE analysis_job
        SET
          status = 'failed',
          completed_at = now(),
          failed_count = %(failed_count)s,
          error_message = %(error_message)s,
          updated_at = now()
        WHERE id = %(analysis_job_id)s
        RETURNING
          id,
          job_type,
          status,
          failed_count,
          error_message,
          completed_at,
          updated_at
    """
    updated = fetch_one(
        query,
        {
            "analysis_job_id": analysis_job_id,
            "error_message": error_message,
            "failed_count": failed_count,
        },
    )
    if updated is None:
        raise RuntimeError("Analysis job update did not return a row.")
    return updated
