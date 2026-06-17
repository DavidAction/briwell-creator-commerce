from typing import Any

from psycopg.types.json import Jsonb

from app.core.db import execute_many, fetch_all


def list_videos(
    creator_id: str | None = None,
    source_risk_level: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": min(limit, 100)}
    filters = [
        "source_risk_level IN ('low', 'low_medium', 'medium')",
        "content_available = TRUE",
        "deletion_detected_at IS NULL",
    ]
    if creator_id:
        filters.append("creator_id = %(creator_id)s")
        params["creator_id"] = creator_id
    if source_risk_level:
        filters.append("source_risk_level = %(source_risk_level)s")
        params["source_risk_level"] = source_risk_level

    query = f"""
        SELECT
          id,
          creator_id,
          platform_video_id,
          url,
          caption,
          hashtags,
          posted_at,
          view_count,
          like_count,
          comment_count,
          share_count,
          save_count,
          duration_seconds,
          thumbnail_url,
          transcript,
          source_type,
          source_url,
          source_risk_level,
          collected_at,
          content_available,
          created_at,
          updated_at
        FROM video
        WHERE {' AND '.join(filters)}
        ORDER BY posted_at DESC NULLS LAST, created_at DESC
        LIMIT %(limit)s
    """
    return fetch_all(query, params)


def import_videos(
    creator_id: str,
    source_type: str,
    source_risk_level: str,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    query = """
        INSERT INTO video (
          creator_id,
          platform_video_id,
          url,
          caption,
          hashtags,
          posted_at,
          view_count,
          like_count,
          comment_count,
          share_count,
          save_count,
          duration_seconds,
          thumbnail_url,
          transcript,
          raw_metadata,
          source_type,
          source_url,
          source_risk_level,
          last_synced_at
        ) VALUES (
          %(creator_id)s,
          %(platform_video_id)s,
          %(url)s,
          %(caption)s,
          %(hashtags)s,
          %(posted_at)s,
          %(view_count)s,
          %(like_count)s,
          %(comment_count)s,
          %(share_count)s,
          %(save_count)s,
          %(duration_seconds)s,
          %(thumbnail_url)s,
          %(transcript)s,
          %(raw_metadata)s,
          %(source_type)s,
          %(source_url)s,
          %(source_risk_level)s,
          now()
        )
        ON CONFLICT (creator_id, platform_video_id)
        DO UPDATE SET
          url = EXCLUDED.url,
          caption = EXCLUDED.caption,
          hashtags = EXCLUDED.hashtags,
          posted_at = EXCLUDED.posted_at,
          view_count = EXCLUDED.view_count,
          like_count = EXCLUDED.like_count,
          comment_count = EXCLUDED.comment_count,
          share_count = EXCLUDED.share_count,
          save_count = EXCLUDED.save_count,
          duration_seconds = EXCLUDED.duration_seconds,
          thumbnail_url = EXCLUDED.thumbnail_url,
          transcript = EXCLUDED.transcript,
          raw_metadata = EXCLUDED.raw_metadata,
          source_type = EXCLUDED.source_type,
          source_url = EXCLUDED.source_url,
          source_risk_level = EXCLUDED.source_risk_level,
          last_synced_at = now(),
          updated_at = now()
        RETURNING id, creator_id, platform_video_id, url, source_risk_level
    """
    rows = []
    for item in items:
        rows.append(
            {
                "creator_id": creator_id,
                "platform_video_id": item.get("platform_video_id"),
                "url": item["url"],
                "caption": item.get("caption"),
                "hashtags": item.get("hashtags", []),
                "posted_at": item.get("posted_at"),
                "view_count": item.get("view_count"),
                "like_count": item.get("like_count"),
                "comment_count": item.get("comment_count"),
                "share_count": item.get("share_count"),
                "save_count": item.get("save_count"),
                "duration_seconds": item.get("duration_seconds"),
                "thumbnail_url": item.get("thumbnail_url"),
                "transcript": item.get("transcript"),
                "raw_metadata": Jsonb(item.get("raw_metadata", {})),
                "source_type": source_type,
                "source_url": item.get("source_url"),
                "source_risk_level": source_risk_level,
            }
        )
    return execute_many(query, rows)
