from typing import Any

from app.core.db import fetch_all, fetch_one


def list_products(product_category: str | None = None) -> list[dict[str, Any]]:
    params: dict[str, Any] = {}
    filters = ["status <> 'inactive'"]
    if product_category:
        filters.append("product_category = %(product_category)s")
        params["product_category"] = product_category

    query = f"""
        SELECT
          id,
          brand_name,
          product_name,
          product_category,
          country_availability,
          key_claims_allowed,
          claims_disallowed,
          target_skin_concerns,
          price_range,
          sample_available,
          landing_url,
          status,
          created_at,
          updated_at
        FROM product_catalog
        WHERE {' AND '.join(filters)}
        ORDER BY created_at DESC
        LIMIT 100
    """
    return fetch_all(query, params)


def create_product(payload: dict[str, Any]) -> dict[str, Any]:
    query = """
        INSERT INTO product_catalog (
          brand_name,
          product_name,
          product_category,
          country_availability,
          key_claims_allowed,
          claims_disallowed
        ) VALUES (
          %(brand_name)s,
          %(product_name)s,
          %(product_category)s,
          %(country_availability)s,
          %(key_claims_allowed)s,
          %(claims_disallowed)s
        )
        RETURNING *
    """
    created = fetch_one(query, payload)
    if created is None:
        raise RuntimeError("Product insert did not return a row.")
    return created
