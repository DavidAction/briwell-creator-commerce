"""Repository functions for the Shopify commerce integrity schema (migration 008).

Pure SQL functions following the existing app/repositories/*.py convention:
fetch_one/fetch_all + %(name)s named params, JSONB params wrapped with
psycopg's Jsonb adapter. No business logic lives here -- accrual/reversal
math and attribution decisions come from app/commerce/*.py; this module only
persists their results.
"""

from typing import Any

from psycopg.types.json import Jsonb

from app.core.db import connection, fetch_all, fetch_one

MAX_LIST_LIMIT = 200


def _limit(value: int) -> int:
    return max(min(value, MAX_LIST_LIMIT), 1)


# ---------------------------------------------------------------------------
# shop_order / shop_order_line_item
# ---------------------------------------------------------------------------


def upsert_shop_order(payload: dict[str, Any]) -> dict[str, Any]:
    query = """
        INSERT INTO shop_order (
          shopify_order_id,
          order_number,
          shop_domain,
          country,
          currency,
          subtotal_amount,
          discount_amount,
          shipping_amount,
          tax_amount,
          total_amount,
          fx_rate_usd,
          financial_status,
          discount_codes,
          landing_site,
          utm_params,
          customer_ref,
          ordered_at,
          raw_payload
        ) VALUES (
          %(shopify_order_id)s,
          %(order_number)s,
          %(shop_domain)s,
          %(country)s,
          %(currency)s,
          %(subtotal_amount)s,
          %(discount_amount)s,
          %(shipping_amount)s,
          %(tax_amount)s,
          %(total_amount)s,
          %(fx_rate_usd)s,
          %(financial_status)s,
          %(discount_codes)s,
          %(landing_site)s,
          %(utm_params)s,
          %(customer_ref)s,
          %(ordered_at)s,
          %(raw_payload)s
        )
        ON CONFLICT (shopify_order_id) DO UPDATE SET
          order_number = EXCLUDED.order_number,
          shop_domain = EXCLUDED.shop_domain,
          country = EXCLUDED.country,
          currency = EXCLUDED.currency,
          subtotal_amount = EXCLUDED.subtotal_amount,
          discount_amount = EXCLUDED.discount_amount,
          shipping_amount = EXCLUDED.shipping_amount,
          tax_amount = EXCLUDED.tax_amount,
          total_amount = EXCLUDED.total_amount,
          fx_rate_usd = EXCLUDED.fx_rate_usd,
          financial_status = EXCLUDED.financial_status,
          discount_codes = EXCLUDED.discount_codes,
          landing_site = EXCLUDED.landing_site,
          utm_params = EXCLUDED.utm_params,
          customer_ref = EXCLUDED.customer_ref,
          ordered_at = EXCLUDED.ordered_at,
          raw_payload = EXCLUDED.raw_payload
        RETURNING *
    """
    created = fetch_one(
        query,
        {
            **payload,
            "discount_codes": Jsonb(payload.get("discount_codes", [])),
            "utm_params": Jsonb(payload.get("utm_params", {})),
            "raw_payload": Jsonb(payload.get("raw_payload", {})),
        },
    )
    if created is None:
        raise RuntimeError("shop_order upsert did not return a row.")
    return created


def insert_line_items(order_id: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not items:
        return []
    query = """
        INSERT INTO shop_order_line_item (
          order_id,
          shopify_line_item_id,
          title,
          sku,
          product_id,
          quantity,
          unit_price,
          total_discount
        ) VALUES (
          %(order_id)s,
          %(shopify_line_item_id)s,
          %(title)s,
          %(sku)s,
          %(product_id)s,
          %(quantity)s,
          %(unit_price)s,
          %(total_discount)s
        )
        ON CONFLICT (order_id, shopify_line_item_id) DO UPDATE SET
          title = EXCLUDED.title,
          sku = EXCLUDED.sku,
          product_id = EXCLUDED.product_id,
          quantity = EXCLUDED.quantity,
          unit_price = EXCLUDED.unit_price,
          total_discount = EXCLUDED.total_discount
        RETURNING *
    """
    created: list[dict[str, Any]] = []
    with connection() as conn:
        with conn.cursor() as cur:
            for item in items:
                cur.execute(query, {"order_id": order_id, **item})
                row = cur.fetchone()
                if row is not None:
                    created.append(dict(row))
        conn.commit()
    return created


def get_order_by_shopify_id(shopify_order_id: str) -> dict[str, Any] | None:
    query = "SELECT * FROM shop_order WHERE shopify_order_id = %(shopify_order_id)s"
    return fetch_one(query, {"shopify_order_id": shopify_order_id})


def get_order_by_id(order_id: str) -> dict[str, Any] | None:
    query = "SELECT * FROM shop_order WHERE id = %(order_id)s"
    return fetch_one(query, {"order_id": order_id})


def list_orders(limit: int = 50) -> list[dict[str, Any]]:
    query = """
        SELECT * FROM shop_order
        ORDER BY ordered_at DESC
        LIMIT %(limit)s
    """
    return fetch_all(query, {"limit": _limit(limit)})


def list_line_items_for_order(order_id: str) -> list[dict[str, Any]]:
    query = """
        SELECT * FROM shop_order_line_item
        WHERE order_id = %(order_id)s
        ORDER BY created_at ASC
    """
    return fetch_all(query, {"order_id": order_id})


# ---------------------------------------------------------------------------
# order_refund
# ---------------------------------------------------------------------------


def insert_refund(payload: dict[str, Any]) -> dict[str, Any]:
    query = """
        INSERT INTO order_refund (
          order_id,
          shopify_refund_id,
          currency,
          commissionable_refund_amount,
          total_refund_amount,
          refund_line_items,
          reason,
          processed_at,
          raw_payload
        ) VALUES (
          %(order_id)s,
          %(shopify_refund_id)s,
          %(currency)s,
          %(commissionable_refund_amount)s,
          %(total_refund_amount)s,
          %(refund_line_items)s,
          %(reason)s,
          %(processed_at)s,
          %(raw_payload)s
        )
        ON CONFLICT (shopify_refund_id) DO NOTHING
        RETURNING *
    """
    created = fetch_one(
        query,
        {
            **payload,
            "refund_line_items": Jsonb(payload.get("refund_line_items", [])),
            "raw_payload": Jsonb(payload.get("raw_payload", {})),
        },
    )
    if created is not None:
        return created
    # Already ingested (webhook redelivery) -- return the existing row.
    existing = get_refund_by_shopify_id(payload["shopify_refund_id"])
    if existing is None:
        raise RuntimeError("order_refund insert conflicted but no existing row was found.")
    return existing


def get_refund_by_shopify_id(shopify_refund_id: str) -> dict[str, Any] | None:
    query = "SELECT * FROM order_refund WHERE shopify_refund_id = %(shopify_refund_id)s"
    return fetch_one(query, {"shopify_refund_id": shopify_refund_id})


def list_refunds_for_order(order_id: str) -> list[dict[str, Any]]:
    query = """
        SELECT * FROM order_refund
        WHERE order_id = %(order_id)s
        ORDER BY processed_at ASC
    """
    return fetch_all(query, {"order_id": order_id})


# ---------------------------------------------------------------------------
# creator_discount_code / creator_utm_link
# ---------------------------------------------------------------------------


def create_discount_code(payload: dict[str, Any]) -> dict[str, Any]:
    query = """
        INSERT INTO creator_discount_code (
          creator_id,
          campaign_id,
          code,
          commission_rate,
          shopify_price_rule_id,
          shopify_discount_code_id,
          valid_from,
          valid_until,
          status
        ) VALUES (
          %(creator_id)s,
          %(campaign_id)s,
          %(code)s,
          %(commission_rate)s,
          %(shopify_price_rule_id)s,
          %(shopify_discount_code_id)s,
          %(valid_from)s,
          %(valid_until)s,
          %(status)s
        )
        RETURNING *
    """
    created = fetch_one(query, payload)
    if created is None:
        raise RuntimeError("creator_discount_code insert did not return a row.")
    return created


def list_discount_codes(creator_id: str | None = None, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    filters = ["1 = 1"]
    params: dict[str, Any] = {"limit": _limit(limit)}
    if creator_id:
        filters.append("creator_id = %(creator_id)s")
        params["creator_id"] = creator_id
    if status:
        filters.append("status = %(status)s")
        params["status"] = status
    query = f"""
        SELECT * FROM creator_discount_code
        WHERE {' AND '.join(filters)}
        ORDER BY created_at DESC
        LIMIT %(limit)s
    """
    return fetch_all(query, params)


def find_active_codes(codes: list[str]) -> list[dict[str, Any]]:
    if not codes:
        return []
    normalized = [code.strip().upper() for code in codes if code and code.strip()]
    if not normalized:
        return []
    query = """
        SELECT * FROM creator_discount_code
        WHERE status = 'active' AND code = ANY(%(codes)s)
    """
    return fetch_all(query, {"codes": normalized})


def create_utm_link(payload: dict[str, Any]) -> dict[str, Any]:
    query = """
        INSERT INTO creator_utm_link (
          creator_id,
          campaign_id,
          ref_token,
          destination_url,
          utm_source,
          utm_medium,
          utm_campaign,
          commission_rate,
          status
        ) VALUES (
          %(creator_id)s,
          %(campaign_id)s,
          %(ref_token)s,
          %(destination_url)s,
          %(utm_source)s,
          %(utm_medium)s,
          %(utm_campaign)s,
          %(commission_rate)s,
          %(status)s
        )
        RETURNING *
    """
    created = fetch_one(query, payload)
    if created is None:
        raise RuntimeError("creator_utm_link insert did not return a row.")
    return created


def list_utm_links(creator_id: str | None = None, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    filters = ["1 = 1"]
    params: dict[str, Any] = {"limit": _limit(limit)}
    if creator_id:
        filters.append("creator_id = %(creator_id)s")
        params["creator_id"] = creator_id
    if status:
        filters.append("status = %(status)s")
        params["status"] = status
    query = f"""
        SELECT * FROM creator_utm_link
        WHERE {' AND '.join(filters)}
        ORDER BY created_at DESC
        LIMIT %(limit)s
    """
    return fetch_all(query, params)


def find_active_utm_link(ref_token: str | None) -> dict[str, Any] | None:
    if not ref_token or not ref_token.strip():
        return None
    query = """
        SELECT * FROM creator_utm_link
        WHERE status = 'active' AND ref_token = %(ref_token)s
    """
    return fetch_one(query, {"ref_token": ref_token.strip().lower()})


# ---------------------------------------------------------------------------
# order_attribution
# ---------------------------------------------------------------------------


def insert_attribution(payload: dict[str, Any]) -> dict[str, Any]:
    query = """
        INSERT INTO order_attribution (
          order_id,
          creator_id,
          method,
          confidence,
          status,
          conflict_kind,
          matched_discount_code_id,
          matched_utm_link_id,
          competing_creator_id,
          decision_notes,
          decided_by,
          resolved_by_email,
          resolved_at
        ) VALUES (
          %(order_id)s,
          %(creator_id)s,
          %(method)s,
          %(confidence)s,
          %(status)s,
          %(conflict_kind)s,
          %(matched_discount_code_id)s,
          %(matched_utm_link_id)s,
          %(competing_creator_id)s,
          %(decision_notes)s,
          %(decided_by)s,
          %(resolved_by_email)s,
          %(resolved_at)s
        )
        RETURNING *
    """
    created = fetch_one(query, payload)
    if created is None:
        raise RuntimeError("order_attribution insert did not return a row.")
    return created


def get_live_attribution(order_id: str) -> dict[str, Any] | None:
    query = """
        SELECT * FROM order_attribution
        WHERE order_id = %(order_id)s AND status IN ('active', 'needs_review')
        LIMIT 1
    """
    return fetch_one(query, {"order_id": order_id})


def get_attribution(attribution_id: str) -> dict[str, Any] | None:
    query = "SELECT * FROM order_attribution WHERE id = %(attribution_id)s"
    return fetch_one(query, {"attribution_id": attribution_id})


def supersede_attribution(attribution_id: str, next_status: str, resolved_by_email: str | None = None) -> dict[str, Any]:
    query = """
        UPDATE order_attribution
        SET status = %(next_status)s,
            resolved_by_email = COALESCE(%(resolved_by_email)s, resolved_by_email),
            resolved_at = now()
        WHERE id = %(attribution_id)s
        RETURNING *
    """
    updated = fetch_one(
        query,
        {
            "attribution_id": attribution_id,
            "next_status": next_status,
            "resolved_by_email": resolved_by_email,
        },
    )
    if updated is None:
        raise RuntimeError(f"order_attribution {attribution_id} not found for status update.")
    return updated


def list_attributions(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    filters = ["1 = 1"]
    params: dict[str, Any] = {"limit": _limit(limit)}
    if status:
        filters.append("status = %(status)s")
        params["status"] = status
    query = f"""
        SELECT * FROM order_attribution
        WHERE {' AND '.join(filters)}
        ORDER BY created_at DESC
        LIMIT %(limit)s
    """
    return fetch_all(query, params)


# ---------------------------------------------------------------------------
# commission_ledger
# ---------------------------------------------------------------------------


def insert_ledger_entry(payload: dict[str, Any]) -> dict[str, Any]:
    query = """
        INSERT INTO commission_ledger (
          creator_id,
          campaign_id,
          order_id,
          attribution_id,
          refund_id,
          entry_type,
          amount,
          currency,
          fx_rate_usd,
          reverses_entry_id,
          commission_rate,
          memo,
          created_by_email
        ) VALUES (
          %(creator_id)s,
          %(campaign_id)s,
          %(order_id)s,
          %(attribution_id)s,
          %(refund_id)s,
          %(entry_type)s,
          %(amount)s,
          %(currency)s,
          %(fx_rate_usd)s,
          %(reverses_entry_id)s,
          %(commission_rate)s,
          %(memo)s,
          %(created_by_email)s
        )
        RETURNING *
    """
    created = fetch_one(query, payload)
    if created is None:
        raise RuntimeError("commission_ledger insert did not return a row.")
    return created


def list_ledger(creator_id: str | None = None, order_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    filters = ["1 = 1"]
    params: dict[str, Any] = {"limit": _limit(limit)}
    if creator_id:
        filters.append("creator_id = %(creator_id)s")
        params["creator_id"] = creator_id
    if order_id:
        filters.append("order_id = %(order_id)s")
        params["order_id"] = order_id
    query = f"""
        SELECT * FROM commission_ledger
        WHERE {' AND '.join(filters)}
        ORDER BY created_at DESC
        LIMIT %(limit)s
    """
    return fetch_all(query, params)


def get_accrual_for_attribution(attribution_id: str) -> dict[str, Any] | None:
    query = """
        SELECT * FROM commission_ledger
        WHERE attribution_id = %(attribution_id)s AND entry_type = 'accrual'
        LIMIT 1
    """
    return fetch_one(query, {"attribution_id": attribution_id})


def sum_reversals_for_accrual(accrual_id: str) -> dict[str, Any]:
    query = """
        SELECT COALESCE(SUM(amount), 0) AS total_reversed, COUNT(*) AS reversal_count
        FROM commission_ledger
        WHERE reverses_entry_id = %(accrual_id)s AND entry_type = 'reversal'
    """
    return fetch_one(query, {"accrual_id": accrual_id}) or {
        "total_reversed": 0,
        "reversal_count": 0,
    }


def get_reversal_for_refund(accrual_id: str, refund_id: str) -> dict[str, Any] | None:
    query = """
        SELECT * FROM commission_ledger
        WHERE reverses_entry_id = %(accrual_id)s
          AND refund_id = %(refund_id)s
          AND entry_type = 'reversal'
        LIMIT 1
    """
    return fetch_one(query, {"accrual_id": accrual_id, "refund_id": refund_id})


def creator_balances(creator_id: str | None = None) -> list[dict[str, Any]]:
    filters = ["1 = 1"]
    params: dict[str, Any] = {}
    if creator_id:
        filters.append("creator_id = %(creator_id)s")
        params["creator_id"] = creator_id
    query = f"""
        SELECT * FROM creator_commission_balance
        WHERE {' AND '.join(filters)}
        ORDER BY creator_id, currency
    """
    return fetch_all(query, params)
