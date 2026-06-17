from typing import Any

from app.core.db import fetch_all, fetch_one


def list_campaigns(
    country: str | None = None,
    status: str | None = None,
    product_category: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": min(limit, 100)}
    filters = ["1 = 1"]
    if country:
        filters.append("country = %(country)s")
        params["country"] = country
    if status:
        filters.append("status = %(status)s")
        params["status"] = status
    if product_category:
        filters.append("product_category = %(product_category)s")
        params["product_category"] = product_category

    query = f"""
        SELECT
          id,
          name,
          product_id,
          country,
          product_category,
          campaign_goal,
          budget,
          sales_channel,
          tracking_url,
          coupon_code_prefix,
          target_creator_count,
          target_post_count,
          start_date,
          end_date,
          status,
          created_at,
          updated_at
        FROM campaign
        WHERE {' AND '.join(filters)}
        ORDER BY created_at DESC
        LIMIT %(limit)s
    """
    return fetch_all(query, params)


def create_campaign(payload: dict[str, Any]) -> dict[str, Any]:
    query = """
        INSERT INTO campaign (
          name,
          product_id,
          country,
          product_category,
          campaign_goal,
          budget,
          sales_channel,
          tracking_url,
          coupon_code_prefix,
          target_creator_count,
          target_post_count,
          start_date,
          end_date,
          status
        ) VALUES (
          %(name)s,
          %(product_id)s,
          %(country)s,
          %(product_category)s,
          %(campaign_goal)s,
          %(budget)s,
          %(sales_channel)s,
          %(tracking_url)s,
          %(coupon_code_prefix)s,
          %(target_creator_count)s,
          %(target_post_count)s,
          %(start_date)s,
          %(end_date)s,
          %(status)s
        )
        RETURNING *
    """
    created = fetch_one(query, payload)
    if created is None:
        raise RuntimeError("Campaign insert did not return a row.")
    return created


def get_campaign(campaign_id: str) -> dict[str, Any] | None:
    query = """
        SELECT
          id,
          name,
          product_id,
          country,
          product_category,
          campaign_goal,
          budget,
          sales_channel,
          tracking_url,
          coupon_code_prefix,
          target_creator_count,
          target_post_count,
          start_date,
          end_date,
          status,
          created_at,
          updated_at
        FROM campaign
        WHERE id = %(campaign_id)s
        LIMIT 1
    """
    return fetch_one(query, {"campaign_id": campaign_id})


def list_campaign_candidates(
    campaign_id: str,
    country: str,
    product_category: str,
    min_score: float = 70,
    max_risk_penalty: float = 10,
    segment: str | None = None,
    exclude_existing_outreach: bool = True,
    limit: int = 50,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "campaign_id": campaign_id,
        "country": country,
        "product_category": product_category,
        "min_score": min_score,
        "max_risk_penalty": max_risk_penalty,
        "limit": min(limit, 100),
    }
    filters = [
        "c.country = %(country)s",
        "lca.final_score >= %(min_score)s",
        "lca.risk_penalty <= %(max_risk_penalty)s",
        "lca.segment <> 'avoid'",
        "%(product_category)s = ANY(lca.recommended_products)",
    ]
    if segment:
        filters.append("lca.segment = %(segment)s")
        params["segment"] = segment
    if exclude_existing_outreach:
        filters.append(
            """
            NOT EXISTS (
              SELECT 1
              FROM outreach o
              WHERE o.creator_id = c.id
                AND o.campaign_id = %(campaign_id)s
                AND o.status NOT IN ('rejected', 'paused')
            )
            """
        )

    query = f"""
        SELECT
          c.id AS creator_id,
          c.username,
          c.display_name,
          c.country,
          c.profile_url,
          c.bio,
          c.language,
          c.follower_count,
          c.contact_email,
          c.instagram_url,
          c.source_risk_level,
          c.status AS creator_status,
          lca.id AS analysis_id,
          lca.analysis_version,
          lca.final_score,
          lca.risk_penalty,
          lca.segment,
          lca.recommended_products,
          lca.recommended_campaign_angle,
          lca.ai_summary,
          lca.score_confidence,
          lca.review_required_reason,
          lca.created_at AS analysis_created_at
        FROM eligible_creator_for_outreach c
        JOIN latest_creator_analysis lca ON lca.creator_id = c.id
        WHERE {' AND '.join(filters)}
        ORDER BY
          lca.final_score DESC,
          lca.risk_penalty ASC,
          lca.score_confidence DESC,
          c.follower_count DESC NULLS LAST
        LIMIT %(limit)s
    """
    return fetch_all(query, params)


def get_campaign_candidate(
    campaign_id: str,
    creator_id: str,
    country: str,
    product_category: str,
    min_score: float = 70,
    max_risk_penalty: float = 10,
    exclude_existing_outreach: bool = True,
) -> dict[str, Any] | None:
    params: dict[str, Any] = {
        "campaign_id": campaign_id,
        "creator_id": creator_id,
        "country": country,
        "product_category": product_category,
        "min_score": min_score,
        "max_risk_penalty": max_risk_penalty,
    }
    filters = [
        "c.id = %(creator_id)s",
        "c.country = %(country)s",
        "lca.final_score >= %(min_score)s",
        "lca.risk_penalty <= %(max_risk_penalty)s",
        "lca.segment <> 'avoid'",
        "%(product_category)s = ANY(lca.recommended_products)",
    ]
    if exclude_existing_outreach:
        filters.append(
            """
            NOT EXISTS (
              SELECT 1
              FROM outreach o
              WHERE o.creator_id = c.id
                AND o.campaign_id = %(campaign_id)s
                AND o.status NOT IN ('rejected', 'paused')
            )
            """
        )

    query = f"""
        SELECT
          c.id AS creator_id,
          c.username,
          c.display_name,
          c.country,
          c.profile_url,
          c.bio,
          c.language,
          c.follower_count,
          c.contact_email,
          c.instagram_url,
          c.source_risk_level,
          c.status AS creator_status,
          lca.id AS analysis_id,
          lca.analysis_version,
          lca.final_score,
          lca.risk_penalty,
          lca.segment,
          lca.recommended_products,
          lca.recommended_campaign_angle,
          lca.ai_summary,
          lca.score_confidence,
          lca.review_required_reason,
          lca.created_at AS analysis_created_at
        FROM eligible_creator_for_outreach c
        JOIN latest_creator_analysis lca ON lca.creator_id = c.id
        WHERE {' AND '.join(filters)}
        LIMIT 1
    """
    return fetch_one(query, params)
