from typing import Any

from app.core.db import fetch_all


def list_keywords(
    country: str | None = None,
    product_category: str | None = None,
    status: str = "active",
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"status": status}
    filters = ["status = %(status)s"]
    if country:
        filters.append("country = %(country)s")
        params["country"] = country
    if product_category:
        filters.append("product_category = %(product_category)s")
        params["product_category"] = product_category

    query = f"""
        SELECT
          id,
          country,
          language,
          keyword,
          hashtag,
          product_category,
          intent_type,
          priority,
          notes,
          status,
          created_at,
          updated_at
        FROM keyword_seed
        WHERE {' AND '.join(filters)}
        ORDER BY country, product_category, priority, keyword NULLS LAST, hashtag NULLS LAST
        LIMIT 500
    """
    return fetch_all(query, params)
