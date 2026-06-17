from typing import Any

from app.core.db import fetch_all, fetch_one


def list_invocation_logs(
    analysis_job_id: str | None = None,
    target_entity_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": min(limit, 100)}
    filters = ["1 = 1"]
    if analysis_job_id:
        filters.append("analysis_job_id = %(analysis_job_id)s")
        params["analysis_job_id"] = analysis_job_id
    if target_entity_type:
        filters.append("target_entity_type = %(target_entity_type)s")
        params["target_entity_type"] = target_entity_type
    if status:
        filters.append("status = %(status)s")
        params["status"] = status

    query = f"""
        SELECT
          id,
          analysis_job_id,
          model_config_id,
          target_entity_type,
          target_entity_id,
          prompt_version,
          input_token_count,
          output_token_count,
          cost_usd,
          latency_ms,
          status,
          error_message,
          created_at
        FROM ai_invocation_log
        WHERE {' AND '.join(filters)}
        ORDER BY created_at DESC
        LIMIT %(limit)s
    """
    return fetch_all(query, params)


def create_invocation_log(payload: dict[str, Any]) -> dict[str, Any]:
    query = """
        INSERT INTO ai_invocation_log (
          analysis_job_id,
          model_config_id,
          target_entity_type,
          target_entity_id,
          prompt_version,
          input_token_count,
          output_token_count,
          cost_usd,
          latency_ms,
          status,
          error_message
        ) VALUES (
          %(analysis_job_id)s,
          %(model_config_id)s,
          %(target_entity_type)s,
          %(target_entity_id)s,
          %(prompt_version)s,
          %(input_token_count)s,
          %(output_token_count)s,
          %(cost_usd)s,
          %(latency_ms)s,
          %(status)s,
          %(error_message)s
        )
        RETURNING
          id,
          analysis_job_id,
          model_config_id,
          target_entity_type,
          target_entity_id,
          prompt_version,
          input_token_count,
          output_token_count,
          cost_usd,
          latency_ms,
          status,
          error_message,
          created_at
    """
    created = fetch_one(
        query,
        {
            "analysis_job_id": payload.get("analysis_job_id"),
            "model_config_id": payload.get("model_config_id"),
            "target_entity_type": payload["target_entity_type"],
            "target_entity_id": payload.get("target_entity_id"),
            "prompt_version": payload["prompt_version"],
            "input_token_count": payload.get("input_token_count"),
            "output_token_count": payload.get("output_token_count"),
            "cost_usd": payload.get("cost_usd"),
            "latency_ms": payload.get("latency_ms"),
            "status": payload["status"],
            "error_message": payload.get("error_message"),
        },
    )
    if created is None:
        raise RuntimeError("AI invocation log insert did not return a row.")
    return created
