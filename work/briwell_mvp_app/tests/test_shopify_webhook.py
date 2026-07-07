import base64
import dataclasses
import hashlib
import hmac
import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.commerce.shopify_webhook import (
    parse_fx_rates,
    parse_utm_params,
    transform_order_webhook,
    transform_refund_webhook,
    verify_webhook_hmac,
)
from app.core.config import settings
from app.main import app
from app.routers import shopify_webhooks as webhooks_module


client = TestClient(app)

SECRET = "test-webhook-secret"
FX_RATES = {"MXN": Decimal("0.054"), "PEN": Decimal("0.27")}


def _sign(body: bytes, secret: str = SECRET) -> str:
    return base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()


ORDER_WEBHOOK = {
    "id": 5001,
    "order_number": 1001,
    "currency": "MXN",
    "subtotal_price": "1000.00",
    "total_discounts": "100.00",
    "total_tax": "160.00",
    "total_price": "1110.00",
    "total_shipping_price_set": {"shop_money": {"amount": "50.00", "currency_code": "MXN"}},
    "financial_status": "paid",
    "created_at": "2026-07-07T10:00:00-05:00",
    "landing_site": "/products/spf?utm_source=tiktok&utm_medium=creator_bio&utm_content=ref123&foo=bar",
    "discount_codes": [{"code": "mari10", "amount": "100.00", "type": "percentage"}],
    "customer": {"id": 777},
    "shipping_address": {"country_code": "MX"},
    "line_items": [
        {
            "id": 9001,
            "title": "SPF50 Sun Serum",
            "sku": "SPF50",
            "product_id": 42,
            "quantity": 2,
            "price": "500.00",
            "total_discount": "100.00",
        }
    ],
}

REFUND_WEBHOOK = {
    "id": 7001,
    "order_id": 5001,
    "note": "customer request",
    "processed_at": "2026-07-08T09:00:00-05:00",
    "refund_line_items": [
        {"line_item_id": 9001, "quantity": 1, "subtotal": "450.00"},
    ],
    "transactions": [
        {"kind": "refund", "amount": "500.00", "currency": "MXN"},
    ],
}


# ---------------------------------------------------------------------------
# HMAC verification
# ---------------------------------------------------------------------------


def test_verify_webhook_hmac_accepts_valid_signature() -> None:
    body = b'{"id": 1}'
    assert verify_webhook_hmac(SECRET, body, _sign(body)) is True


def test_verify_webhook_hmac_rejects_wrong_signature_missing_header_and_empty_secret() -> None:
    body = b'{"id": 1}'
    assert verify_webhook_hmac(SECRET, body, _sign(body, "other-secret")) is False
    assert verify_webhook_hmac(SECRET, body, None) is False
    assert verify_webhook_hmac("", body, _sign(body)) is False


# ---------------------------------------------------------------------------
# FX / UTM parsing
# ---------------------------------------------------------------------------


def test_parse_fx_rates_parses_pairs_and_rejects_bad_values() -> None:
    assert parse_fx_rates("MXN:0.054, pen:0.27") == {"MXN": Decimal("0.054"), "PEN": Decimal("0.27")}
    assert parse_fx_rates("") == {}
    with pytest.raises(ValueError):
        parse_fx_rates("MXN:abc")
    with pytest.raises(ValueError):
        parse_fx_rates("MXN:-1")


def test_parse_utm_params_keeps_only_utm_keys() -> None:
    parsed = parse_utm_params("/p?utm_source=tiktok&utm_content=ref123&foo=bar")
    assert parsed == {"utm_source": "tiktok", "utm_content": "ref123"}
    assert parse_utm_params(None) == {}


# ---------------------------------------------------------------------------
# Order transform
# ---------------------------------------------------------------------------


def test_transform_order_webhook_maps_all_ingest_fields() -> None:
    result = transform_order_webhook(ORDER_WEBHOOK, FX_RATES, shop_domain="briwell-mx.myshopify.com")

    assert result["shopify_order_id"] == "5001"
    assert result["order_number"] == "1001"
    assert result["shop_domain"] == "briwell-mx.myshopify.com"
    assert result["country"] == "MX"
    assert result["currency"] == "MXN"
    assert result["subtotal_amount"] == Decimal("1000.00")
    assert result["discount_amount"] == Decimal("100.00")
    assert result["shipping_amount"] == Decimal("50.00")
    assert result["tax_amount"] == Decimal("160.00")
    assert result["total_amount"] == Decimal("1110.00")
    assert result["fx_rate_usd"] == Decimal("0.054")
    assert result["financial_status"] == "paid"
    assert result["discount_codes"] == ["MARI10"]
    assert result["utm_params"] == {
        "utm_source": "tiktok",
        "utm_medium": "creator_bio",
        "utm_content": "ref123",
    }
    assert result["customer_ref"] == "777"
    assert result["line_items"][0]["shopify_line_item_id"] == "9001"
    assert result["line_items"][0]["unit_price"] == Decimal("500.00")
    assert result["raw_payload"] is ORDER_WEBHOOK


def test_transform_order_webhook_usd_gets_fx_rate_one_without_config() -> None:
    payload = {**ORDER_WEBHOOK, "currency": "USD"}
    result = transform_order_webhook(payload, {})
    assert result["fx_rate_usd"] == Decimal("1")


def test_transform_order_webhook_fails_closed_on_missing_fx_and_bad_currency() -> None:
    with pytest.raises(ValueError, match="No FX rate configured"):
        transform_order_webhook(ORDER_WEBHOOK, {})
    with pytest.raises(ValueError, match="Unsupported order currency"):
        transform_order_webhook({**ORDER_WEBHOOK, "currency": "BRL"}, FX_RATES)


def test_transform_order_webhook_cancelled_at_overrides_financial_status() -> None:
    payload = {**ORDER_WEBHOOK, "cancelled_at": "2026-07-07T11:00:00-05:00"}
    result = transform_order_webhook(payload, FX_RATES)
    assert result["financial_status"] == "cancelled"


# ---------------------------------------------------------------------------
# Refund transform
# ---------------------------------------------------------------------------


def test_transform_refund_webhook_maps_amounts_and_currency_from_transactions() -> None:
    result = transform_refund_webhook(REFUND_WEBHOOK)

    assert result["order_shopify_order_id"] == "5001"
    assert result["shopify_refund_id"] == "7001"
    assert result["currency"] == "MXN"
    assert result["commissionable_refund_amount"] == Decimal("450.00")
    assert result["total_refund_amount"] == Decimal("500.00")
    assert result["reason"] == "customer request"


def test_transform_refund_webhook_uses_order_currency_when_no_transactions() -> None:
    payload = {**REFUND_WEBHOOK, "transactions": []}
    result = transform_refund_webhook(payload, order_currency="MXN")
    assert result["currency"] == "MXN"
    assert result["total_refund_amount"] == Decimal("450.00")

    with pytest.raises(ValueError, match="refund currency"):
        transform_refund_webhook(payload, order_currency=None)


# ---------------------------------------------------------------------------
# Webhook endpoints (no DB -> validated_not_persisted path)
# ---------------------------------------------------------------------------


def _configure_secret(monkeypatch, secret: str, fx_rates: str = "MXN:0.054,PEN:0.27") -> None:
    patched = dataclasses.replace(
        settings, shopify_webhook_secret=secret, shopify_fx_rates_raw=fx_rates
    )
    monkeypatch.setattr(webhooks_module, "settings", patched)


def test_order_webhook_rejects_all_traffic_when_secret_unset(monkeypatch) -> None:
    _configure_secret(monkeypatch, "")
    body = json.dumps(ORDER_WEBHOOK).encode()
    response = client.post(
        "/commerce/webhooks/shopify/orders",
        content=body,
        headers={"X-Shopify-Hmac-Sha256": _sign(body), "Content-Type": "application/json"},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "WEBHOOK_SECRET_NOT_CONFIGURED"


def test_order_webhook_rejects_invalid_hmac(monkeypatch) -> None:
    _configure_secret(monkeypatch, SECRET)
    body = json.dumps(ORDER_WEBHOOK).encode()
    response = client.post(
        "/commerce/webhooks/shopify/orders",
        content=body,
        headers={"X-Shopify-Hmac-Sha256": _sign(body, "wrong"), "Content-Type": "application/json"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "WEBHOOK_HMAC_INVALID"


def test_order_webhook_accepts_signed_payload_and_runs_ingest(monkeypatch) -> None:
    _configure_secret(monkeypatch, SECRET)
    body = json.dumps(ORDER_WEBHOOK).encode()
    response = client.post(
        "/commerce/webhooks/shopify/orders",
        content=body,
        headers={
            "X-Shopify-Hmac-Sha256": _sign(body),
            "X-Shopify-Shop-Domain": "briwell-mx.myshopify.com",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["webhook"] == "orders"
    assert result["status"] == "validated_not_persisted"
    assert result["order"]["shopify_order_id"] == "5001"
    assert result["order"]["shop_domain"] == "briwell-mx.myshopify.com"


def test_order_webhook_returns_422_when_fx_rate_missing(monkeypatch) -> None:
    _configure_secret(monkeypatch, SECRET, fx_rates="")
    body = json.dumps(ORDER_WEBHOOK).encode()
    response = client.post(
        "/commerce/webhooks/shopify/orders",
        content=body,
        headers={"X-Shopify-Hmac-Sha256": _sign(body), "Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "WEBHOOK_TRANSFORM_FAILED"


def test_refund_webhook_accepts_signed_payload(monkeypatch) -> None:
    _configure_secret(monkeypatch, SECRET)
    body = json.dumps(REFUND_WEBHOOK).encode()
    response = client.post(
        "/commerce/webhooks/shopify/refunds",
        content=body,
        headers={"X-Shopify-Hmac-Sha256": _sign(body), "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["webhook"] == "refunds"
    assert result["status"] == "validated_not_persisted"


def test_refund_webhook_rejects_invalid_json(monkeypatch) -> None:
    _configure_secret(monkeypatch, SECRET)
    body = b"not-json"
    response = client.post(
        "/commerce/webhooks/shopify/refunds",
        content=body,
        headers={"X-Shopify-Hmac-Sha256": _sign(body), "Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "WEBHOOK_BODY_INVALID"
