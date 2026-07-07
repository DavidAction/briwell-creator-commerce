"""Shopify webhook receivers (orders/create, orders/updated, refunds/create).

These endpoints are intentionally outside header/OIDC auth: Shopify cannot
send our auth headers. HMAC-SHA256 signature verification against
SHOPIFY_WEBHOOK_SECRET is the authentication. Fail-closed: if the secret is
not configured the endpoints refuse all deliveries (503) rather than accept
unsigned traffic.

After verification, payloads are transformed and fed through the exact same
ingest functions as the operator API, so attribution/accrual/ledger behavior
is identical for webhook-delivered and manually ingested orders.
"""

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from app.commerce.shopify_webhook import (
    parse_fx_rates,
    transform_order_webhook,
    transform_refund_webhook,
    verify_webhook_hmac,
)
from app.core.auth import UserContext
from app.core.config import settings
from app.core.db import database_enabled
from app.repositories import commerce as commerce_repository
from app.routers.commerce import (
    OrderRefundIngestRequest,
    ShopifyOrderIngestRequest,
    ingest_shopify_order,
    ingest_shopify_refund,
)


router = APIRouter(prefix="/commerce/webhooks/shopify", tags=["commerce-webhooks"])

WEBHOOK_ACTOR = UserContext(role="operator", email="shopify-webhook@system")


async def _verified_body(request: Request) -> bytes:
    if not settings.shopify_webhook_secret:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "WEBHOOK_SECRET_NOT_CONFIGURED",
                "message": "SHOPIFY_WEBHOOK_SECRET is not set; refusing unsigned webhook traffic.",
            },
        )
    body = await request.body()
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256")
    if not verify_webhook_hmac(settings.shopify_webhook_secret, body, hmac_header):
        raise HTTPException(
            status_code=401,
            detail={"code": "WEBHOOK_HMAC_INVALID", "message": "Webhook HMAC verification failed."},
        )
    return body


def _parse_json(body: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "WEBHOOK_BODY_INVALID", "message": f"Webhook body is not valid JSON: {exc}"},
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=400,
            detail={"code": "WEBHOOK_BODY_INVALID", "message": "Webhook body must be a JSON object."},
        )
    return parsed


@router.post("/orders")
async def receive_order_webhook(request: Request) -> dict[str, Any]:
    body = await _verified_body(request)
    payload = _parse_json(body)
    try:
        transformed = transform_order_webhook(
            payload,
            fx_rates=parse_fx_rates(settings.shopify_fx_rates_raw),
            shop_domain=request.headers.get("X-Shopify-Shop-Domain"),
        )
        ingest_request = ShopifyOrderIngestRequest(**transformed)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "WEBHOOK_TRANSFORM_FAILED", "message": str(exc)},
        ) from exc
    result = ingest_shopify_order(ingest_request, user=WEBHOOK_ACTOR)
    return {"webhook": "orders", **result}


@router.post("/refunds")
async def receive_refund_webhook(request: Request) -> dict[str, Any]:
    body = await _verified_body(request)
    payload = _parse_json(body)

    order_currency: str | None = None
    order_shopify_id = payload.get("order_id")
    if database_enabled() and order_shopify_id is not None:
        order = commerce_repository.get_order_by_shopify_id(str(order_shopify_id))
        if order is not None:
            order_currency = order["currency"]

    try:
        transformed = transform_refund_webhook(payload, order_currency=order_currency)
        ingest_request = OrderRefundIngestRequest(**transformed)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "WEBHOOK_TRANSFORM_FAILED", "message": str(exc)},
        ) from exc
    result = ingest_shopify_refund(ingest_request, user=WEBHOOK_ACTOR)
    return {"webhook": "refunds", **result}
