"""Shopify Admin API client for creator discount-code issuance.

Dry-run first: with default settings (SHOPIFY_DRY_RUN=true,
ALLOW_LIVE_SHOPIFY_CALLS=false) no network call is made -- the client
returns the exact requests it would send so operators can review them.
Live calls require BOTH flags flipped AND shop domain + admin token set,
mirroring the AI/TikTok provider live gates.

Only discount issuance lives here. Order/refund data arrives via webhooks
(app/routers/shopify_webhooks.py), not by polling the Admin API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx

from app.core.config import settings


REQUEST_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class DiscountIssueResult:
    mode: str  # "dry_run" | "live"
    code: str
    shopify_price_rule_id: str | None = None
    shopify_discount_code_id: str | None = None
    planned_requests: list[dict[str, Any]] = field(default_factory=list)
    live_blockers: list[str] = field(default_factory=list)


def live_blockers(config: Any = None) -> list[str]:
    cfg = config or settings
    blockers: list[str] = []
    if cfg.shopify_dry_run:
        blockers.append("SHOPIFY_DRY_RUN is true")
    if not cfg.allow_live_shopify_calls:
        blockers.append("ALLOW_LIVE_SHOPIFY_CALLS is false")
    if not cfg.shopify_shop_domain:
        blockers.append("SHOPIFY_SHOP_DOMAIN is not set")
    if not cfg.shopify_admin_api_token:
        blockers.append("SHOPIFY_ADMIN_API_TOKEN is not set")
    return blockers


def _admin_url(cfg: Any, path: str) -> str:
    return f"https://{cfg.shopify_shop_domain}/admin/api/{cfg.shopify_api_version}/{path}"


def _price_rule_body(
    title: str,
    customer_discount_percent: Decimal,
    starts_at: datetime | None,
    ends_at: datetime | None,
) -> dict[str, Any]:
    starts = (starts_at or datetime.now().astimezone()).isoformat()
    body: dict[str, Any] = {
        "price_rule": {
            "title": title,
            "target_type": "line_item",
            "target_selection": "all",
            "allocation_method": "across",
            "value_type": "percentage",
            # Shopify expects a negative percentage string, e.g. "-15.0".
            "value": f"-{customer_discount_percent}",
            "customer_selection": "all",
            "starts_at": starts,
        }
    }
    if ends_at is not None:
        body["price_rule"]["ends_at"] = ends_at.isoformat()
    return body


def issue_discount_code(
    code: str,
    customer_discount_percent: Decimal,
    title: str,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    config: Any = None,
    http_post: Any = None,
) -> DiscountIssueResult:
    """Create a PriceRule + DiscountCode pair in Shopify (or plan it in dry-run).

    `http_post(url, json, headers) -> httpx.Response` is injectable for tests.
    """
    cfg = config or settings
    code = code.strip().upper()
    price_rule_body = _price_rule_body(title, customer_discount_percent, starts_at, ends_at)
    discount_code_body = {"discount_code": {"code": code}}

    blockers = live_blockers(cfg)
    if blockers:
        return DiscountIssueResult(
            mode="dry_run",
            code=code,
            planned_requests=[
                {"method": "POST", "path": "price_rules.json", "body": price_rule_body},
                {
                    "method": "POST",
                    "path": "price_rules/{price_rule_id}/discount_codes.json",
                    "body": discount_code_body,
                },
            ],
            live_blockers=blockers,
        )

    post = http_post or _default_post
    headers = {
        "X-Shopify-Access-Token": cfg.shopify_admin_api_token,
        "Content-Type": "application/json",
    }

    rule_response = post(_admin_url(cfg, "price_rules.json"), json=price_rule_body, headers=headers)
    _raise_for_status("price_rules.json", rule_response)
    price_rule_id = str(rule_response.json()["price_rule"]["id"])

    code_response = post(
        _admin_url(cfg, f"price_rules/{price_rule_id}/discount_codes.json"),
        json=discount_code_body,
        headers=headers,
    )
    _raise_for_status("discount_codes.json", code_response)
    discount_code_id = str(code_response.json()["discount_code"]["id"])

    return DiscountIssueResult(
        mode="live",
        code=code,
        shopify_price_rule_id=price_rule_id,
        shopify_discount_code_id=discount_code_id,
    )


def _default_post(url: str, json: dict[str, Any], headers: dict[str, str]) -> httpx.Response:
    return httpx.post(url, json=json, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)


def _raise_for_status(step: str, response: httpx.Response) -> None:
    if response.status_code >= 400:
        raise RuntimeError(
            f"Shopify Admin API call failed at {step}: HTTP {response.status_code} {response.text[:500]}"
        )
