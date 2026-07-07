"""Shopify webhook verification and payload transformation.

Pure functions only -- no DB, no network. The webhook router feeds real
Shopify webhook JSON through these transforms into the same ingest models
(`ShopifyOrderIngestRequest` / `OrderRefundIngestRequest`) used by the
operator-facing endpoints, so attribution/accrual behavior is identical
regardless of how an order arrives.

Fail-closed policy: unsupported currency, missing FX rate, or an
unrecognized financial_status raises ValueError (surfaced as HTTP 422)
instead of persisting a guessed value into the commission ledger.
"""

import base64
import hashlib
import hmac
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import parse_qsl, urlsplit

SUPPORTED_CURRENCIES = {"MXN", "PEN", "USD"}
SUPPORTED_COUNTRIES = {"MX", "PE", "EC"}
FINANCIAL_STATUSES = {
    "pending",
    "authorized",
    "paid",
    "partially_paid",
    "partially_refunded",
    "refunded",
    "voided",
    "cancelled",
}


def verify_webhook_hmac(secret: str, body: bytes, hmac_header: str | None) -> bool:
    if not secret or not hmac_header:
        return False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, hmac_header.strip())


def parse_fx_rates(raw: str) -> dict[str, Decimal]:
    """Parse SHOPIFY_FX_RATES, e.g. "MXN:0.058,PEN:0.27" -> {"MXN": Decimal(...)}."""
    rates: dict[str, Decimal] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        currency, _, value = pair.partition(":")
        currency = currency.strip().upper()
        try:
            rate = Decimal(value.strip())
        except InvalidOperation as exc:
            raise ValueError(f"Invalid FX rate for {currency!r} in SHOPIFY_FX_RATES: {value!r}") from exc
        if rate <= 0:
            raise ValueError(f"FX rate for {currency!r} must be positive, got {rate}")
        rates[currency] = rate
    return rates


def parse_utm_params(landing_site: str | None) -> dict[str, str]:
    if not landing_site:
        return {}
    query = urlsplit(landing_site).query
    return {
        key: value
        for key, value in parse_qsl(query, keep_blank_values=False)
        if key.startswith("utm_")
    }


def _money(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid money amount: {value!r}") from exc


def _resolve_fx(currency: str, fx_rates: dict[str, Decimal]) -> Decimal:
    if currency == "USD":
        return Decimal("1")
    rate = fx_rates.get(currency)
    if rate is None:
        raise ValueError(
            f"No FX rate configured for currency {currency!r}. "
            "Set SHOPIFY_FX_RATES (e.g. \"MXN:0.058,PEN:0.27\") before ingesting webhooks in this currency."
        )
    return rate


def transform_order_webhook(
    payload: dict[str, Any],
    fx_rates: dict[str, Decimal],
    shop_domain: str | None = None,
) -> dict[str, Any]:
    """Map a Shopify orders/create|orders/updated webhook body to ShopifyOrderIngestRequest kwargs."""
    shopify_order_id = payload.get("id")
    if shopify_order_id is None:
        raise ValueError("Order webhook payload is missing 'id'.")

    currency = str(payload.get("currency") or "").upper()
    if currency not in SUPPORTED_CURRENCIES:
        raise ValueError(
            f"Unsupported order currency {currency!r}; supported: {sorted(SUPPORTED_CURRENCIES)}."
        )

    financial_status = str(payload.get("financial_status") or "pending").lower()
    if payload.get("cancelled_at"):
        financial_status = "cancelled"
    if financial_status not in FINANCIAL_STATUSES:
        raise ValueError(f"Unrecognized financial_status {financial_status!r}.")

    ordered_at = payload.get("created_at") or payload.get("processed_at")
    if not ordered_at:
        raise ValueError("Order webhook payload is missing 'created_at'.")

    shipping_amount = Decimal("0")
    shipping_set = payload.get("total_shipping_price_set") or {}
    shop_money = shipping_set.get("shop_money") or {}
    if shop_money.get("amount") is not None:
        shipping_amount = _money(shop_money["amount"])

    country = None
    for address_key in ("shipping_address", "billing_address"):
        address = payload.get(address_key) or {}
        code = str(address.get("country_code") or "").upper()
        if code in SUPPORTED_COUNTRIES:
            country = code
            break

    customer = payload.get("customer") or {}
    customer_ref = str(customer["id"]) if customer.get("id") is not None else None

    line_items = []
    for item in payload.get("line_items") or []:
        title = item.get("title")
        if not title:
            raise ValueError("Order webhook line item is missing 'title'.")
        line_items.append(
            {
                "shopify_line_item_id": str(item["id"]) if item.get("id") is not None else None,
                "title": title,
                "sku": item.get("sku") or None,
                "product_id": str(item["product_id"]) if item.get("product_id") is not None else None,
                "quantity": int(item.get("quantity") or 1),
                "unit_price": _money(item.get("price")),
                "total_discount": _money(item.get("total_discount")),
            }
        )

    discount_codes = [
        str(entry["code"]).strip().upper()
        for entry in payload.get("discount_codes") or []
        if entry.get("code")
    ]

    return {
        "shopify_order_id": str(shopify_order_id),
        "order_number": str(payload["order_number"]) if payload.get("order_number") is not None else payload.get("name"),
        "shop_domain": shop_domain,
        "country": country,
        "currency": currency,
        "subtotal_amount": _money(payload.get("subtotal_price")),
        "discount_amount": _money(payload.get("total_discounts")),
        "shipping_amount": shipping_amount,
        "tax_amount": _money(payload.get("total_tax")),
        "total_amount": _money(payload.get("total_price")),
        "fx_rate_usd": _resolve_fx(currency, fx_rates),
        "financial_status": financial_status,
        "discount_codes": discount_codes,
        "landing_site": payload.get("landing_site"),
        "utm_params": parse_utm_params(payload.get("landing_site")),
        "customer_ref": customer_ref,
        "ordered_at": ordered_at,
        "line_items": line_items,
        "raw_payload": payload,
    }


def transform_refund_webhook(
    payload: dict[str, Any],
    order_currency: str | None = None,
) -> dict[str, Any]:
    """Map a Shopify refunds/create webhook body to OrderRefundIngestRequest kwargs."""
    refund_id = payload.get("id")
    order_id = payload.get("order_id")
    if refund_id is None or order_id is None:
        raise ValueError("Refund webhook payload is missing 'id' or 'order_id'.")

    refund_line_items = []
    commissionable = Decimal("0")
    for entry in payload.get("refund_line_items") or []:
        subtotal = _money(entry.get("subtotal"))
        commissionable += subtotal
        refund_line_items.append(
            {
                "line_item_id": str(entry["line_item_id"]) if entry.get("line_item_id") is not None else None,
                "quantity": int(entry.get("quantity") or 0),
                "subtotal": str(subtotal),
            }
        )

    transactions = payload.get("transactions") or []
    total_refund = Decimal("0")
    currency = None
    for transaction in transactions:
        if str(transaction.get("kind") or "").lower() not in {"refund", "void"}:
            continue
        total_refund += _money(transaction.get("amount"))
        if currency is None and transaction.get("currency"):
            currency = str(transaction["currency"]).upper()
    if total_refund == 0:
        total_refund = commissionable

    if currency is None:
        currency = str(order_currency or "").upper() or None
    if currency not in SUPPORTED_CURRENCIES:
        raise ValueError(
            f"Cannot determine a supported refund currency (got {currency!r}). "
            "Refund transactions carry no currency and the order lookup did not supply one."
        )

    processed_at = payload.get("processed_at") or payload.get("created_at")
    if not processed_at:
        raise ValueError("Refund webhook payload is missing 'processed_at'.")

    return {
        "order_shopify_order_id": str(order_id),
        "shopify_refund_id": str(refund_id),
        "currency": currency,
        "commissionable_refund_amount": commissionable,
        "total_refund_amount": total_refund,
        "refund_line_items": refund_line_items,
        "reason": payload.get("note"),
        "processed_at": processed_at,
        "raw_payload": payload,
    }
