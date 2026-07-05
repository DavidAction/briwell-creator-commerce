from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

ADMIN = {"X-User-Role": "admin", "X-User-Email": "admin@briwell.test"}
VIEWER = {"X-User-Role": "viewer"}

VALID_ORDER_PAYLOAD = {
    "shopify_order_id": "gid://shopify/Order/1001",
    "order_number": "#1001",
    "shop_domain": "briwell-mx.myshopify.com",
    "country": "MX",
    "currency": "MXN",
    "subtotal_amount": "1000.00",
    "discount_amount": "0.00",
    "shipping_amount": "50.00",
    "tax_amount": "0.00",
    "total_amount": "1050.00",
    "fx_rate_usd": "0.054",
    "financial_status": "paid",
    "discount_codes": ["CREATORCODE10"],
    "landing_site": "/products/spf?utm_source=tiktok&utm_content=ref123",
    "utm_params": {"utm_source": "tiktok", "utm_content": "ref123"},
    "ordered_at": "2026-07-06T12:00:00Z",
    "line_items": [],
    "raw_payload": {},
}


def test_ingest_order_without_database_returns_validated_not_persisted() -> None:
    response = client.post("/commerce/shopify/orders", headers=ADMIN, json=VALID_ORDER_PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "validated_not_persisted"
    assert "attribution" in body
    assert "accrual_preview" in body
    # With no DB, no code/UTM matches exist -> no attribution decision.
    assert body["attribution"]["creator_id"] is None
    assert body["accrual_preview"] is None


def test_ingest_order_viewer_forbidden() -> None:
    response = client.post("/commerce/shopify/orders", headers=VIEWER, json=VALID_ORDER_PAYLOAD)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"


def test_ingest_order_no_role_header_defaults_to_viewer_forbidden() -> None:
    response = client.post("/commerce/shopify/orders", json=VALID_ORDER_PAYLOAD)
    assert response.status_code == 403


def test_get_orders_allows_all_roles() -> None:
    for headers in (ADMIN, VIEWER, {}):
        response = client.get("/commerce/orders", headers=headers)
        assert response.status_code == 200
        assert response.json()["items"] == []


def test_get_discount_codes_allows_viewer() -> None:
    response = client.get("/commerce/discount-codes", headers=VIEWER)
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_get_ledger_balances_allows_viewer() -> None:
    response = client.get("/commerce/ledger/balances", headers=VIEWER)
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_create_discount_code_viewer_forbidden() -> None:
    response = client.post(
        "/commerce/discount-codes",
        headers=VIEWER,
        json={
            "creator_id": "11111111-1111-1111-1111-111111111111",
            "code": "ABC123",
            "commission_rate": "0.15",
        },
    )
    assert response.status_code == 403


def test_create_discount_code_admin_validated_not_persisted() -> None:
    response = client.post(
        "/commerce/discount-codes",
        headers=ADMIN,
        json={
            "creator_id": "11111111-1111-1111-1111-111111111111",
            "code": "abc123",
            "commission_rate": "0.15",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "validated_not_persisted"
    # code is normalized to uppercase.
    assert body["discount_code"]["code"] == "ABC123"


def test_create_utm_link_normalizes_ref_token_lowercase() -> None:
    response = client.post(
        "/commerce/utm-links",
        headers=ADMIN,
        json={
            "creator_id": "11111111-1111-1111-1111-111111111111",
            "ref_token": "REF-Token1",
            "destination_url": "https://briwell.mx/spf",
            "commission_rate": "0.10",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["utm_link"]["ref_token"] == "ref-token1"


# ---------------------------------------------------------------------------
# Pydantic validation (422s)
# ---------------------------------------------------------------------------


def test_invalid_currency_code_is_422() -> None:
    payload = {**VALID_ORDER_PAYLOAD, "currency": "ARS"}
    response = client.post("/commerce/shopify/orders", headers=ADMIN, json=payload)
    assert response.status_code == 422


def test_negative_amount_is_422() -> None:
    payload = {**VALID_ORDER_PAYLOAD, "subtotal_amount": "-1.00"}
    response = client.post("/commerce/shopify/orders", headers=ADMIN, json=payload)
    assert response.status_code == 422


def test_non_positive_fx_rate_is_422() -> None:
    payload = {**VALID_ORDER_PAYLOAD, "fx_rate_usd": "0"}
    response = client.post("/commerce/shopify/orders", headers=ADMIN, json=payload)
    assert response.status_code == 422


def test_usd_currency_with_fx_rate_not_one_is_422() -> None:
    payload = {**VALID_ORDER_PAYLOAD, "currency": "USD", "fx_rate_usd": "0.9"}
    response = client.post("/commerce/shopify/orders", headers=ADMIN, json=payload)
    assert response.status_code == 422


def test_usd_currency_with_fx_rate_one_is_valid() -> None:
    payload = {**VALID_ORDER_PAYLOAD, "currency": "USD", "fx_rate_usd": "1"}
    response = client.post("/commerce/shopify/orders", headers=ADMIN, json=payload)
    assert response.status_code == 200


def test_reassign_action_without_creator_id_is_422() -> None:
    response = client.post(
        "/commerce/attributions/11111111-1111-1111-1111-111111111111/resolve",
        headers=ADMIN,
        json={"action": "reassign"},
    )
    assert response.status_code == 422
