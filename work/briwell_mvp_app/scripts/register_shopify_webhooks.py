from __future__ import annotations

"""Register (or preview) Briwell's Shopify order/refund webhooks.

Shopify pushes order and refund events to public HTTPS endpoints. This script
registers the three topics Briwell consumes, pointing them at the deployed
webhook receiver, and is idempotent: it lists existing webhooks first and skips
any topic already pointing at the same address.

Dry-run by default. It performs live calls only when the same gates that guard
discount issuance are open (SHOPIFY_DRY_RUN=false and ALLOW_LIVE_SHOPIFY_CALLS=true),
plus the shop domain and admin token are set. Without --public-base it only
prints what it would do.

Usage:
    python -m scripts.register_shopify_webhooks --public-base https://api.briwell.co
    python -m scripts.register_shopify_webhooks --public-base https://api.briwell.co --list

The public base must be the internet-reachable origin of the FastAPI app; the
receiver paths (/commerce/webhooks/shopify/{orders,refunds}) are appended here.
"""

import argparse
import sys

import httpx

from app.core.config import settings
from app.providers import shopify_admin

# Shopify topic -> Briwell receiver path. orders/updated re-fires on
# financial_status changes (e.g. paid, refunded); the receiver upserts idempotently.
WEBHOOK_TOPICS = {
    "orders/create": "/commerce/webhooks/shopify/orders",
    "orders/updated": "/commerce/webhooks/shopify/orders",
    "refunds/create": "/commerce/webhooks/shopify/refunds",
}

REQUEST_TIMEOUT_SECONDS = 15.0


def _headers() -> dict[str, str]:
    return {
        "X-Shopify-Access-Token": settings.shopify_admin_api_token,
        "Content-Type": "application/json",
    }


def _admin_url(path: str) -> str:
    return f"https://{settings.shopify_shop_domain}/admin/api/{settings.shopify_api_version}/{path}"


def list_webhooks() -> list[dict]:
    response = httpx.get(
        _admin_url("webhooks.json"), headers=_headers(), timeout=REQUEST_TIMEOUT_SECONDS
    )
    if response.status_code >= 400:
        raise RuntimeError(f"List webhooks failed: HTTP {response.status_code} {response.text[:400]}")
    return response.json().get("webhooks", [])


def register_webhook(topic: str, address: str) -> dict:
    body = {"webhook": {"topic": topic, "address": address, "format": "json"}}
    response = httpx.post(
        _admin_url("webhooks.json"), json=body, headers=_headers(), timeout=REQUEST_TIMEOUT_SECONDS
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"Register {topic} failed: HTTP {response.status_code} {response.text[:400]}"
        )
    return response.json().get("webhook", {})


def _desired(public_base: str) -> dict[str, str]:
    base = public_base.rstrip("/")
    return {topic: f"{base}{path}" for topic, path in WEBHOOK_TOPICS.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Register Briwell Shopify webhooks.")
    parser.add_argument(
        "--public-base",
        help="Public HTTPS origin of the deployed API, e.g. https://api.briwell.co",
    )
    parser.add_argument("--list", action="store_true", help="List current webhooks and exit.")
    args = parser.parse_args(argv)

    blockers = shopify_admin.live_blockers()

    if not settings.shopify_webhook_secret and not blockers:
        print(
            "REFUSING: SHOPIFY_WEBHOOK_SECRET is not set. The receiver rejects all "
            "deliveries (503) without it, so registering webhooks now would only "
            "produce failed deliveries. Set the secret first."
        )
        return 2

    if args.list:
        if blockers:
            print("Cannot list in dry-run/unconfigured mode. Open the live gates:")
            for blocker in blockers:
                print(f"  - {blocker}")
            return 1
        for webhook in list_webhooks():
            print(f"  {webhook.get('topic'):16} -> {webhook.get('address')}  (id={webhook.get('id')})")
        return 0

    if not args.public_base:
        parser.error("--public-base is required unless --list is used")

    desired = _desired(args.public_base)

    if blockers:
        print("DRY RUN (live Shopify calls are gated). Would register:")
        for topic, address in desired.items():
            print(f"  POST webhooks.json  {topic:16} -> {address}")
        print("\nOpen the gates to apply:")
        for blocker in blockers:
            print(f"  - {blocker}")
        return 0

    existing = {(w.get("topic"), w.get("address")) for w in list_webhooks()}
    for topic, address in desired.items():
        if (topic, address) in existing:
            print(f"skip (already registered): {topic} -> {address}")
            continue
        created = register_webhook(topic, address)
        print(f"registered: {topic} -> {address}  (id={created.get('id')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
