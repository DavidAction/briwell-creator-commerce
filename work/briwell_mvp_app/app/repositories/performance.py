from typing import Any

from app.core.db import fetch_one


def create_performance_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    query = """
        INSERT INTO campaign_performance_snapshot (
          campaign_id,
          outreach_id,
          creator_id,
          post_url,
          platform,
          tracking_url,
          coupon_code,
          view_count,
          like_count,
          comment_count,
          share_count,
          click_count,
          conversion_count,
          revenue_usd,
          source_type,
          source_risk_level,
          measured_at
        ) VALUES (
          %(campaign_id)s,
          %(outreach_id)s,
          %(creator_id)s,
          %(post_url)s,
          %(platform)s,
          %(tracking_url)s,
          %(coupon_code)s,
          %(view_count)s,
          %(like_count)s,
          %(comment_count)s,
          %(share_count)s,
          %(click_count)s,
          %(conversion_count)s,
          %(revenue_usd)s,
          %(source_type)s,
          %(source_risk_level)s,
          COALESCE(%(measured_at)s, now())
        )
        RETURNING *
    """
    created = fetch_one(query, payload)
    if created is None:
        raise RuntimeError("Performance snapshot insert did not return a row.")
    return created


def campaign_summary(campaign_id: str) -> dict[str, Any]:
    query = """
        SELECT
          campaign_id,
          COUNT(*) AS snapshot_count,
          COALESCE(SUM(view_count), 0) AS view_count,
          COALESCE(SUM(like_count), 0) AS like_count,
          COALESCE(SUM(comment_count), 0) AS comment_count,
          COALESCE(SUM(click_count), 0) AS click_count,
          COALESCE(SUM(conversion_count), 0) AS conversion_count,
          COALESCE(SUM(revenue_usd), 0) AS revenue_usd
        FROM campaign_performance_snapshot
        WHERE campaign_id = %(campaign_id)s
        GROUP BY campaign_id
    """
    return fetch_one(query, {"campaign_id": campaign_id}) or {
        "campaign_id": campaign_id,
        "snapshot_count": 0,
        "view_count": 0,
        "like_count": 0,
        "comment_count": 0,
        "click_count": 0,
        "conversion_count": 0,
        "revenue_usd": 0,
    }
