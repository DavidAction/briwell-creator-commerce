import dataclasses
from decimal import Decimal

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.providers import shopify_admin


client = TestClient(app)

ADMIN = {"X-User-Role": "admin", "X-User-Email": "admin@briwell.test"}
VIEWER = {"X-User-Role": "viewer"}


def _live_config():
    return dataclasses.replace(
        settings,
        shopify_dry_run=False,
        allow_live_shopify_calls=True,
        shopify_shop_domain="briwell-mx.myshopify.com",
        shopify_admin_api_token="shpat_test",
    )


# ---------------------------------------------------------------------------
# Live gate
# ---------------------------------------------------------------------------


def test_default_settings_block_live_calls_with_all_reasons() -> None:
    blockers = shopify_admin.live_blockers()
    assert "SHOPIFY_DRY_RUN is true" in blockers
    assert "ALLOW_LIVE_SHOPIFY_CALLS is false" in blockers
    assert "SHOPIFY_SHOP_DOMAIN is not set" in blockers
    assert "SHOPIFY_ADMIN_API_TOKEN is not set" in blockers


def test_fully_configured_live_settings_have_no_blockers() -> None:
    assert shopify_admin.live_blockers(_live_config()) == []


# ---------------------------------------------------------------------------
# Dry-run issuance
# ---------------------------------------------------------------------------


def test_issue_discount_code_dry_run_plans_both_requests_without_network() -> None:
    def explode(*_a, **_k):
        raise AssertionError("dry-run must not touch the network")

    result = shopify_admin.issue_discount_code(
        code="mari10",
        customer_discount_percent=Decimal("15"),
        title="Briwell creator c-1 / MARI10",
        http_post=explode,
    )

    assert result.mode == "dry_run"
    assert result.code == "MARI10"
    assert result.shopify_price_rule_id is None
    assert [request["path"] for request in result.planned_requests] == [
        "price_rules.json",
        "price_rules/{price_rule_id}/discount_codes.json",
    ]
    rule_body = result.planned_requests[0]["body"]["price_rule"]
    assert rule_body["value"] == "-15"
    assert rule_body["value_type"] == "percentage"
    assert result.planned_requests[1]["body"]["discount_code"]["code"] == "MARI10"
    assert result.live_blockers


# ---------------------------------------------------------------------------
# Live issuance (stubbed HTTP)
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


def test_issue_discount_code_live_creates_rule_then_code() -> None:
    calls = []

    def fake_post(url, json, headers):
        calls.append({"url": url, "json": json, "headers": headers})
        if url.endswith("/price_rules.json"):
            return _FakeResponse(201, {"price_rule": {"id": 111}})
        return _FakeResponse(201, {"discount_code": {"id": 222, "code": "MARI10"}})

    result = shopify_admin.issue_discount_code(
        code="mari10",
        customer_discount_percent=Decimal("15"),
        title="Briwell creator c-1 / MARI10",
        config=_live_config(),
        http_post=fake_post,
    )

    assert result.mode == "live"
    assert result.shopify_price_rule_id == "111"
    assert result.shopify_discount_code_id == "222"
    assert len(calls) == 2
    assert calls[0]["url"] == (
        "https://briwell-mx.myshopify.com/admin/api/2026-01/price_rules.json"
    )
    assert calls[1]["url"].endswith("/price_rules/111/discount_codes.json")
    assert calls[0]["headers"]["X-Shopify-Access-Token"] == "shpat_test"


def test_issue_discount_code_live_raises_on_http_error() -> None:
    def fake_post(url, json, headers):
        return _FakeResponse(422, {"errors": "code taken"})

    try:
        shopify_admin.issue_discount_code(
            code="mari10",
            customer_discount_percent=Decimal("15"),
            title="t",
            config=_live_config(),
            http_post=fake_post,
        )
    except RuntimeError as exc:
        assert "price_rules.json" in str(exc)
        assert "422" in str(exc)
    else:
        raise AssertionError("expected RuntimeError on HTTP 422")


# ---------------------------------------------------------------------------
# /commerce/discount-codes/issue endpoint
# ---------------------------------------------------------------------------


ISSUE_PAYLOAD = {
    "creator_id": "c-1",
    "code": "mari10",
    "commission_rate": "0.10",
    "customer_discount_percent": "15",
}


def test_issue_endpoint_dry_run_returns_plan_without_persisting() -> None:
    response = client.post("/commerce/discount-codes/issue", headers=ADMIN, json=ISSUE_PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "dry_run"
    assert body["persisted"] is False
    assert body["code"] == "MARI10"
    assert body["live_blockers"]
    assert len(body["planned_requests"]) == 2


def test_issue_endpoint_rejects_viewer_role() -> None:
    response = client.post("/commerce/discount-codes/issue", headers=VIEWER, json=ISSUE_PAYLOAD)
    assert response.status_code == 403


def test_issue_endpoint_refuses_live_without_database(monkeypatch) -> None:
    from app.routers import commerce as commerce_module

    monkeypatch.setattr(
        commerce_module.shopify_admin, "live_blockers", lambda config=None: []
    )
    response = client.post("/commerce/discount-codes/issue", headers=ADMIN, json=ISSUE_PAYLOAD)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SHOPIFY_LIVE_REQUIRES_DATABASE"
