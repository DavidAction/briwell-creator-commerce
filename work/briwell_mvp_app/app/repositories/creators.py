from typing import Any

from app.core.db import execute_many, fetch_all, fetch_one


def list_creators(
    country: str | None = None,
    source_risk_level: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": min(limit, 100)}
    filters = [
        "source_risk_level IN ('low', 'low_medium', 'medium')",
        "status NOT IN ('quarantined', 'do_not_contact', 'removed', 'avoided')",
        "do_not_contact = FALSE",
        "removal_requested_at IS NULL",
    ]
    if country:
        filters.append("country = %(country)s")
        params["country"] = country
    if source_risk_level:
        filters.append("source_risk_level = %(source_risk_level)s")
        params["source_risk_level"] = source_risk_level

    query = f"""
        SELECT
          id,
          platform,
          country,
          username,
          display_name,
          profile_url,
          bio,
          language,
          follower_count,
          contact_email,
          instagram_url,
          source_type,
          source_url,
          source_risk_level,
          collected_at,
          last_verified_at,
          status
        FROM creator
        WHERE {' AND '.join(filters)}
        ORDER BY created_at DESC
        LIMIT %(limit)s
    """
    return fetch_all(query, params)


def get_creator_by_id(creator_id: str) -> dict[str, Any] | None:
    query = """
        SELECT
          id,
          platform,
          country,
          username,
          display_name,
          profile_url,
          bio,
          language,
          follower_count,
          contact_email,
          instagram_url,
          source_type,
          source_url,
          source_risk_level,
          collected_at,
          last_verified_at,
          do_not_contact,
          removal_requested_at,
          status
        FROM creator
        WHERE id = %(creator_id)s
        LIMIT 1
    """
    return fetch_one(query, {"creator_id": creator_id})


def import_creators(
    source_type: str,
    source_risk_level: str,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    query = """
        INSERT INTO creator (
          platform,
          country,
          username,
          display_name,
          profile_url,
          bio,
          language,
          follower_count,
          source_type,
          source_url,
          source_risk_level,
          last_verified_at,
          status
        ) VALUES (
          'tiktok',
          %(country)s,
          %(username)s,
          %(display_name)s,
          %(profile_url)s,
          %(bio)s,
          %(language)s,
          %(follower_count)s,
          %(source_type)s,
          %(source_url)s,
          %(source_risk_level)s,
          now(),
          'active'
        )
        ON CONFLICT (platform, username)
        DO UPDATE SET
          display_name = EXCLUDED.display_name,
          profile_url = EXCLUDED.profile_url,
          bio = EXCLUDED.bio,
          follower_count = EXCLUDED.follower_count,
          source_type = EXCLUDED.source_type,
          source_url = EXCLUDED.source_url,
          source_risk_level = EXCLUDED.source_risk_level,
          last_verified_at = now(),
          updated_at = now()
        RETURNING id, username, country, source_risk_level, status
    """
    rows = []
    for item in items:
        rows.append(
            {
                "country": item["country"],
                "username": item["username"],
                "display_name": item.get("display_name"),
                "profile_url": item["profile_url"],
                "bio": item.get("bio"),
                "language": item.get("language", "es"),
                "follower_count": item.get("follower_count"),
                "source_type": source_type,
                "source_url": item.get("source_url"),
                "source_risk_level": source_risk_level,
            }
        )
    return execute_many(query, rows)
