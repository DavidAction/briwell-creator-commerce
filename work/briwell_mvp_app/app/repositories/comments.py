from typing import Any

from app.core.db import execute_many, fetch_all


def list_comment_samples(
    video_id: str | None = None,
    source_risk_level: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": min(limit, 100)}
    filters = [
        "source_risk_level IN ('low', 'low_medium', 'medium')",
        "contains_sensitive_data = FALSE",
    ]
    if video_id:
        filters.append("video_id = %(video_id)s")
        params["video_id"] = video_id
    if source_risk_level:
        filters.append("source_risk_level = %(source_risk_level)s")
        params["source_risk_level"] = source_risk_level

    query = f"""
        SELECT
          id,
          video_id,
          comment_text,
          comment_language,
          like_count,
          reply_count,
          sentiment,
          purchase_intent,
          question_type,
          sample_method,
          source_risk_level,
          collected_at,
          sampled_at
        FROM comment_sample
        WHERE {' AND '.join(filters)}
        ORDER BY sampled_at DESC, created_at DESC
        LIMIT %(limit)s
    """
    return fetch_all(query, params)


def import_comment_samples(
    video_id: str,
    sample_method: str,
    source_risk_level: str,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    query = """
        INSERT INTO comment_sample (
          video_id,
          comment_text,
          comment_language,
          like_count,
          reply_count,
          sentiment,
          purchase_intent,
          question_type,
          sample_method,
          source_risk_level,
          contains_sensitive_data
        ) VALUES (
          %(video_id)s,
          %(comment_text)s,
          %(comment_language)s,
          %(like_count)s,
          %(reply_count)s,
          %(sentiment)s,
          %(purchase_intent)s,
          %(question_type)s,
          %(sample_method)s,
          %(source_risk_level)s,
          FALSE
        )
        RETURNING id, video_id, comment_language, source_risk_level, sample_method
    """
    rows = []
    for item in items:
        rows.append(
            {
                "video_id": video_id,
                "comment_text": item["comment_text"],
                "comment_language": item.get("comment_language", "es"),
                "like_count": item.get("like_count"),
                "reply_count": item.get("reply_count"),
                "sentiment": item.get("sentiment"),
                "purchase_intent": item.get("purchase_intent"),
                "question_type": item.get("question_type"),
                "sample_method": sample_method,
                "source_risk_level": source_risk_level,
            }
        )
    return execute_many(query, rows)
